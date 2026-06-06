import json
import os
import time
from pathlib import Path


def _log_path() -> Path:
    base = os.environ.get("POLYGLOT_AUDIT_DIR") or str(Path.home() / ".polyglot")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p / "audit.log"


def record(tool: str, args: dict, outcome: str, error: str | None = None) -> None:
    entry = {
        "ts": time.time(),
        "tool": tool,
        "args": args,
        "outcome": outcome,
    }
    if error:
        entry["error"] = error
    with _log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
