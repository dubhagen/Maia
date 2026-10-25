"""Multi-instance channel resolution and persistence.

Two worlds must coexist: a legacy install driven by ``channel_type`` + flat
credentials, and a multi-instance install driven by an explicit
``channel_instances`` list in the roster file. These tests pin the legacy
behavior (so it never regresses) and cover the new persistence helpers.
"""

from channel import channel_instances as ci


# ---------------------------------------------------------------------------
# instance id generation
# ---------------------------------------------------------------------------

def test_new_instance_id_has_type_prefix_and_is_unique():
    ids = set()
    for _ in range(50):
        new = ci.new_instance_id("web", ids)
        assert new.startswith("web-")
        assert new not in ids
        ids.add(new)


def test_new_instance_id_keeps_type_and_handles_empty():
    assert ci.new_instance_id("wx").startswith("wx-")
    assert ci.new_instance_id("").startswith("channel-")


def test_new_instance_id_avoids_taken():
    taken = {f"web-{i:010d}" for i in range(3)}
    assert ci.new_instance_id("web", taken) not in taken


# ---------------------------------------------------------------------------
# legacy compatibility: no channel_instances -> synthesized from channel_type
# ---------------------------------------------------------------------------

def test_legacy_channel_type_string(tmp_path):
    settings = {"agent_workspace": str(tmp_path), "channel_type": "web, terminal"}
    insts = ci.resolve_channel_instances(settings)
    ids = {i.instance_id for i in insts}
    assert ids == {"web", "terminal"}
    # legacy instances carry no per-instance credentials or binding
    for i in insts:
        assert i.legacy is True
        assert i.credentials == {}
        assert i.agent_id == ""


def test_legacy_channel_type_list(tmp_path):
    settings = {"agent_workspace": str(tmp_path), "channel_type": ["web"]}
    insts = ci.resolve_channel_instances(settings)
    assert [i.instance_id for i in insts] == ["web"]
    assert insts[0].legacy is True


def test_legacy_does_not_rename_unknown_types(tmp_path):
    settings = {"agent_workspace": str(tmp_path), "channel_type": "wx"}
    insts = ci.resolve_channel_instances(settings)
    assert insts[0].channel_type == "wx"


# ---------------------------------------------------------------------------
# explicit multi-instance resolution
# ---------------------------------------------------------------------------

def _write_instances(tmp_path, records):
    """Persist records to team.json and return settings with them overlaid.

    Mirrors how the launcher reads channels: team.resolve() lifts the roster
    file (where channel_instances lives) onto the flat settings before
    resolve_channel_instances() runs.
    """
    from agent import team

    base = {"agent_workspace": str(tmp_path)}
    team.write(base, {"channel_instances": records})
    return team.resolve(base)


def test_explicit_instances_win_over_legacy(tmp_path):
    settings = _write_instances(
        tmp_path,
        [
            {
                "instance_id": "web-a",
                "channel_type": "web",
                "agent_id": "default",
                "credentials": {"web_app_id": "A", "web_app_secret": "sa"},
            },
            {
                "instance_id": "web-b",
                "channel_type": "web",
                "agent_id": "ops",
                "credentials": {"web_app_id": "B", "web_app_secret": "sb"},
            },
        ],
    )
    settings["channel_type"] = "web"  # legacy field present but ignored
    insts = ci.resolve_channel_instances(settings)
    by_id = {i.instance_id: i for i in insts}
    assert set(by_id) == {"web-a", "web-b"}
    assert by_id["web-a"].agent_id == "default"
    assert by_id["web-b"].agent_id == "ops"
    assert by_id["web-a"].credentials == {}
    assert all(i.legacy is False for i in insts)


def test_explicit_only_known_credential_keys_kept(tmp_path):
    settings = _write_instances(
        tmp_path,
        [
            {
                "instance_id": "web-a",
                "channel_type": "web",
                "credentials": {"web_app_id": "A", "junk": "x"},
            }
        ],
    )
    inst = ci.resolve_channel_instances(settings)[0]
    assert inst.credentials == {}


# ---------------------------------------------------------------------------
# persistence helpers: upsert / update / remove
# ---------------------------------------------------------------------------

