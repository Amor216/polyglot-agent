import os
from collections.abc import Iterator

import anthropic

from . import audit
from .pricing import format_usage
from .tools import ToolRegistry

DEFAULT_MODEL = os.environ.get("POLYGLOT_MODEL", "claude-sonnet-4-5")

SYSTEM_PROMPT = """You are a terminal-resident assistant with access to system and browser tools.

Rules:
- Prefer tools over guessing. Read files, list dirs, query the browser instead of inventing answers.
- Chain tools when needed. Multi-step tasks are normal.
- Be terse. The user is in a terminal, not reading prose.
- Surface errors verbatim. Do not invent retries.
- If a command is blocked or needs confirmation, explain why in one line.
"""


class ToolLoopExhausted(RuntimeError):
    pass


class Agent:
    def __init__(self, tools: ToolRegistry, model: str = DEFAULT_MODEL, max_steps: int = 12):
        self.client = anthropic.Anthropic()
        self.tools = tools
        self.model = model
        self.max_steps = max_steps
        self.messages: list[dict] = []
        self.total_in = 0
        self.total_out = 0

    def reset(self) -> None:
        self.messages = []
        self.total_in = 0
        self.total_out = 0

    def chat(self, user_input: str) -> Iterator[str]:
        self.messages.append({"role": "user", "content": user_input})
        tool_calls = 0

        for _ in range(self.max_steps):
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=self.tools.schemas(),
                messages=self.messages,
            ) as stream:
                yield from stream.text_stream
                resp = stream.get_final_message()

            self.total_in += resp.usage.input_tokens
            self.total_out += resp.usage.output_tokens
            self.messages.append({"role": "assistant", "content": [_serialize(b) for b in resp.content]})

            if resp.stop_reason != "tool_use":
                yield f"\n[dim]{format_usage(self.model, self.total_in, self.total_out, tool_calls)}[/dim]\n"
                return

            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                tool_calls += 1
                yield f"\n  → {block.name}({_brief(block.input)})\n"
                result, is_error = self._run(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                    "is_error": is_error,
                })

            self.messages.append({"role": "user", "content": tool_results})

        raise ToolLoopExhausted(f"tool loop exceeded {self.max_steps} steps")

    def _run(self, name: str, args: dict) -> tuple[str, bool]:
        try:
            out = self.tools.call(name, args)
            audit.record(name, args, "ok")
            return out, False
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            audit.record(name, args, "error", error=msg)
            return msg, True


def _serialize(block) -> dict:
    """Strip SDK-internal fields (parsed_output, etc.) that the API rejects on resend."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return block.model_dump()


def _brief(d: dict) -> str:
    parts = []
    for k, v in d.items():
        s = str(v)
        if len(s) > 60:
            s = s[:57] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
