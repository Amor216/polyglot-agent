from typing import Literal

SAFE_PREFIXES = (
    "ls", "dir", "cat", "type", "head", "tail",
    "grep", "findstr", "find", "echo", "pwd", "cd",
    "wc", "git status", "git log", "git diff", "git branch",
    "python", "py", "node", "npm", "pnpm", "uv",
    "where", "which",
)

DESTRUCTIVE = (
    "rm", "del", "rmdir", "rd", "mv", "move",
    "format", "dd", "mkfs",
    "git push", "git reset --hard", "git clean -f",
    "shutdown", "reboot", "halt", "poweroff",
    "kill", "taskkill",
    "chmod -r", "chown -r",
)

Classification = Literal["safe", "destructive", "blocked"]


def classify(
    cmd: str,
    extra_allowed: tuple[str, ...] = (),
    extra_blocked: tuple[str, ...] = (),
) -> Classification:
    norm = cmd.strip().lower()
    if not norm:
        return "blocked"
    for b in extra_blocked:
        if norm.startswith(b.lower()):
            return "blocked"
    for d in DESTRUCTIVE:
        if norm.startswith(d):
            return "destructive"
    for s in (*SAFE_PREFIXES, *extra_allowed):
        if norm.startswith(s.lower()):
            return "safe"
    return "blocked"
