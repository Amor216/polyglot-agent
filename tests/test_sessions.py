import json
from pathlib import Path

import pytest

from polyglot import sessions


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYGLOT_HOME", str(tmp_path))


def test_session_dir_respects_env(tmp_path: Path) -> None:
    assert sessions.session_dir() == tmp_path / "sessions"


def test_save_and_load_roundtrip() -> None:
    path = sessions.new_path()
    messages = [{"role": "user", "content": "hi"}]
    sessions.save(path, messages, total_in=10, total_out=20)
    snap = sessions.load(path)
    assert snap.messages == messages
    assert snap.total_in == 10
    assert snap.total_out == 20


def test_latest_returns_most_recent() -> None:
    older = sessions.new_path()
    sessions.save(older, [{"role": "user", "content": "old"}], 0, 0)
    import time as _t
    _t.sleep(0.01)
    newer = sessions.new_path()
    sessions.save(newer, [{"role": "user", "content": "new"}], 0, 0)
    assert sessions.latest() == newer


def test_latest_is_none_when_empty() -> None:
    assert sessions.latest() is None


def test_list_sessions_orders_newest_first() -> None:
    a = sessions.new_path()
    sessions.save(a, [{"role": "user", "content": "a"}], 0, 0)
    import time as _t
    _t.sleep(0.01)
    b = sessions.new_path()
    sessions.save(b, [{"role": "user", "content": "b"}], 0, 0)
    snaps = sessions.list_sessions(limit=10)
    assert [s.path for s in snaps] == [b, a]


def test_save_writes_valid_json() -> None:
    path = sessions.new_path()
    sessions.save(path, [{"role": "user", "content": "x"}], 1, 2)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total_in"] == 1
    assert data["total_out"] == 2
