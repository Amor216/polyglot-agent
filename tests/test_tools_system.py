from pathlib import Path

from polyglot.tools import ToolRegistry
from polyglot.tools.system import register_system_tools


def _reg():
    r = ToolRegistry()
    register_system_tools(r, yolo=True)
    return r


def test_read_and_list(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    r = _reg()
    out = r.call("read_file", {"path": str(tmp_path / "a.txt")})
    assert out == "hello"
    listing = r.call("list_dir", {"path": str(tmp_path)})
    assert "a.txt" in listing
    assert "sub" in listing


def test_list_glob(tmp_path: Path):
    (tmp_path / "x.py").write_text("")
    (tmp_path / "y.md").write_text("")
    r = _reg()
    listing = r.call("list_dir", {"path": str(tmp_path), "pattern": "*.py"})
    assert "x.py" in listing
    assert "y.md" not in listing


def test_read_missing(tmp_path: Path):
    r = _reg()
    out = r.call("read_file", {"path": str(tmp_path / "nope")})
    assert "not found" in out


def test_run_blocked():
    r = _reg()
    out = r.call("run_command", {"cmd": "curl http://example.com"})
    assert "blocked" in out


def test_run_safe():
    r = _reg()
    out = r.call("run_command", {"cmd": "echo hello"})
    assert "exit=0" in out
    assert "hello" in out
