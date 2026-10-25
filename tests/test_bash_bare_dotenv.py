import sys
from agent.tools.bash.bash import Bash

def test_bare_dotenv_key_does_not_break_native_shell(tmp_path, monkeypatch):
    home = tmp_path / "home"
    folder = home / ".maia"
    folder.mkdir(parents=True)
    (folder / ".env").write_text("MAIA_BARE_KEY\nMAIA_EMPTY_KEY=\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("MAIA_BARE_KEY", "inherited")
    monkeypatch.setenv("MAIA_EMPTY_KEY", "old")
    command = f"{sys.executable} -c \"import os; print(os.environ['MAIA_BARE_KEY'] + ':' + os.environ['MAIA_EMPTY_KEY'])\""
    result = Bash({"cwd": str(tmp_path)}).execute({"command": command})
    assert result.status == "success", result.result
    assert "inherited:" in result.result["output"]
    assert "old" not in result.result["output"]
