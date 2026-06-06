# USD per 1M tokens. Update when Anthropic changes pricing.
# https://docs.anthropic.com/en/docs/about-claude/models/overview
PRICING = {
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-opus-4-5":   (15.00, 75.00),
    "claude-haiku-4-5":  (1.00,  5.00),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    for prefix, (in_p, out_p) in PRICING.items():
        if model.startswith(prefix):
            return (input_tokens / 1_000_000) * in_p + (output_tokens / 1_000_000) * out_p
    return None


def format_usage(model: str, input_tokens: int, output_tokens: int, tool_calls: int) -> str:
    parts = [f"{_h(input_tokens)} in", f"{_h(output_tokens)} out"]
    c = cost_usd(model, input_tokens, output_tokens)
    if c is not None:
        parts.append(f"${c:.4f}")
    if tool_calls:
        parts.append(f"{tool_calls} tool call{'s' if tool_calls != 1 else ''}")
    return " · ".join(parts)


def _h(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)
