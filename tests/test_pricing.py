from polyglot.pricing import cost_usd, format_usage


def test_cost_sonnet():
    # 1M in @ $3, 1M out @ $15
    assert cost_usd("claude-sonnet-4-5", 1_000_000, 1_000_000) == 18.00


def test_cost_haiku_cheaper():
    sonnet = cost_usd("claude-sonnet-4-5", 10_000, 5_000)
    haiku = cost_usd("claude-haiku-4-5", 10_000, 5_000)
    assert haiku < sonnet


def test_cost_unknown_model():
    assert cost_usd("some-unknown-model", 1000, 1000) is None


def test_format_usage_compact():
    s = format_usage("claude-sonnet-4-5", 1500, 2000, 3)
    assert "1.5k in" in s
    assert "2.0k out" in s
    assert "3 tool calls" in s
    assert "$" in s


def test_format_singular():
    s = format_usage("claude-sonnet-4-5", 100, 50, 1)
    assert "1 tool call" in s
    assert "1 tool calls" not in s
