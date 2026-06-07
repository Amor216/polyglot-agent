from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from ..config import Config
from .base import Tool, ToolRegistry

MAX_EXTRACT_CHARS = 50_000
ACTION_TIMEOUT_MS = 15_000

_SHUTDOWN = object()


class _BrowserWorker:
    # Playwright lives on its own thread so its asyncio loop never collides
    # with prompt_toolkit's. Tools submit closures, the worker runs them.

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name="polyglot-browser", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=30)
        if self._error:
            raise self._error

    def _run(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=False)
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            page.set_default_timeout(ACTION_TIMEOUT_MS)
        except BaseException as e:
            self._error = e
            self._ready.set()
            return

        self._ready.set()
        try:
            while True:
                item = self._queue.get()
                if item is _SHUTDOWN:
                    return
                fn, fut = item
                try:
                    fut.set_result(fn(page))
                except BaseException as e:
                    fut.set_exception(e)
        finally:
            try:
                browser.close()
            finally:
                pw.stop()

    def submit(self, fn: Callable[[Any], str]) -> str:
        fut: Future = Future()
        self._queue.put((fn, fut))
        return fut.result()

    def stop(self) -> None:
        self._queue.put(_SHUTDOWN)
        self._thread.join(timeout=5)


_worker: _BrowserWorker | None = None


def _w() -> _BrowserWorker:
    global _worker
    if _worker is None:
        _worker = _BrowserWorker()
    return _worker


def shutdown_browser() -> None:
    global _worker
    if _worker is not None:
        _worker.stop()
        _worker = None


def _navigate(args: dict) -> str:
    url = args["url"]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    def go(page) -> str:
        page.goto(url, wait_until="domcontentloaded")
        return f"loaded: {page.url}\ntitle: {page.title()}"

    return _w().submit(go)


def _extract(args: dict) -> str:
    selector = args.get("selector")

    def grab(page) -> str:
        if selector:
            text = "\n".join(page.locator(selector).all_inner_texts())
        else:
            text = page.inner_text("body")
        if len(text) > MAX_EXTRACT_CHARS:
            text = text[:MAX_EXTRACT_CHARS] + "\n...[truncated]"
        return text or "(no text)"

    return _w().submit(grab)


def _click(args: dict) -> str:
    selector = args["selector"]

    def do(page) -> str:
        page.locator(selector).first.click()
        return f"clicked: {selector}"

    return _w().submit(do)


def _type(args: dict) -> str:
    selector = args["selector"]
    text = args["text"]
    submit = bool(args.get("submit", False))

    def do(page) -> str:
        loc = page.locator(selector).first
        loc.fill(text)
        if submit:
            loc.press("Enter")
        return f"typed into {selector}{' + Enter' if submit else ''}"

    return _w().submit(do)


def _screenshot(args: dict) -> str:
    out = Path(args["path"]).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    full = bool(args.get("full_page", False))

    def do(page) -> str:
        page.screenshot(path=str(out), full_page=full)
        return f"saved: {out}"

    return _w().submit(do)


def register_browser_tools(reg: ToolRegistry, config: Config | None = None) -> None:
    cfg = config or Config()
    candidates: list[Tool] = [
        Tool(
            name="browser_navigate",
            description="Open a URL in the headed browser. Returns final URL and page title.",
            input_schema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            handler=_navigate,
        ),
        Tool(
            name="browser_extract",
            description=(
                "Return visible text of the current page or, if selector is given, of matched elements. "
                "Truncates at 50K chars."
            ),
            input_schema={
                "type": "object",
                "properties": {"selector": {"type": "string", "description": "Optional CSS selector"}},
            },
            handler=_extract,
        ),
        Tool(
            name="browser_click",
            description="Click the first element matching a CSS selector.",
            input_schema={
                "type": "object",
                "properties": {"selector": {"type": "string"}},
                "required": ["selector"],
            },
            handler=_click,
        ),
        Tool(
            name="browser_type",
            description="Type text into the first element matching a CSS selector. Optionally press Enter.",
            input_schema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                    "submit": {"type": "boolean", "default": False},
                },
                "required": ["selector", "text"],
            },
            handler=_type,
        ),
        Tool(
            name="browser_screenshot",
            description="Save a PNG screenshot of the current page.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "full_page": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
            handler=_screenshot,
        ),
    ]
    for tool in candidates:
        if cfg.is_tool_enabled(tool.name):
            reg.register(tool)
