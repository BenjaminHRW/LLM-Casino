import random

from poker.engine import Table
from poker.llm import parse_decision
from poker.personas import clone_defaults, key_label, provider_of
from poker.ui import render_table

LEGAL = {"actions": ["fold", "call", "raise", "allin"], "to_call": 20, "min_to": 60, "max_to": 980}


def test_parse_json_decision() -> None:
    decision = parse_decision(
        '{"action":"raise","amount":80,"thought":"Charge the draws."}',
        LEGAL,
    )
    assert decision.action == "raise"
    assert decision.amount == 80
    assert decision.thought.startswith("Charge")


def test_parse_fenced_and_illegal_fallback() -> None:
    decision = parse_decision(
        "```json\n{\"action\":\"check\",\"thought\":\"oops\"}\n```",
        LEGAL,
    )
    assert decision.action == "call"
    assert "illegal" in decision.thought


def test_table_html_has_seats() -> None:
    table = Table(clone_defaults(), rng=random.Random(0))
    table.start_hand()
    html = render_table(table.snapshot())
    assert "Vega" in html
    assert "Nova" in html
    assert "Orion" in html
    assert "POT" in html
    assert "felt" in html
    assert "AWARDED" not in html


def test_provider_key_labels() -> None:
    assert provider_of("gpt-4o-mini") == "openai"
    assert provider_of("claude-sonnet-4-0") == "anthropic"
    assert provider_of("gemini-2.0-flash") == "gemini"
    assert key_label("claude-3-5-sonnet-latest") == "Anthropic API key"
    assert key_label("gpt-4o") == "API key"
