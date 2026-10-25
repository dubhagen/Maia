# Architecture

Maia is an out-of-the-box super AI assistant and a complete Agent harness framework, featuring complex task planning, long-term memory, skill extensibility, self-evolution, and multi-agent collaboration.

## System Architecture

A request enters from the web console or the local terminal, crosses one bridge, and leaves as a LiteLLM call. The model id is not rewritten. Local tools run only when you turn them on.

![Request path from the web console and terminal through the bridge to one LiteLLM endpoint](../images/architecture.svg)

The rest of the process is the modules around that path:

| Module | Description |
| --- | --- |
| **Plan** | Understands user intent, decomposes complex tasks into multi-step plans, and iteratively invokes tools until the goal is achieved |
| **Memory** | Automatically persists important information as core memory and daily memory, with hybrid keyword and vector retrieval for cross-session context continuity |
| **Knowledge** | Organizes structured knowledge by topic. The Agent autonomously distills valuable information into Markdown pages, maintaining indexes and cross-references to build a growing knowledge network |
| **Evolution** | Reviews a conversation in an isolated environment after it goes idle, improving skills, following up on unfinished tasks, and backfilling memory and knowledge so the Agent keeps growing through everyday use |
| **Multi-agent** | Multiple Agents form a team, each with its own responsibilities, model, and workspace. They can share a group chat, delegate tasks, and run sub-agents. |
| **Tools** | Core capability for Agent to access OS resources. 10+ built-in tools including file read/write, terminal, browser, scheduler, memory search, web search, and more |
| **Skills** | Loads skills shipped with Maia and skills in the workspace. Install from a git URL or a local path. There is no hosted catalog. |
| **Models** | One LiteLLM endpoint. The model id is passed through unchanged. An empty id turns embeddings, vision, images, speech-to-text, or speech synthesis off. |
| **Channels** | Web console and the local terminal. |
| **CLI** | Command-line system providing terminal commands (`maia`) and chat commands (`/`) for process management, skill installation, configuration, knowledge base management, and more |

## Agent Mode Workflow

When Agent mode is enabled, Maia runs as an autonomous agent with the following workflow:

1. **Receive Message** — Receive user input through channels
2. **Understand Intent** — Analyze task requirements and context
3. **Plan Task** — Break complex tasks into multiple steps
4. **Invoke Tools** — Select and execute appropriate tools for each step
5. **Update Memory & Knowledge** — Store important information in long-term memory and organize structured knowledge into the knowledge base
6. **Return Result** — Send execution results back to the user

## Workspace {#workspace}

### System Workspace {#system-workspace}

The Agent's system workspace is located at `~/maia` by default and stores system prompts, memory files, and skill files:

```
~/maia/
├── SYSTEM.md          # Agent system prompt
├── USER.md            # User profile
├── MEMORY.md          # Core memory
├── memory/            # Long-term memory storage
│   └── YYYY-MM-DD.md  # Daily memory
├── knowledge/         # Personal knowledge base
│   ├── index.md       # Knowledge index
│   └── <category>/    # Topic-based pages
├── skills/            # Custom skills
│   ├── skill-1/
│   └── skill-2/
└── agents/            # Multi-agent team
    ├── team.json      # Team roster & channel bindings
    └── <agent-id>/    # Non-default agent's own workspace
```

Secret keys are stored separately in `~/.maia` directory for security:

```
~/.maia/
└── .env               # Secret keys for skills
```

### Project Workspace {#project-workspace}

Besides the default workspace, each session can be bound to its own **project directory**. The Agent's file reads/writes and command execution happen inside that directory, giving you multi-project isolation; memory, skills, and the like still live in the default workspace. When more than one project is in use, the Web/desktop history list automatically groups sessions by project.

### Multi-Agent Workspace {#multi-agent-workspace}

Once you build an [Agent team](../multi-agent/team.md), each Agent has a complete workspace of its own. The default Agent uses the instance root `~/maia`, while every other member lives under `~/maia/agents/<agent-id>/`. This splits storage into three categories — system-shared, per-member isolated, and optionally shared:

- **System-shared**: the secrets file (`~/.maia/.env`) and the team config (`~/maia/agents/team.json`) are shared across the whole instance.
- **Per-member isolated**: each Agent's core files (`SYSTEM.md`, `USER.md`, `AGENT.md`, `RULE.md`), memory (`MEMORY.md`, `memory/`), and output files live inside its own workspace and are not visible to other members.
- **Optionally shared**: skills and the knowledge base can either be shared with the team or dedicated to a specific member, and the two modes can be switched at any time.

> A sub-Agent is a temporary execution unit spun up by the lead Agent; it shares the lead Agent's workspace and has no memory of its own. A team member is a persistent, full Agent with a completely independent workspace and memory. See [Sub-Agents](../multi-agent/subagent.md) for details.

### Per-Session Model & Permission {#session-settings}

Workspace, model, and permission can all be **set per session**, falling back to the global default when unset:

- **Model**: different sessions can switch to different models, making it easy to pick the right one per task.
- **Permission**: controls what the Agent is allowed to do, in three levels — **read-only**, **workspace-write**, and **full-access**. You can set a global default (`agent_permission_mode`) in the config; new sessions inherit it and can be adjusted individually as needed. Permissions reduce the risk of accidental changes; for strong isolation, run inside a container.

## Core Configuration

Configure Agent mode parameters in `config.json`:

```json
{
  "agent": true,
  "agent_workspace": "~/maia",
  "agent_max_context_tokens": 200000,
  "agent_max_context_turns": 30,
  "agent_max_steps": 100,
  "agent_permission_mode": "workspace-write",
  "enable_thinking": false,
  "maia_lang": "auto"
}
```

| Parameter | Description | Default |
| --- | --- | --- |
| `agent` | Enable Agent mode | `true` |
| `agent_workspace` | Workspace path | `~/maia` |
| `agent_max_context_tokens` | Max context tokens | `200000` |
| `agent_max_context_turns` | Max context turns | `30` |
| `agent_max_steps` | Max decision steps per task | `100` |
| `agent_permission_mode` | Global default permission inherited by new sessions: `read-only` / `workspace-write` / `full-access` | `workspace-write` |
| `enable_thinking` | Enable deep-thinking mode | `false` |
| `knowledge` | Enable personal knowledge base | `true` |
| `self_evolution_enabled` | Enable Self-Evolution. New installs leave it off | `false` |
| `maia_lang` | UI language. English is the only language; `auto` stays English | `auto` |
