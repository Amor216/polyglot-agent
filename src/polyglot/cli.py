import sys

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console

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
    yolo = "--yolo" in sys.argv
    reg = build_registry(yolo=yolo)
    agent = Agent(reg)

    console.print("[bold]polyglot[/bold] (sonnet 4.5) tools: " + ", ".join(reg.names()))
    if yolo:
        console.print("[yellow]yolo mode: destructive commands run without confirmation[/yellow]")
    console.print("[dim]ctrl-d or :q to exit, :reset to clear history[/dim]\n")

    session: PromptSession = PromptSession(history=InMemoryHistory())

    while True:
        try:
            line = session.prompt("> ")
        except (EOFError, KeyboardInterrupt):
            break

        if not line.strip():
            continue
        if line.strip() in (":q", ":quit", "exit"):
            break
        if line.strip() == ":reset":
            agent.reset()
            console.print("[dim]history cleared[/dim]")
            continue

        try:
            for chunk in agent.chat(line):
                console.print(chunk, end="", soft_wrap=True)
            console.print()
        except ToolLoopExhausted as e:
            console.print(f"\n[red]{e}[/red]")
        except Exception as e:
            console.print(f"\n[red]{type(e).__name__}: {e}[/red]")

    shutdown_browser()
    console.print("[dim]bye[/dim]")
