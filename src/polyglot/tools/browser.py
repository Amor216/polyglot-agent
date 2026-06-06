from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import Tool, ToolRegistry

MAX_EXTRACT_CHARS = 50_000
ACTION_TIMEOUT_MS = 15_000


class _BrowserHandle:
    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None

    def page(self):
        if self._page is not None:
            return self._page
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=False)
        ctx = self._browser.new_context(viewport={"width": 1280, "height": 800})
        self._page = ctx.new_page()
        self._page.set_default_timeout(ACTION_TIMEOUT_MS)
        return self._page

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._playwright:
                self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None


_handle: Optional[_BrowserHandle] = None


def _h() -> _BrowserHandle:
    global _handle
    if _handle is None:
        _handle = _BrowserHandle()
    return _handle


def shutdown_browser() -> None:
    global _handle
    if _handle is not None:
        _handle.close()
        _handle = None


def _navigate(args: dict) -> str:
    page = _h().page()
    url = args["url"]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    page.goto(url, wait_until="domcontentloaded")
    return f"loaded: {page.url}\ntitle: {page.title()}"


def _extract(args: dict) -> str:
    page = _h().page()
    selector = args.get("selector")
    if selector:
        loc = page.locator(selector)
        text = "\n".join(loc.all_inner_texts())
    else:
        text = page.inner_text("body")
    if len(text) > MAX_EXTRACT_CHARS:
        text = text[:MAX_EXTRACT_CHARS] + "\n...[truncated]"
    return text or "(no text)"


def _click(args: dict) -> str:
    page = _h().page()
    selector = args["selector"]
    page.locator(selector).first.click()
    return f"clicked: {selector}"


def _type(args: dict) -> str:
    page = _h().page()
    selector = args["selector"]
    text = args["text"]
    submit = bool(args.get("submit", False))
    loc = page.locator(selector).first
    loc.fill(text)
    if submit:
        loc.press("Enter")
    return f"typed into {selector}{' + Enter' if submit else ''}"


def _screenshot(args: dict) -> str:
    page = _h().page()
    out = Path(args["path"]).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=bool(args.get("full_page", False)))
    return f"saved: {out}"


def register_browser_tools(reg: ToolRegistry) -> None:
    reg.register(Tool(
        name="browser_navigate",
        description="Open a URL in the headed browser. Returns final URL and page title.",
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        handler=_navigate,
    ))
    reg.register(Tool(
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
    ))
    reg.register(Tool(
        name="browser_click",
        description="Click the first element matching a CSS selector.",
        input_schema={
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
        handler=_click,
    ))
    reg.register(Tool(
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
    ))
    reg.register(Tool(
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
    ))
