import random
from dataclasses import replace
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from poker.cards import Card
from poker.engine import Table
from poker.house import HOUSE_MODEL, house_decide, parse_display_card
from poker.llm import LLMClient
from poker.personas import clone_defaults


def _empty_key_configs():
    return [replace(player, api_key="") for player in clone_defaults()]


def test_parse_display_card() -> None:
    ace = parse_display_card("A♠")
    ten = parse_display_card("10♥")
    assert ace.rank == 14
    assert ace.suit == "s"
    assert ten.rank == 10
    assert ten.suit == "h"


def test_house_decide_without_key_is_legal() -> None:
    table = Table(_empty_key_configs(), rng=random.Random(0))
    table.start_hand()
    actor = table.current_player()
    assert actor is not None
    view = table.view_for(actor)
    decision = house_decide(actor, view, rng=random.Random(1), reason="no API key")
    assert decision.action in view["legal"]["actions"]
    assert decision.source == HOUSE_MODEL
    assert "House LLM" in decision.thought


def test_client_uses_house_when_key_missing() -> None:
    table = Table(_empty_key_configs(), rng=random.Random(2))
    table.start_hand()
    actor = table.current_player()
    assert actor is not None
    decision = LLMClient().decide(actor, table.view_for(actor))
    assert decision.source == HOUSE_MODEL


def test_client_uses_house_when_api_rejected() -> None:
    configs = [replace(player, api_key="sk-invalid") for player in clone_defaults()]
    table = Table(configs, rng=random.Random(3))
    table.start_hand()
    actor = table.current_player()
    assert actor is not None
    error = HTTPError("https://api.openai.com/v1/chat/completions", 401, "Unauthorized", hdrs=None, fp=BytesIO(b'{"error":"invalid"}'))
    with patch("poker.llm.urllib.request.urlopen", side_effect=error):
        decision = LLMClient().decide(actor, table.view_for(actor))
    assert decision.source == HOUSE_MODEL
    assert "invalid or failed API" in decision.thought


def test_full_hand_with_no_keys() -> None:
    table = Table(_empty_key_configs(), rng=random.Random(7))
    client = LLMClient()
    table.start_hand()
    for _ in range(80):
        if table.phase == "complete":
            break
        table.step(client)
    assert table.phase == "complete"
    assert table.winners


def test_house_folds_trash_facing_large_bet() -> None:
    player_configs = _empty_key_configs()
    table = Table(player_configs, rng=random.Random(0))
    table.start_hand()
    actor = table.current_player()
    assert actor is not None
    actor.hole = [Card(2, "c"), Card(7, "d")]
    view = table.view_for(actor)
    view["legal"] = {"actions": ["fold", "call", "raise", "allin"], "to_call": 400, "min_to": 800, "max_to": 980}
    view["pot"] = 80
    view["board"] = []
    decision = house_decide(actor, view, rng=random.Random(0), reason="no API key")
    assert decision.action == "fold"
