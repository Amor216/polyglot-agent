import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    enabled_tools: set[str] | None = None
    disabled_tools: set[str] = field(default_factory=set)
    extra_allowed_commands: tuple[str, ...] = ()
    extra_blocked_commands: tuple[str, ...] = ()

    def is_tool_enabled(self, name: str) -> bool:
        if name in self.disabled_tools:
            return False
        if self.enabled_tools is None:
            return True
        return name in self.enabled_tools


def default_path() -> Path:
    override = os.environ.get("POLYGLOT_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".polyglot" / "config.toml"


def load(path: Path | None = None) -> Config:
    path = path or default_path()
    if not path.exists():
        return Config()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    tools = data.get("tools") or {}
    enabled = tools.get("enabled")
    disabled = tools.get("disabled") or []
    commands = data.get("commands") or {}
    return Config(
        enabled_tools=set(enabled) if isinstance(enabled, list) else None,
        disabled_tools=set(disabled),
        extra_allowed_commands=tuple(commands.get("allowed") or ()),
        extra_blocked_commands=tuple(commands.get("blocked") or ()),
    )
