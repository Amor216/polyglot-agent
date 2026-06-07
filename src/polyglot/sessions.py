import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionSnapshot:
    path: Path
    saved_at: float
    messages: list[dict]
    total_in: int
    total_out: int


def session_dir() -> Path:
    root = os.environ.get("POLYGLOT_HOME")
    if root:
        return Path(root) / "sessions"
    return Path.home() / ".polyglot" / "sessions"


def new_path() -> Path:
    d = session_dir()
    d.mkdir(parents=True, exist_ok=True)
    now = time.time()
    stamp = time.strftime("%Y%m%dT%H%M%S", time.localtime(now))
    millis = int((now - int(now)) * 1000)
    return d / f"{stamp}_{millis:03d}.json"


def save(path: Path, messages: list[dict], total_in: int, total_out: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": time.time(),
        "total_in": total_in,
        "total_out": total_out,
        "messages": messages,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load(path: Path) -> SessionSnapshot:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SessionSnapshot(
        path=path,
        saved_at=payload.get("saved_at", path.stat().st_mtime),
        messages=payload.get("messages", []),
        total_in=payload.get("total_in", 0),
        total_out=payload.get("total_out", 0),
    )


def latest() -> Path | None:
    d = session_dir()
    if not d.exists():
        return None
    candidates = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def list_sessions(limit: int = 10) -> list[SessionSnapshot]:
    d = session_dir()
    if not d.exists():
        return []
    paths = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [load(p) for p in paths[:limit]]
