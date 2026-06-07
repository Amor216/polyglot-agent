from pathlib import Path

from polyglot.config import Config, load


def test_default_config_enables_everything():
    c = Config()
    assert c.is_tool_enabled("read_file") is True
    assert c.is_tool_enabled("anything") is True


def test_enabled_whitelist_excludes_others():
    c = Config(enabled_tools={"read_file", "list_dir"})
    assert c.is_tool_enabled("read_file") is True
    assert c.is_tool_enabled("run_command") is False


def test_disabled_wins_over_enabled():
    c = Config(enabled_tools={"run_command"}, disabled_tools={"run_command"})
    assert c.is_tool_enabled("run_command") is False


def test_load_missing_file_returns_default(tmp_path: Path):
    c = load(tmp_path / "absent.toml")
    assert c.enabled_tools is None
    assert c.disabled_tools == set()


def test_load_parses_tools_and_commands(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text(
        '[tools]\n'
        'enabled = ["read_file", "list_dir"]\n'
        'disabled = ["browser_navigate"]\n'
        '\n'
        '[commands]\n'
        'allowed = ["docker ps"]\n'
        'blocked = ["sudo"]\n',
        encoding="utf-8",
    )
    c = load(p)
    assert c.enabled_tools == {"read_file", "list_dir"}
    assert c.disabled_tools == {"browser_navigate"}
    assert c.extra_allowed_commands == ("docker ps",)
    assert c.extra_blocked_commands == ("sudo",)


def test_env_override(monkeypatch, tmp_path: Path):
    p = tmp_path / "alt.toml"
    p.write_text('[tools]\ndisabled = ["x"]\n', encoding="utf-8")
    monkeypatch.setenv("POLYGLOT_CONFIG", str(p))
    c = load()
    assert c.disabled_tools == {"x"}
