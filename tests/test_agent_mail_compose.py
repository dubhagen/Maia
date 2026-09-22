from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_mail_overlay_persists_the_runtime_and_wraps_the_base_entrypoint():
    """Removing any mount or entrypoint override would lose the opt-in runtime."""
    overlay = (ROOT / "docker/docker-compose.agent-mail.yml").read_text()
    base_compose = (ROOT / "docker/docker-compose.yml").read_text()

    assert "chatgpt-on-wechat:" in overlay
    assert "image: zhayujie/chatgpt-on-wechat" in base_compose
    assert "user: root" in overlay
    assert "./cow-data/agent-mail/config:/home/agent/.agently-cli" in overlay
    assert "./cow-data/agent-mail/share:/home/agent/.local/share/agently-cli" in overlay
    assert "./cow-data/agent-mail/npm-global:/home/agent/.npm-global" in overlay
    assert (
        "./docker/agent-mail/entrypoint.sh:"
        "/docker-entrypoint-init.d/agent-mail-entrypoint.sh:ro" in overlay
    )
    assert (
        'entrypoint: ["/bin/bash", '
        '"/docker-entrypoint-init.d/agent-mail-entrypoint.sh"]' in overlay
    )


def test_agent_mail_initializer_installs_a_pinned_cli_without_interactive_setup():
    """A missing runtime must trigger the pinned install, never an interactive login."""
    wrapper = (ROOT / "docker/agent-mail/entrypoint.sh").read_text()

    assert "set -eu" in wrapper
    assert "AGENTLY_CLI_VERSION=1.0.18" in wrapper
    assert 'PATH="$NPM_GLOBAL_PREFIX/bin:$PATH"' in wrapper
    assert 'command -v node' in wrapper
    assert '"$NPM_GLOBAL_PREFIX/bin/agently-cli"' in wrapper
    assert "nodesource.com/setup_20.x" in wrapper
    assert (
        'npm install --global --prefix "$NPM_GLOBAL_PREFIX" '
        '"@tencent-qqmail/agently-cli@${AGENTLY_CLI_VERSION}"' in wrapper
    )
    assert "auth login" not in wrapper
    assert "skills add" not in wrapper
    assert "exec /entrypoint.sh" in wrapper


def test_agent_mail_guide_keeps_authentication_as_a_user_run_step():
    """The guide must expose opt-in startup and explicit post-start authentication."""
    guide = (ROOT / "docs/guide/agent-mail.mdx").read_text()

    assert (
        "docker compose -f docker/docker-compose.yml "
        "-f docker/docker-compose.agent-mail.yml up -d" in guide
    )
    assert "docker compose exec -u agent chatgpt-on-wechat agently-cli auth login" in guide
    assert (
        "docker compose exec -u agent chatgpt-on-wechat "
        "npx -y skills add https://agent.qq.com --skill -g -y" in guide
    )
    assert "./cow-data/agent-mail/" in guide
    assert "optional" in guide.lower()
    assert "default" in guide.lower()
