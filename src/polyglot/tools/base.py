from collections.abc import Callable
from dataclasses import dataclass, field


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
