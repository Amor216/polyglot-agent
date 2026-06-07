import sys
import time

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console

from . import sessions
from .agent import Agent, ToolLoopExhausted
from .tools import ToolRegistry
from .tools.browser import register_browser_tools, shutdown_browser
from .tools.system import register_system_tools

console = Console()


def build_registry(yolo: bool) -> ToolRegistry:
    reg = ToolRegistry()
    register_system_tools(reg, yolo=yolo)
    register_browser_tools(reg)
    return reg


def main() -> None:
    load_dotenv()
    argv = sys.argv[1:]
    yolo = "--yolo" in argv
    resume = "--resume" in argv

    reg = build_registry(yolo=yolo)
    agent = Agent(reg)

    session_path = sessions.new_path()
    if resume:
        prior = sessions.latest()
        if prior is not None:
            snap = sessions.load(prior)
            agent.load_state(snap.messages, snap.total_in, snap.total_out)
            session_path = prior
            console.print(f"[dim]resumed {prior.name} ({len(snap.messages)} messages)[/dim]")
        else:
            console.print("[yellow]no prior session to resume[/yellow]")

    console.print("[bold]polyglot[/bold] (sonnet 4.5) tools: " + ", ".join(reg.names()))
    if yolo:
        console.print("[yellow]yolo mode: destructive commands run without confirmation[/yellow]")
    console.print("[dim]ctrl-d or :q to exit, :reset to clear history, :sessions to list, :save to snapshot now[/dim]\n")

    prompt: PromptSession = PromptSession(history=InMemoryHistory())

    while True:
        try:
            line = prompt.prompt("> ")
        except (EOFError, KeyboardInterrupt):
            break

        stripped = line.strip()
        if not stripped:
            continue
        if stripped in (":q", ":quit", "exit"):
            break
        if stripped == ":reset":
            agent.reset()
            session_path = sessions.new_path()
            console.print("[dim]history cleared; future turns save to a new session[/dim]")
            continue
        if stripped == ":save":
            sessions.save(session_path, agent.messages, agent.total_in, agent.total_out)
            console.print(f"[dim]saved → {session_path}[/dim]")
            continue
        if stripped == ":sessions":
            _print_sessions()
            continue

        try:
            for chunk in agent.chat(line):
                console.print(chunk, end="", soft_wrap=True)
            console.print()
            sessions.save(session_path, agent.messages, agent.total_in, agent.total_out)
        except ToolLoopExhausted as e:
            console.print(f"\n[red]{e}[/red]")
        except Exception as e:
            console.print(f"\n[red]{type(e).__name__}: {e}[/red]")

    shutdown_browser()
    console.print("[dim]bye[/dim]")


def _print_sessions() -> None:
    snaps = sessions.list_sessions(limit=10)
    if not snaps:
        console.print("[dim]no sessions yet[/dim]")
        return
    for s in snaps:
        ago = _ago(time.time() - s.saved_at)
        first = _first_user(s.messages)
        console.print(f"[dim]{s.path.name}[/dim]  {ago:>8}  {first}")


def _ago(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    return f"{int(seconds / 86400)}d ago"


def _first_user(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            text = m["content"].strip().replace("\n", " ")
            return text[:60] + ("..." if len(text) > 60 else "")
    return "(no user message)"