def test_upsert_creates_with_generated_id(tmp_path):
    settings = {"agent_workspace": str(tmp_path)}
    inst = ci.upsert_instance(
        settings,
        channel_type="web",
        agent_id="agent-x",
        credentials={"web_app_id": "A", "web_app_secret": "B", "junk": "no"},
    )
    assert inst.instance_id.startswith("web-")
    assert inst.agent_id == "agent-x"
    assert inst.credentials == {}
    assert ci.read_raw_instances(settings)[0]["instance_id"] == inst.instance_id


def test_upsert_partial_update_keeps_binding(tmp_path):
    settings = {"agent_workspace": str(tmp_path)}
    inst = ci.upsert_instance(
        settings, channel_type="web", agent_id="agent-x",
        credentials={"web_app_id": "A", "web_app_secret": "B"},
    )
    # update credentials only, without re-sending agent_id
    updated = ci.upsert_instance(
        settings, channel_type="web", instance_id=inst.instance_id,
        credentials={"web_app_secret": "B2"},
    )
    assert updated.agent_id == "agent-x"  # binding preserved
    assert updated.credentials == {}
    # exactly one record: it was updated, not duplicated
    assert len(ci.read_raw_instances(settings)) == 1


def test_upsert_honors_provided_id(tmp_path):
    settings = {"agent_workspace": str(tmp_path)}
    inst = ci.upsert_instance(
        settings, channel_type="web", instance_id="from-remote-123",
        agent_id="a", credentials={"web_app_id": "A"},
    )
    assert inst.instance_id == "from-remote-123"


# ---------------------------------------------------------------------------
# instance name: a user-editable friendly label, seeded with a default and
# fully optional so legacy records without one keep working.
# ---------------------------------------------------------------------------

def test_new_instance_gets_default_name(tmp_path):
    settings = {"agent_workspace": str(tmp_path)}
    first = ci.upsert_instance(settings, channel_type="terminal", credentials={})
    second = ci.upsert_instance(settings, channel_type="terminal", credentials={})
    # First of a type is unnumbered; the second is suffixed so they read apart.
    assert first.name == "terminal"
    assert second.name == "terminal 2"


def test_upsert_can_set_and_clear_name(tmp_path):
    settings = {"agent_workspace": str(tmp_path)}
    inst = ci.upsert_instance(settings, channel_type="web",
                              credentials={"web_app_id": "A"})
    renamed = ci.upsert_instance(settings, channel_type="web",
                                 instance_id=inst.instance_id, name="Ops")
    assert renamed.name == "Ops"
    # Renaming must not disturb credentials or duplicate the record.
    assert renamed.credentials == {}
    assert len(ci.read_raw_instances(settings)) == 1
    # Empty name clears the label back to unset.
    cleared = ci.upsert_instance(settings, channel_type="web",
                                 instance_id=inst.instance_id, name="")
    assert cleared.name == ""


def test_upsert_partial_update_keeps_name(tmp_path):
    settings = {"agent_workspace": str(tmp_path)}
    inst = ci.upsert_instance(settings, channel_type="web", name="Support",
                              credentials={"web_app_id": "A"})
    # A credentials-only update (name=None) must preserve the existing label.
    updated = ci.upsert_instance(settings, channel_type="web",
                                 instance_id=inst.instance_id,
                                 credentials={"web_app_secret": "S"})
    assert updated.name == "Support"


def test_legacy_record_without_name_resolves(tmp_path):
    # A record written before the name field existed must still load, with an
    # empty name (the UI falls back to the id) and no error.
    settings = _write_instances(
        tmp_path,
        [{"instance_id": "web-old", "channel_type": "web",
          "credentials": {"web_app_id": "A"}}],
    )
    inst = ci.resolve_channel_instances(settings)[0]
    assert inst.name == ""
    assert inst.instance_id == "web-old"


def test_remove_instance(tmp_path):
    settings = {"agent_workspace": str(tmp_path)}
    inst = ci.upsert_instance(settings, channel_type="web",
                              credentials={"web_app_id": "A"})
    assert ci.remove_instance(settings, inst.instance_id) is True
    assert ci.read_raw_instances(settings) == []
    # removing a missing id is a no-op
    assert ci.remove_instance(settings, "nope") is False


