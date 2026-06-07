# polyglot

Terminal LLM agent with two tool domains: system (files, shell, apps) and browser (Playwright, headed). Built against the Anthropic SDK directly, no agent framework.

Responses stream as they arrive. Each turn ends with a token + cost summary. Playwright runs in its own worker thread so its asyncio loop doesn't collide with the REPL's.

![demo](docs/demo.gif)

## What it does

You type what you want in natural language. The agent picks tools, runs them, replies. Examples:

```
> finde die drei größten dateien in meinem downloads ordner
> öffne hackernews und gib mir die top 3 titel
> erstelle einen ordner notes mit drei leeren markdown files
> screenshot von wikipedia.org speichern unter ./shots/wiki.png
```

## Install

Requires Python 3.10+.

```bash
uv sync
uv run playwright install chromium
cp .env.example .env  # add your ANTHROPIC_API_KEY
```

## Run

```bash
uv run polyglot
uv run polyglot --resume     # pick up the most recent session
uv run polyglot --markdown   # also render each assistant reply as Markdown after streaming
uv run polyglot --yolo       # skip the confirmation prompt on destructive commands (don't)
```

Sessions auto-save after every turn to `~/.polyglot/sessions/<timestamp>.json` (override with `POLYGLOT_HOME`).

Optional `~/.polyglot/config.toml` (or `POLYGLOT_CONFIG=path`) restricts which tools register and which shell commands are safe — see `config.example.toml`.

In-session commands:

| Command | Effect |
|---|---|
| `:reset` | Clear conversation history; future turns save to a new session |
| `:save` | Snapshot the current session now |
| `:sessions` | List the 10 most recent sessions |
| `:q` / Ctrl-D | Exit |

## Architecture

```
CLI (prompt_toolkit, rich)
    |
    v
Agent (streaming tool-use loop, max 12 steps)
    |
    +-- tools/system.py    read_file, list_dir, run_command, open_app
    |
    +-- tools/browser.py   browser_navigate, _extract, _click, _type, _screenshot
            |
            +-- worker thread -> Playwright (sync API, headed Chromium)

  safety.py    allowlist, destructive-op confirmation, default-deny
  audit.py     JSONL log at ~/.polyglot/audit.log
  pricing.py   per-model token cost
```

Why the worker thread: Playwright's sync API and `prompt_toolkit` both touch asyncio. On Python 3.12 their loops collide. Isolating Playwright on a daemon thread fixes it.

### Safety

Three layers:

1. **Allowlist** for shell commands. Anything not on the allowlist is rejected. The destructive set (`rm`, `git push`, `shutdown`, etc.) is recognized explicitly and requires confirmation.
2. **Interactive confirmation** for destructive commands, unless `--yolo`.
3. **Audit log** at `~/.polyglot/audit.log` (or `$POLYGLOT_AUDIT_DIR`): one JSON line per tool invocation, including inputs and outcomes.

Adjust `safety.py` to fit your environment. Default is conservative.

## Layout

```
src/polyglot/
  agent.py        tool-use loop
  cli.py          REPL
  safety.py       allowlist + classification
  audit.py        JSONL writer
  tools/
    base.py       Tool, ToolRegistry
    system.py     4 system tools
    browser.py    5 browser tools, lazy-launched Playwright on a worker thread
```

About 550 lines of Python. The browser is launched lazily on first browser-tool call and shut down on exit. Every turn ends with a dim line like `12.4k in, 1.8k out, $0.072, 4 tool calls`.

## Notes

- Model defaults to `claude-sonnet-4-5`. Override via `POLYGLOT_MODEL`.
- Browser runs **headed** so you can watch the agent work. Flip to headless in `browser.py` if you want it for CI.
- Tool loop is capped at 12 steps to avoid runaway cost.
- Output of `run_command` is truncated at 8K chars. Files at 200K bytes. Browser text at 50K chars.

## License

MIT.
