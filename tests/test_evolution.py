"""Self-evolution test harness.

Simulates multiple realistic conversations and checks the evolution pass behaves
correctly: stays silent when it should, evolves (memory/skill) when it should,
backs up before editing, notifies the user, and supports undo.

Two modes:
  - stub  (default): the review agent's reasoning is replaced by a scripted
    output per scenario. Fast, deterministic, validates the WIRING (backup,
    record, inject, notify, undo, protection). No model calls.
  - real:  the review agent runs the configured model for real. Validates the
    QUALITY of the judgement (does it correctly decide to act / stay silent).

Run:
    python tests/test_evolution.py            # stub mode
    python tests/test_evolution.py --real      # real model mode
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeChannel:
    """Captures channel.send calls instead of sending."""

    def __init__(self):
        self.sent = []

    def send(self, reply, context):
        self.sent.append({"content": getattr(reply, "content", str(reply)), "receiver": context.get("receiver")})


class FakeModel:
    pass


class FakeAgent:
    """Minimal stand-in for a chat Agent."""

    def __init__(self, messages, tools=None):
        import threading
        self.messages = messages
        self.messages_lock = threading.Lock()
        self.tools = tools or []
        self.model = FakeModel()
        self.skill_manager = None
        self.memory_manager = None


class FakeReviewAgent:
    """Review agent whose run_stream returns a scripted result (stub mode)."""

    def __init__(self, scripted_output, workspace, on_edit=None):
        self._out = scripted_output
        self._workspace = workspace
        self._on_edit = on_edit
        self.model = None

    def run_stream(self, user_message, clear_history=False, **kwargs):
        # Simulate the side effects a real review agent would perform.
        if self._on_edit:
            self._on_edit(self._workspace)
        return self._out


class FakeAgentBridge:
    """Stand-in for AgentBridge wiring used by the executor."""

    def __init__(self, agent, scripted_output, on_edit=None):
        self.agents = {"session_test": agent}
        self.default_agent = agent
        self._scripted = scripted_output
        self._on_edit = on_edit
        self.injected = []

    def create_agent(self, **kwargs):
        from agent.memory.config import get_default_memory_config
        ws = get_default_memory_config().get_workspace()
        return FakeReviewAgent(self._scripted, ws, on_edit=self._on_edit)

    def remember_scheduled_output(self, session_id, content, channel_type="", task_description=""):
        self.injected.append(content)


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------
def _setup_workspace():
    """Create a realistic temp workspace: seeded memory + real editable skills.

    Mirrors a real Maia workspace closely enough that the model has genuine
    content to read, reason about, and edit during a real evolution pass.
    """
    ws = Path(tempfile.mkdtemp(prefix="evo_test_"))
    (ws / "MEMORY.md").write_text(
        "# Long-term Memory\n\n"
        "## User\n"
        "- Name: David\n"
        "- Lives in Shenzhen, works as a backend engineer\n"
        "- Company: a fintech startup, team of 8\n\n"
        "## Preferences\n"
        "- Likes detailed technical explanations\n",
        encoding="utf-8",
    )
    (ws / "memory").mkdir()
    (ws / "output").mkdir()
    skills = ws / "skills"

    # Editable skill 1: weekly report generator (has a structural gap: no risk).
    (skills / "weekly-report").mkdir(parents=True)
    (skills / "weekly-report" / "SKILL.md").write_text(
        "# Weekly Report\n\n"
        "Generate a weekly work report from the user's notes.\n\n"
        "## Steps\n"
        "1. Collect this week's completed items.\n"
        "2. Summarize key progress in 3-5 bullets.\n"
        "3. List next week's plan.\n\n"
        "## Output format\n"
        "Markdown with sections: This week / Next week\n",
        encoding="utf-8",
    )

    # Editable skill 2: expense tracker (has a wrong currency-format step).
    (skills / "expense-tracker").mkdir(parents=True)
    (skills / "expense-tracker" / "SKILL.md").write_text(
        "# Expense Tracker\n\n"
        "Record an expense into output/expenses.md.\n\n"
        "## Steps\n"
        "1. Parse amount and category from the user message.\n"
        "2. Append a row to output/expenses.md.\n"
        "3. Format the amount with a `$` prefix.\n",
        encoding="utf-8",
    )

    # Editable skill 3: an API caller whose SKILL.md hardcodes a WRONG endpoint
    # host. The conversation discovers the correct host at runtime; the right
    # fix is to edit this file's source, not just log the corrected fact.
    (skills / "data-fetch").mkdir(parents=True)
    (skills / "data-fetch" / "SKILL.md").write_text(
        "# Data Fetch\n\n"
        "Fetch records from the data service.\n\n"
        "## Steps\n"
        "1. Build the request payload from the user's query.\n"
        "2. POST it to `https://api.example-wrong.com/v1/fetch`.\n"
        "3. Parse and return the `data` field.\n",
        encoding="utf-8",
    )

    # Protected built-in skill: must never be edited by evolution.
    (skills / "image-generation").mkdir(parents=True)
    (skills / "image-generation" / "SKILL.md").write_text(
        "# Image Generation (built-in)\nDo not modify.\n", encoding="utf-8"
    )
    return ws


def _point_config_at(ws):
    """Force the global memory config to use the temp workspace."""
    from agent.memory.config import MemoryConfig, set_global_memory_config
    set_global_memory_config(MemoryConfig(workspace_root=str(ws)))


def _make_messages(turns):
    msgs = []
    for u, a in turns:
        msgs.append({"role": "user", "content": u})
        msgs.append({"role": "assistant", "content": a})
    return msgs


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
def _review_note(learned, change, undo="undo the last review"):
    return (
        "I just finished a self-review.\n"
        f"- Learned: {learned}\n"
        f"- Changed: {change}\n"
        f"If this is wrong, reply \"{undo}\"."
    )


def scenario_silent():
    """Pure small talk -> should stay SILENT (no change, no notify)."""
    return {
        "name": "small talk (should stay SILENT)",
        "goal": "none",
        "turns": [
            ("You there?", "Yes. What can I help with?"),
            ("It's Friday. The weekend is finally here.", "It is. Rest well this weekend."),
            ("Ha, yes. That's all.", "Okay. Call me anytime."),
        ],
        "scripted": "[SILENT]",
        "on_edit": None,
        "expect_evolved": False,
    }


def scenario_silent_qa():
    """A normal knowledge Q&A -> nothing durable, should stay SILENT."""
    return {
        "name": "ordinary Q&A (should stay SILENT)",
        "goal": "none",
        "turns": [
            ("What is the difference between a Python list and a tuple?",
             "A list is mutable and uses []. A tuple is immutable and uses (). Tuples use less memory and can be dict keys."),
            ("When should I use a tuple?", "When the data must not change, or when you need a dict key or set item."),
            ("Got it, thanks.", "You're welcome."),
        ],
        "scripted": "[SILENT]",
        "on_edit": None,
        "expect_evolved": False,
    }


def scenario_silent_transient():
    """User shares transient, non-durable info -> should stay SILENT."""
    return {
        "name": "transient info (should stay SILENT)",
        "goal": "none",
        "turns": [
            ("Is today's weather good for a run in Seattle?", "Seattle is cloudy and 68F. Humidity rises this evening. Morning or night is better."),
            ("I'll go tonight then.", "Okay. Bring water."),
            ("Sure.", "OK"),
        ],
        "scripted": "[SILENT]",
        "on_edit": None,
        "expect_evolved": False,
    }


def scenario_silent_advice():
    """User asks for one-off advice, no reusable workflow -> should stay SILENT."""
    return {
        "name": "one-off advice (should stay SILENT)",
        "goal": "none",
        "turns": [
            ("Give me three names for a cafe.", "Try: 1) Daylight Coffee 2) Corner 3) Half Pace."),
            ("The second one is good.", "Yes. Corner is short and easy to remember."),
            ("We'll use that.", "Great. Good luck with the opening."),
        ],
        "scripted": "[SILENT]",
        "on_edit": None,
        "expect_evolved": False,
    }


def scenario_memory_preference():
    """User states a durable working preference -> update MEMORY.md."""
    def edit(ws):
        from datetime import datetime
        p = ws / "memory" / (datetime.now().strftime("%Y-%m-%d") + ".md")
        p.write_text((p.read_text() if p.exists() else "") + "- Prefers concise replies; avoid long explanations\n", encoding="utf-8")

    return {
        "name": "memory preference (should note in daily memory)",
        "goal": "memory",
        "turns": [
            ("Can you explain what a database transaction is?", "A transaction is a unit of work that either fully succeeds or fully fails. It has four properties, ACID: atomicity, consistency, isolation, and durability. (Then five long paragraphs.)"),
            ("Stop, stop. That is too long.", "Sorry. I went into too much detail."),
            ("Right. From now on keep answers short and focused. No long essays.", "Understood."),
            ("Yes, that is better.", "OK"),
        ],
        "scripted": _review_note(
            "You want short answers that stay on the point",
            "Updated long-term memory in MEMORY.md",
        ),
        "on_edit": edit,
        "expect_evolved": True,
        "expect_memory_contains": "concise",
    }


def scenario_memory_correction():
    """User corrects a wrong fact the agent stated -> fix MEMORY.md."""
    def edit(ws):
        from datetime import datetime
        p = ws / "memory" / (datetime.now().strftime("%Y-%m-%d") + ".md")
        p.write_text((p.read_text() if p.exists() else "") + "- Correction: team size is now 15 (was recorded as 8)\n", encoding="utf-8")

    return {
        "name": "memory correction (should note correction in daily)",
        "goal": "memory",
        "turns": [
            ("We hired a few more people.", "I remember a team of 8. Growing is good."),
            ("No. We are 15 now. You had that wrong last time.", "Sorry. You are a team of 15 now."),
            ("Yes. Remember that.", "Saved."),
        ],
        "scripted": _review_note(
            "The team is 15 people now (it was recorded as 8)",
            "Corrected long-term memory in MEMORY.md",
        ),
        "on_edit": edit,
        "expect_evolved": True,
        "expect_memory_contains": "15",
    }


def scenario_skill_gap():
    """Using weekly-report reveals a missing section -> patch the skill."""
    def edit(ws):
        p = ws / "skills" / "weekly-report" / "SKILL.md"
        p.write_text(p.read_text() + "4. List risk items / blockers.\n", encoding="utf-8")

    return {
        "name": "skill gap (should patch weekly-report skill)",
        "goal": "skill",
        "turns": [
            ("Use the weekly-report skill. Notes: rebuilt the payment gateway, fixed 3 production bugs, and integrated the risk API.",
             "Here is the weekly-report draft:\n\n## This week\n- Rebuilt the payment gateway\n- Fixed 3 production bugs\n- Integrated the risk API\n\n## Next week\n- Finish the risk API integration"),
            ("Good, but every report misses the risks section. Our lead always asks for it.", "You are right. Risks matter."),
            ("Yes. Make the weekly-report skill always include a risks section.", "I will add that step to the skill."),
        ],
        "scripted": _review_note(
            "Weekly reports must include a Risks section",
            "Added a risks step to the weekly-report skill",
        ),
        "on_edit": edit,
        "expect_evolved": True,
        "expect_skill_contains": ("weekly-report", "risk"),
    }


def scenario_skill_error():
    """A skill step is wrong (currency format) -> correct the skill."""
    def edit(ws):
        p = ws / "skills" / "expense-tracker" / "SKILL.md"
        p.write_text(p.read_text().replace("`$` prefix", "`¥` prefix (RMB)"), encoding="utf-8")

    return {
        "name": "skill error (should fix expense-tracker skill)",
        "goal": "skill",
        "turns": [
            ("Use the expense skill. Lunch was 35.", "Recorded: lunch $35 (written to output/expenses.md)."),
            ("Why dollars? We use yuan.", "Sorry. The format should be ¥35."),
            ("Right. That skill should always use the yuan sign.", "I will fix the currency format in the skill."),
        ],
        "scripted": _review_note(
            "Expenses should use the yuan sign, not $",
            "Fixed the currency step in the expense-tracker skill",
        ),
        "on_edit": edit,
        "expect_evolved": True,
        "expect_skill_contains": ("expense-tracker", "¥"),
    }


def scenario_skill_wrong_config():
    """A skill's SKILL.md hardcodes a wrong endpoint; the chat works around it
    at runtime. Correct evolution = FIX the skill source, not log a memory note.
    """
    def edit(ws):
        p = ws / "skills" / "data-fetch" / "SKILL.md"
        p.write_text(
            p.read_text().replace("api.example-wrong.com", "api.example-correct.com"),
            encoding="utf-8",
        )

    return {
        "name": "skill config error (should fix skill source, not log memory)",
        "goal": "skill",
        "turns": [
            ("Use the data-fetch skill to pull the latest data.",
             "I POSTed to https://api.example-wrong.com/v1/fetch as the skill says. The connection failed."),
            ("That host is wrong. Use api.example-correct.com.",
             "Switched to https://api.example-correct.com/v1/fetch and got the data."),
            ("Yes, that is the right host.", "Understood. That is the correct service address."),
        ],
        # The model must decide on its own to edit the skill; we still provide a
        # scripted output for stub mode wiring.
        "scripted": _review_note(
            "The correct data-fetch host is api.example-correct.com",
            "Fixed the endpoint written in the data-fetch skill",
        ),
        "on_edit": edit,
        "expect_evolved": True,
        "expect_skill_contains": ("data-fetch", "api.example-correct.com"),
    }


def scenario_skill_create():
    """A reusable, repeatable workflow emerges that no skill covers, and the
    user explicitly asks to make it permanent -> CREATE a new skill.
    """
    return {
        "name": "skill create (should create a new skill)",
        "goal": "skill",
        "turns": [
            ("Every Monday, turn customer feedback into a standup brief: classify each item as severe, normal, or suggestion, count each class, then write a 3-sentence summary.",
             "This week's brief:\n\n## Severe (2)\n- Payment failed\n- Data lost\n## Normal (3)\n- Slow load\n## Suggestion (1)\n- Add a dark mode\n\nSummary: stability issues dominate. Check payments and the data path first. Schedule the rest."),
            ("That format is right. I asked for the same thing last week.", "Classify, count, then three summary sentences. That flow works."),
            ("Yes. I need this every Monday. Save the flow, and run it when I say 'make the customer feedback brief'.",
             "I will save the customer feedback brief as a reusable skill."),
        ],
        "scripted": _review_note(
            "Every Monday you want a customer feedback brief: classify, count, then three sentences",
            "Created a customer feedback brief skill for that flow",
        ),
        "on_edit": _create_briefing_skill,
        "expect_evolved": True,
        "expect_new_skill": True,
    }


def scenario_skill_create_implicit():
    """A complex, clearly-structured multi-step workflow is executed once. The
    user NEVER says "I do this weekly" or "make this a skill". The agent must
    judge on its own that this is a reusable procedure worth capturing.

    This is the realistic, harder case: no explicit instruction to create a
    skill, only an obviously repeatable workflow.
    """
    return {
        "name": "implicit skill (complex workflow, user never asks to save)",
        "goal": "skill",
        "turns": [
            ("Compare Notion, Confluence, and Coda.",
             "I will use a fixed method:\n1. Set the dimensions: price, collaboration, templates, API, and localization.\n2. Collect each product on those dimensions.\n3. Build a comparison table.\n4. Give a conclusion and a recommendation.\n\n(Then a full five-dimension table and a conclusion.)"),
            ("Good. Use the same method for Slack, Teams, and Discord.",
             "Using the same method (price, collaboration, templates, API, localization, then a table and a conclusion).\n\n(Then a second table and a recommendation.)"),
            ("That conclusion is clear.", "The five-dimension comparison stays easy to follow."),
        ],
        # In real mode the model decides on its own. The scripted side effect
        # only wires stub mode; it emulates capturing the procedure as a skill.
        "scripted": _review_note(
            "Competitor research follows a fixed method: five dimensions, collect, table, conclusion",
            "Saved that competitor-research flow as a reusable skill",
        ),
        "on_edit": _create_competitor_skill,
        "expect_evolved": True,
        "expect_new_skill": True,
    }


def _create_competitor_skill(ws):
    """Stub side effect: emulate capturing the competitor-research procedure."""
    d = ws / "skills" / "competitor-research"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "# Competitor Research\n\n"
        "Compare a set of products with a fixed methodology.\n\n"
        "## Steps\n"
        "1. Fix the comparison dimensions (pricing, collaboration, templates, API, localization).\n"
        "2. Collect info per product across each dimension.\n"
        "3. Build a comparison table.\n"
        "4. Give a conclusion and recommendation.\n",
        encoding="utf-8",
    )


def scenario_skill_no_create():
    """A one-off, novel task with no sign of recurrence -> must NOT create a
    skill (and ideally stay silent). Guards against over-eager skill creation.
    """
    return {
        "name": "do not create a skill (one-off task)",
        "goal": "none",
        "turns": [
            ("Translate this into English: the celebration dinner tonight moves to 8.", "The celebration dinner tonight is moved to 8 PM."),
            ("Thanks.", "You're welcome."),
            ("That is all.", "Okay. Call me anytime."),
        ],
        "scripted": "[SILENT]",
        "on_edit": None,
        "expect_evolved": False,
        "expect_no_new_skill": True,
    }


def _create_briefing_skill(ws):
    """Stub side effect: emulate creating a new skill under workspace skills/."""
    d = ws / "skills" / "customer-feedback-briefing"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "# Customer Feedback Briefing\n\n"
        "Turn raw customer feedback into a standup briefing.\n\n"
        "## Steps\n"
        "1. Classify each item as severe, normal, or suggestion.\n"
        "2. Count items per category.\n"
        "3. Write a 3-sentence summary.\n",
        encoding="utf-8",
    )


def scenario_unfinished_task():
    """A promised deliverable was not produced -> finish it now via tools."""
    def edit(ws):
        p = ws / "output" / "team-roster.md"
        p.write_text("# Team Roster (backend)\n- Wei Zhang\n- Na Li\n- Qiang Wang\n- David\n", encoding="utf-8")

    return {
        "name": "unfinished task (should finish and write the output file)",
        "goal": "task",
        "turns": [
            ("Save a backend team roster. Members: Wei Zhang, Na Li, Qiang Wang, and me (David).",
             "Four people: Wei Zhang, Na Li, Qiang Wang, and David. I will save output/team-roster.md."),
            ("Thanks. I am heading into a meeting.", "I will do it now."),
            ("(The user left and the session stopped before the file was written.)", "(The assistant had not written the file when the chat stopped.)"),
        ],
        "scripted": _review_note(
            "A promised team roster was never written",
            "Wrote the backend roster to output/team-roster.md",
            undo="undo the last review if you do not want it",
        ),
        "on_edit": edit,
        "expect_evolved": True,
        "expect_output_file": "team-roster.md",
    }


SCENARIOS = [
    scenario_silent,
    scenario_silent_qa,
    scenario_silent_transient,
    scenario_silent_advice,
    scenario_memory_preference,
    scenario_memory_correction,
    scenario_skill_gap,
    scenario_skill_error,
    scenario_skill_wrong_config,
    scenario_skill_create,
    scenario_skill_create_implicit,
    scenario_skill_no_create,
    scenario_unfinished_task,
]

# Skill directories present in a fresh workspace; anything beyond these that
# appears after a pass is a newly-created skill.
_SEED_SKILLS = {"weekly-report", "expense-tracker", "data-fetch", "image-generation"}


def _new_skill_dirs(ws: Path) -> set:
    """Skill directories created beyond the seeded set."""
    skills_dir = ws / "skills"
    if not skills_dir.exists():
        return set()
    return {p.name for p in skills_dir.iterdir() if p.is_dir()} - _SEED_SKILLS


# ---------------------------------------------------------------------------
# Runner (stub mode)
# ---------------------------------------------------------------------------
def run_stub():
    from agent.evolution.executor import run_evolution_for_session
    from agent.evolution import backup as backup_mod
    from config import conf
    # Evolution is disabled by default now; enable for the test.
    conf()["self_evolution_enabled"] = True

    passed, failed = 0, 0
    for make in SCENARIOS:
        sc = make()
        ws = _setup_workspace()
        try:
            _point_config_at(ws)
            # Patch channel push to capture instead of send.
            channel = FakeChannel()
            import agent.evolution.executor as ex
            orig_notify = ex._notify_user
            ex._notify_user = lambda ct, rcv, summary: channel.send(
                type("R", (), {"content": summary})(),
                {"receiver": rcv},
            )

            agent = FakeAgent(_make_messages(sc["turns"]))
            bridge = FakeAgentBridge(agent, sc["scripted"], on_edit=sc["on_edit"])

            evolved = run_evolution_for_session(
                bridge, "session_test", channel_type="web", receiver="user_42"
            )

            ok = True
            errs = []

            if evolved != sc["expect_evolved"]:
                ok = False
                errs.append(f"evolved={evolved}, expected {sc['expect_evolved']}")

            if sc["expect_evolved"]:
                # memory / skill content checks
                if "expect_memory_contains" in sc:
                    # Evolution now writes to the dated daily file, not MEMORY.md.
                    from datetime import datetime
                    daily = ws / "memory" / (datetime.now().strftime("%Y-%m-%d") + ".md")
                    mem = daily.read_text() if daily.exists() else ""
                    if sc["expect_memory_contains"] not in mem:
                        ok = False
                        errs.append("daily memory missing expected content")
                if "expect_skill_contains" in sc:
                    sk, txt = sc["expect_skill_contains"]
                    content = (ws / "skills" / sk / "SKILL.md").read_text()
                    if txt not in content:
                        ok = False
                        errs.append("skill missing expected content")
                if sc.get("expect_new_skill") and not _new_skill_dirs(ws):
                    ok = False
                    errs.append("expected a new skill to be created")
                # notify happened
                if not channel.sent:
                    ok = False
                    errs.append("no notification sent")
                # injection happened (undo support)
                if not bridge.injected or "[EVOLUTION]" not in bridge.injected[0]:
                    ok = False
                    errs.append("no [EVOLUTION] record injected")
                # protected skill untouched
                prot = (ws / "skills" / "image-generation" / "SKILL.md").read_text()
                if prot != "# Image Generation (built-in)\nDo not modify.\n":
                    ok = False
                    errs.append("PROTECTED skill was modified!")
                # backup exists (undo possible)
                backups = list((ws / "memory" / ".evolution_backups").glob("*"))
                if not backups:
                    ok = False
                    errs.append("no backup created")
            else:
                # SILENT: nothing should have changed / been sent
                if channel.sent:
                    ok = False
                    errs.append("notification sent on SILENT")
                if bridge.injected:
                    ok = False
                    errs.append("injected record on SILENT")
            if sc.get("expect_no_new_skill") and _new_skill_dirs(ws):
                ok = False
                errs.append(f"unexpected new skill created: {_new_skill_dirs(ws)}")

            ex._notify_user = orig_notify

            if ok:
                passed += 1
                print(f"  PASS  {sc['name']}")
            else:
                failed += 1
                print(f"  FAIL  {sc['name']}: {'; '.join(errs)}")
        finally:
            shutil.rmtree(ws, ignore_errors=True)

    # Undo verification (uses the memory scenario's backup path).
    print("\n-- undo tool --")
    _verify_undo()

    print(f"\nStub results: {passed} passed, {failed} failed")
    return failed == 0


def _verify_undo():
    from agent.evolution.backup import create_backup, restore_backup
    ws = _setup_workspace()
    try:
        _point_config_at(ws)
        mem = ws / "MEMORY.md"
        bid = create_backup(ws, [mem])
        mem.write_text("CORRUPTED", encoding="utf-8")
        from agent.tools.evolution_undo import EvolutionUndoTool
        r = EvolutionUndoTool().execute({"backup_id": bid})
        restored = mem.read_text()
        if r.status == "success" and "David" in restored:
            print("  PASS  undo restores pre-evolution state")
        else:
            print(f"  FAIL  undo: status={r.status}, content={restored[:40]}")
    finally:
        shutil.rmtree(ws, ignore_errors=True)


# ---------------------------------------------------------------------------
# Runner (real mode) — minimal: just prints the model's decision per scenario.
# ---------------------------------------------------------------------------
def _snapshot_ws(ws: Path) -> dict:
    """Map every text file under the workspace -> content (skip backups dir)."""
    snap = {}
    for p in ws.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(ws))
        if rel.startswith("memory/.evolution_backups"):
            continue
        try:
            snap[rel] = p.read_text(encoding="utf-8")
        except Exception:
            pass
    return snap


def _print_diff(before: dict, after: dict) -> bool:
    """Print added/changed files. Returns True if anything changed."""
    changed = False
    keys = sorted(set(before) | set(after))
    for rel in keys:
        old = before.get(rel)
        new = after.get(rel)
        if old == new:
            continue
        changed = True
        tag = "NEW FILE" if old is None else "CHANGED"
        print(f"      ~ {rel} [{tag}]")
        old_lines = set((old or "").splitlines())
        for line in (new or "").splitlines():
            if line not in old_lines:
                print(f"          + {line}")
    return changed


def run_real():
    """Run real model evolution on each scenario and print the actual output.

    Uses config.json's configured model via a real AgentBridge, so you see
    exactly what the model decides and writes for each conversation.
    """
    from bridge.bridge import Bridge
    from agent.memory.config import (
        MemoryConfig,
        set_global_memory_config,
        get_default_memory_config,
    )
    from config import conf, load_config

    # Load config.json so real API keys are available to the bots.
    load_config()

    # Default the test to deepseek-v4-flash (fast, low cost) unless overridden.
    override_model = os.environ.get("EVO_TEST_MODEL", "deepseek-v4-flash")
    conf()["model"] = override_model
    conf()["bot_type"] = os.environ.get("EVO_TEST_BOT_TYPE", "deepseek")
    # Force-enable evolution for the test regardless of config.json default.
    conf()["self_evolution_enabled"] = True
    print(f"[test] model: {override_model} (bot_type={conf().get('bot_type')}, "
          f"key={'set' if conf().get('deepseek_api_key') else 'MISSING'})")

    from agent.memory.manager import MemoryManager
    import agent.evolution.executor as ex

    bridge = Bridge()
    agent_bridge = bridge.get_agent_bridge()

    # Capture the user-facing reply instead of pushing it to a channel.
    captured = {"reply": None}
    orig_notify = ex._notify_user
    ex._notify_user = lambda ct, rcv, summary: captured.__setitem__("reply", summary)

    results = []  # (name, goal, evolved, changed, reply_ok)

    only = os.environ.get("EVO_TEST_ONLY")  # substring filter on goal/name
    try:
        for make in SCENARIOS:
            sc = make()
            if only and only not in sc["goal"] and only not in sc["name"]:
                continue
            ws = _setup_workspace()
            captured["reply"] = None
            try:
                mem_cfg = MemoryConfig(workspace_root=str(ws))
                set_global_memory_config(mem_cfg)

                sid = "session_evo_real"
                # Fully isolated agent: tool cwd + memory_manager -> temp ws.
                iso_mem = MemoryManager(mem_cfg)
                agent = agent_bridge.create_agent(
                    system_prompt="You are a helpful assistant.",
                    tools=None,
                    workspace_dir=str(ws),
                    memory_manager=iso_mem,
                    enable_skills=False,
                )
                # Notify path needs a channel+receiver to fire; give dummies.
                agent_bridge.agents[sid] = agent
                with agent.messages_lock:
                    agent.messages.clear()
                    agent.messages.extend(_make_messages(sc["turns"]))

                before = _snapshot_ws(ws)

                print("\n" + "=" * 72)
                print(f"Scenario: {sc['name']}   [goal: {sc['goal']}]")
                print("-" * 72)
                print("[Conversation]")
                for u, a in sc["turns"]:
                    print(f"   User: {u}")
                    print(f"   Assistant: {a}")

                from agent.evolution.executor import run_evolution_for_session
                evolved = run_evolution_for_session(
                    agent_bridge, sid, channel_type="web", receiver="tester"
                )

                after = _snapshot_ws(ws)
                print("\n[Evolution result] evolved =", evolved)
                changed = False
                if evolved:
                    changed = _print_diff(before, after)
                    if not changed:
                        print("      (no file changes)")
                else:
                    print("      (silent, nothing changed)")

                new_skills = _new_skill_dirs(ws)
                if new_skills:
                    print(f"      New skills: {', '.join(sorted(new_skills))}")
                # Surface mismatches against the scenario's skill expectation.
                if sc.get("expect_new_skill") and not new_skills:
                    print("      Warning: expected a new skill, but none was created")
                if sc.get("expect_no_new_skill") and new_skills:
                    print("      Warning: a new skill was created, but should not have been")

                print("\n[Reply to the user]")
                if captured["reply"]:
                    for line in captured["reply"].splitlines():
                        print(f"   {line}")
                else:
                    print("   (no notification)")

                reply_ok = bool(captured["reply"]) == bool(evolved)
                results.append((sc["name"], sc["goal"], evolved, changed, reply_ok))
                agent_bridge.agents.pop(sid, None)
            finally:
                shutil.rmtree(ws, ignore_errors=True)
    finally:
        ex._notify_user = orig_notify

    # Summary table.
    print("\n" + "=" * 72)
    print("Summary (deepseek-v4-flash live run)")
    print("-" * 72)
    for name, goal, evolved, changed, reply_ok in results:
        exp = "silent" if goal == "none" else "should evolve"
        got = "evolved" if evolved else "silent"
        mark = "✓" if (goal == "none") != evolved else "✗"
        print(f"  {mark}  {name:42s} expected={exp} actual={got}")


if __name__ == "__main__":
    if "--debug" in sys.argv:
        import logging
        from common.log import logger as _cow_logger
        _cow_logger.setLevel(logging.DEBUG)
        for _h in _cow_logger.handlers:
            _h.setLevel(logging.DEBUG)
    if "--real" in sys.argv:
        run_real()
    else:
        ok = run_stub()
        sys.exit(0 if ok else 1)