# ---------------------------------------------------------------------------
# team members: a channel instance owns a roster (owner + teammates)
# ---------------------------------------------------------------------------

def test_explicit_instance_parses_members(tmp_path):
    settings = _write_instances(
        tmp_path,
        [
            {
                "instance_id": "web-team",
                "channel_type": "web",
                "agent_id": "leader",
                "members": ["ops", "research", "leader", "ops", ""],
                "credentials": {"web_app_id": "A"},
            }
        ],
    )
    inst = ci.resolve_channel_instances(settings)[0]
    # owner is never a member; duplicates and blanks are dropped; order kept
    assert inst.members == ["ops", "research"]


def test_upsert_sets_and_preserves_members(tmp_path):
    settings = {"agent_workspace": str(tmp_path)}
    inst = ci.upsert_instance(
        settings, channel_type="web", agent_id="leader",
        members=["ops", "leader", "research"],
        credentials={"web_app_id": "A"},
    )
    assert inst.members == ["ops", "research"]  # owner filtered out

    # a credentials-only update must not drop the team
    kept = ci.upsert_instance(
        settings, channel_type="web", instance_id=inst.instance_id,
        credentials={"web_app_secret": "S"},
    )
    assert kept.members == ["ops", "research"]

    # members=[] clears the team
    cleared = ci.upsert_instance(
        settings, channel_type="web", instance_id=inst.instance_id,
        members=[],
    )
    assert cleared.members == []
    assert "members" not in ci.read_raw_instances(settings)[0]


# ---------------------------------------------------------------------------
# bootstrap: unknown channel types are not folded into channel_instances
# ---------------------------------------------------------------------------

def test_bootstrap_does_not_adopt_an_unknown_channel(tmp_path):
    settings = {
        "agent_workspace": str(tmp_path),
        "channel_type": "extra",
        "extra_token": "tok",
    }
    assert ci.bootstrap_legacy_instances(settings, {}, "primary") == []


def test_bootstrap_keeps_an_existing_record(tmp_path):
    settings = {
        "agent_workspace": str(tmp_path),
        "channel_type": "extra",
        "extra_token": "tok",
    }
    roster = {
        "channel_instances": [
            {"instance_id": "terminal-a", "channel_type": "terminal", "agent_id": "ops"}
        ]
    }
    records = ci.bootstrap_legacy_instances(settings, roster, "primary")
    assert [r["instance_id"] for r in records] == ["terminal-a"]


def test_startup_does_not_add_an_unknown_channel(tmp_path):
    from agent import team

    settings = {"agent_workspace": str(tmp_path), "channel_type": ""}
    team.write(settings, {
        "default_agent_id": "primary",
        "agents": [],
        "channel_instances": [
            {"instance_id": "terminal-a", "channel_type": "terminal", "agent_id": "primary"}
        ],
    })
    settings["channel_type"] = "extra"
    settings["extra_token"] = "tok"
    assert team.adopt_legacy_channels(settings) is None
    records = team.read(settings)["channel_instances"]
    assert [r["instance_id"] for r in records] == ["terminal-a"]


def test_startup_leaves_the_roster_alone_when_nothing_is_missing(tmp_path):
    from agent import team

    settings = {"agent_workspace": str(tmp_path), "channel_type": "extra"}
    assert team.adopt_legacy_channels(settings) is None
    assert not team.team_file(settings).exists()

    path = team.team_file(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"channel_instances": [', encoding="utf-8")
    settings.update({"extra_token": "tok"})
    assert team.adopt_legacy_channels(settings) is None
    assert path.read_text(encoding="utf-8") == '{"channel_instances": ['


def test_write_does_not_copy_unknown_channel_secrets(tmp_path):
    """team.write must not copy flat credentials for an unknown channel."""
    from agent import team

    settings = {
        "agent_workspace": str(tmp_path),
        "channel_type": "extra",
        "extra_token": "SECRET",
        "default_agent_id": "primary",
    }
    team.write(settings, {"default_agent_id": "primary", "agents": []})
    assert team.read(settings).get("channel_instances") in (None, [])
    resolved = team.resolve(settings)
    insts = ci.resolve_channel_instances(resolved)
    assert all(i.credentials == {} for i in insts)
