import random

from poker.cards import parse_cards
from poker.engine import Decision, Player, Table
from poker.llm import LLMClient, MissingAPIKey
from poker.personas import clone_defaults


class Scripted:
    def __init__(self, actions: list[tuple[str, int | None]]) -> None:
        self.actions = list(actions)

    def decide(self, player: Player, view: dict) -> Decision:
        if self.actions:
            action, amount = self.actions.pop(0)
        else:
            legal = view["legal"]["actions"]
            action = "check" if "check" in legal else "call" if "call" in legal else legal[0]
            amount = None
        return Decision(action, amount, thought=f"{player.name} scripted {action}", source="script")


def test_blinds_and_first_actor() -> None:
    table = Table(clone_defaults(), rng=random.Random(1))
    table.start_hand()
    assert table.street == "preflop"
    assert table.pot == 30
    assert table.players[table.sb_index()].street_bet == 10
    assert table.players[table.bb_index()].street_bet == 20
    assert table.actor == table.dealer  # 3-handed: button acts first preflop
    assert all(len(player.hole) == 2 for player in table.players)
    codes = [card.code for player in table.players for card in player.hole]
    assert len(codes) == len(set(codes))


def test_fold_fold_awards_bb() -> None:
    table = Table(clone_defaults(), rng=random.Random(2))
    table.start_hand()
    client = Scripted([("fold", None), ("fold", None)])
    table.step(client)
    table.step(client)
    assert table.phase == "complete"
    assert table.winners == [table.players[table.bb_index()].name]
    assert sum(player.stack for player in table.players) == 3000
    assert table.players[table.bb_index()].stack == 1010


def test_check_down_preserves_chips() -> None:
    table = Table(clone_defaults(), rng=random.Random(3))
    client = Scripted([])  # always check/call
    table.start_hand()
    steps = 0
    while table.phase != "complete" and steps < 80:
        table.step(client)
        steps += 1
    assert table.phase == "complete"
    assert len(table.board) == 5
    assert sum(player.stack for player in table.players) == 3000
    assert table.winners
    assert table.showdown_ranks


def test_side_pot_split() -> None:
    table = Table(clone_defaults(), rng=random.Random(4))
    table.start_hand()
    table.players[0].hole = parse_cards(["As", "Ad"])
    table.players[1].hole = parse_cards(["Kc", "Kd"])
    table.players[2].hole = parse_cards(["2h", "3h"])
    table.board = parse_cards(["Ah", "Kh", "9c", "4d", "8s"])
    table.players[0].stack = 0
    table.players[0].total_in = 100
    table.players[0].all_in = True
    table.players[1].stack = 0
    table.players[1].total_in = 300
    table.players[1].all_in = True
    table.players[2].stack = 700
    table.players[2].total_in = 300
    table.players[0].folded = False
    table.players[1].folded = False
    table.players[2].folded = False
    table._showdown()
    assert table.players[0].name in table.winners
    # Main pot 300: Vega (AA) wins. Side pot 400: Nova (KK) vs Orion (air) — Nova.
    assert table.players[0].stack == 300
    assert table.players[1].stack == 400
    assert table.players[2].stack == 700
    assert sum(player.stack for player in table.players) == 1400


def test_new_hand_refunds_unsettled_pot() -> None:
    table = Table(clone_defaults(), rng=random.Random(2))
    table.start_hand()
    table.step(Scripted([("fold", None)]))
    assert table.pot > 0
    assert sum(player.stack for player in table.players) + table.pot == 3000
    table.start_hand()
    assert sum(player.stack for player in table.players) + table.pot == 3000
    assert table.pot == 30


def test_next_step_after_complete_is_noop() -> None:
    table = Table(clone_defaults(), rng=random.Random(5))
    client = Scripted([("fold", None), ("fold", None)])
    table.start_hand()
    table.step(client)
    table.step(client)
    result = table.step(client)
    assert result.kind == "complete"
    assert table.phase == "complete"


def test_llm_client_requires_per_seat_key() -> None:
    table = Table(clone_defaults(), rng=random.Random(6))
    table.start_hand()
    client = LLMClient()
    try:
        table.step(client)
        raise AssertionError("expected MissingAPIKey")
    except MissingAPIKey as exc:
        assert "API key" in str(exc)
    table.players[0].api_key = "sk-test"
    assert client.missing_seats(table.players) == ["Nova", "Orion"]

