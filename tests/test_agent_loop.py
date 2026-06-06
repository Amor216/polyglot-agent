from types import SimpleNamespace
from unittest.mock import MagicMock

from polyglot.agent import Agent
from polyglot.tools import ToolRegistry
from polyglot.tools.base import Tool


def _block_dump(b):
    out = {"type": b.type}
    for k in ("text", "id", "name", "input"):
        if hasattr(b, k):
            out[k] = getattr(b, k)
    return out


def _text(t):
    b = SimpleNamespace(type="text", text=t)
    b.model_dump = lambda b=b: _block_dump(b)
    return b


def _use(tid, name, inp):
    b = SimpleNamespace(type="tool_use", id=tid, name=name, input=inp)
    b.model_dump = lambda b=b: _block_dump(b)
    return b


def _final(content, stop_reason, usage=(10, 5)):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1]),
    )


class _FakeStream:
    def __init__(self, final_msg):
        self._final = final_msg
        self.text_stream = iter(b.text for b in final_msg.content if b.type == "text" and b.text)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self._final


def _client_with(*finals):
    c = MagicMock()
    c.messages.stream.side_effect = [_FakeStream(f) for f in finals]
    return c


def _registry_with_echo():
    r = ToolRegistry()
    r.register(Tool(
        name="echo",
        description="returns input",
        input_schema={"type": "object", "properties": {"v": {"type": "string"}}, "required": ["v"]},
        handler=lambda a: a["v"],
    ))
    return r


def test_no_tool_use_returns_text():
    agent = Agent(_registry_with_echo())
    agent.client = _client_with(_final([_text("done.")], "end_turn"))
    out = "".join(agent.chat("hi"))
    assert "done." in out
    assert "tool" not in out  # no tool_call indicator
    assert agent.total_in == 10
    assert agent.total_out == 5


def test_tool_use_then_text():
    agent = Agent(_registry_with_echo())
    agent.client = _client_with(
        _final([_use("u1", "echo", {"v": "hello"})], "tool_use"),
        _final([_text("got hello")], "end_turn"),
    )
    out = "".join(agent.chat("say hi"))
    assert "got hello" in out
    assert "[echo]" in out
    assert agent.total_in == 20  # both calls summed
    assert agent.client.messages.stream.call_count == 2


def test_unknown_tool_returns_error_to_model():
    agent = Agent(_registry_with_echo())
    agent.client = _client_with(
        _final([_use("u1", "missing", {})], "tool_use"),
        _final([_text("ok")], "end_turn"),
    )
    list(agent.chat("x"))
    tool_result_msgs = [m for m in agent.messages
                        if m["role"] == "user" and isinstance(m["content"], list)
                        and any(isinstance(c, dict) and c.get("type") == "tool_result" for c in m["content"])]
    assert tool_result_msgs
    assert tool_result_msgs[0]["content"][0]["is_error"] is True


def test_usage_summary_emitted_at_end():
    agent = Agent(_registry_with_echo())
    agent.client = _client_with(_final([_text("hi")], "end_turn", usage=(100, 200)))
    out = "".join(agent.chat("x"))
    assert "100 in" in out
    assert "200 out" in out
    assert "$" in out
