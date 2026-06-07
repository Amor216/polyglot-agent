from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from .base import Tool, ToolRegistry


@dataclass(frozen=True)
class MCPServerSpec:
    name: str
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None


class MCPClient:
    """One asyncio loop in a worker thread. Owns one stdio MCP server.

    Public methods are sync; they submit coroutines to the worker thread and wait."""

    def __init__(self, spec: MCPServerSpec) -> None:
        self.spec = spec
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._err: BaseException | None = None
        self._session: Any = None
        self._stack: Any = None
        self._thread = threading.Thread(target=self._run, name=f"mcp-{spec.name}", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=30)
        if self._err:
            raise self._err

    def _run(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._connect())
            self._ready.set()
            self._loop.run_forever()
        except BaseException as exc:
            self._err = exc
            self._ready.set()

    async def _connect(self) -> None:
        from contextlib import AsyncExitStack

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._stack = AsyncExitStack()
        params = StdioServerParameters(
            command=self.spec.command,
            args=list(self.spec.args),
            env=self.spec.env,
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    def _call(self, coro_factory: Callable[[], Awaitable[Any]]) -> Any:
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError(f"mcp client {self.spec.name!r} is not running")
        fut: Future = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        return fut.result(timeout=60)

    def list_tools(self) -> list[dict]:
        result = self._call(lambda: self._session.list_tools())
        out = []
        for t in result.tools:
            out.append({
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema or {"type": "object", "properties": {}},
            })
        return out

    def call_tool(self, name: str, args: dict) -> str:
        async def do() -> str:
            res = await self._session.call_tool(name, args)
            chunks: list[str] = []
            for item in res.content:
                text = getattr(item, "text", None)
                if text:
                    chunks.append(text)
            if res.isError and not chunks:
                return "mcp error (no content)"
            return "\n".join(chunks) if chunks else ""
        return self._call(lambda: do())

    def stop(self) -> None:
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        async def teardown() -> None:
            if self._stack is not None:
                await self._stack.aclose()
        try:
            asyncio.run_coroutine_threadsafe(teardown(), loop).result(timeout=5)
        except Exception:
            pass
        loop.call_soon_threadsafe(loop.stop)
        self._thread.join(timeout=5)


_clients: list[MCPClient] = []


def register_mcp_servers(reg: ToolRegistry, specs: list[MCPServerSpec]) -> list[MCPClient]:
    clients: list[MCPClient] = []
    for spec in specs:
        client = MCPClient(spec)
        clients.append(client)
        for schema in client.list_tools():
            tool_name = f"{spec.name}__{schema['name']}"
            reg.register(Tool(
                name=tool_name,
                description=f"[{spec.name}] {schema['description']}",
                input_schema=schema["input_schema"],
                handler=_bind(client, schema["name"]),
            ))
    _clients.extend(clients)
    return clients


def shutdown_mcp() -> None:
    while _clients:
        client = _clients.pop()
        try:
            client.stop()
        except Exception:
            pass


def _bind(client: MCPClient, remote_name: str) -> Callable[[dict], str]:
    def handler(args: dict) -> str:
        return client.call_tool(remote_name, args)
    return handler
