import fnmatch
import os
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from ..safety import classify
from .base import Tool, ToolRegistry

MAX_READ_BYTES = 200_000
MAX_OUTPUT_CHARS = 8000
DEFAULT_TIMEOUT = 30


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _read_file(args: dict) -> str:
    p = _resolve(args["path"])
    if not p.exists():
        return f"not found: {p}"
    if not p.is_file():
        return f"not a file: {p}"
    data = p.read_bytes()[:MAX_READ_BYTES]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _list_dir(args: dict) -> str:
    p = _resolve(args["path"])
    if not p.exists():
        return f"not found: {p}"
    if not p.is_dir():
        return f"not a directory: {p}"
    pattern = args.get("pattern")
    rows = []
    entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    for e in entries:
        if pattern and not fnmatch.fnmatch(e.name, pattern):
            continue
        try:
            st = e.stat()
            kind = "d" if e.is_dir() else "f"
            mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            size = "-" if e.is_dir() else _human_size(st.st_size)
            rows.append(f"{kind} {size:>8}  {mtime}  {e.name}")
        except OSError:
            continue
    if not rows:
        return "(empty)"
    return "\n".join(rows)


def _human_size(n: int) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.0f}P"


def _make_run(yolo: bool):
    def run(args: dict) -> str:
        cmd = args["cmd"]
        cwd = args.get("cwd") or "."
        cls = classify(cmd)
        if cls == "blocked":
            return f"blocked by allowlist: {cmd!r}. add it to SAFE_PREFIXES if intended."
        if cls == "destructive" and not yolo:
            if not _confirm_destructive(cmd):
                return f"user declined: {cmd!r}"
        try:
            out = subprocess.run(
                cmd,
                shell=True,
                cwd=str(_resolve(cwd)),
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return f"timeout after {DEFAULT_TIMEOUT}s"
        combined = (out.stdout or "") + (out.stderr or "")
        if len(combined) > MAX_OUTPUT_CHARS:
            combined = combined[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
        return f"exit={out.returncode}\n{combined}"
    return run


def _confirm_destructive(cmd: str) -> bool:
    sys.stderr.write(f"\n[confirm] run destructive command: {cmd}\n[y/N] ")
    sys.stderr.flush()
    try:
        ans = input().strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def _open_app(args: dict) -> str:
    target = args["target"]
    if target.startswith(("http://", "https://")):
        webbrowser.open(target)
        return f"opened url: {target}"
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
        return f"opened: {target}"
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, target])
    return f"opened: {target}"


def register_system_tools(reg: ToolRegistry, yolo: bool = False) -> None:
    reg.register(Tool(
        name="read_file",
        description="Read text content of a file. Returns up to 200KB.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        handler=_read_file,
    ))
    reg.register(Tool(
        name="list_dir",
        description="List entries of a directory. Non-recursive. Optional glob pattern.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "pattern": {"type": "string", "description": "Optional glob, e.g. *.py"},
            },
            "required": ["path"],
        },
        handler=_list_dir,
    ))
    reg.register(Tool(
        name="run_command",
        description=(
            "Run a shell command. Subject to an allowlist; destructive commands "
            "require interactive confirmation unless yolo mode is on. Returns exit code and output."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "cmd": {"type": "string"},
                "cwd": {"type": "string", "description": "Working directory, defaults to ."},
            },
            "required": ["cmd"],
        },
        handler=_make_run(yolo=yolo),
    ))
    reg.register(Tool(
        name="open_app",
        description="Open an application, file, or URL via the OS default handler.",
        input_schema={
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": ["target"],
        },
        handler=_open_app,
    ))
