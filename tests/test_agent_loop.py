from types import SimpleNamespace
from unittest.mock import MagicMock

from polyglot.agent import Agent
from polyglot.tools import ToolRegistry
from polyglot.tools.base import Tool


def _msg(content, stop_reason):
    for b in content:
        if "model_dump" not in dir(b):
            b.model_dump = lambda b=b: {"type": b.type, **{k: v for k, v in b.__dict__.items() if k != "type"}}
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _use(tid, name, inp):
    return SimpleNamespace(type="tool_use", id=tid, name=name, input=inp)


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
    agent.client = MagicMock()
    agent.client.messages.create.return_value = _msg([_text("done.")], stop_reason="end_turn")
    out = "".join(agent.chat("hi"))
    assert "done." in out
    assert agent.client.messages.create.call_count == 1


def test_tool_use_then_text():
    agent = Agent(_registry_with_echo())
    agent.client = MagicMock()
    agent.client.messages.create.side_effect = [
        _msg([_use("u1", "echo", {"v": "hello"})], stop_reason="tool_use"),
        _msg([_text("got hello")], stop_reason="end_turn"),
    ]
    out = "".join(agent.chat("say hi"))
    assert "got hello" in out
    assert agent.client.messages.create.call_count == 2


def test_unknown_tool_returns_error_to_model():
    agent = Agent(_registry_with_echo())
    agent.client = MagicMock()
    agent.client.messages.create.side_effect = [
        _msg([_use("u1", "missing", {})], stop_reason="tool_use"),
        _msg([_text("ok")], stop_reason="end_turn"),
    ]
    list(agent.chat("x"))
    tool_result_msgs = [m for m in agent.messages
                        if m["role"] == "user" and isinstance(m["content"], list)
                        and any(isinstance(c, dict) and c.get("type") == "tool_result" for c in m["content"])]
    assert tool_result_msgs
    assert tool_result_msgs[0]["content"][0]["is_error"] is True
