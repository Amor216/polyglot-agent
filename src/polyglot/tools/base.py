from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str]

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self.tools.values()]

    def call(self, name: str, args: dict) -> str:
        if name not in self.tools:
            raise KeyError(f"unknown tool: {name}")
        return self.tools[name].handler(args)

    def names(self) -> list[str]:
        return list(self.tools.keys())


def text_tool(name: str, description: str, schema: dict) -> Callable:
    def decorator(fn: Callable[[dict], Any]) -> Tool:
        def handler(args: dict) -> str:
            out = fn(args)
            return out if isinstance(out, str) else str(out)
        return Tool(name=name, description=description, input_schema=schema, handler=handler)
    return decorator
