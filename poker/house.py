"""Built-in House LLM: a local strategy player used when a seat has no usable API."""

from __future__ import annotations

import random
from typing import Any

from poker.cards import Card, RANK_VALUE, SUIT_SYMBOL
from poker.engine import Decision, Player
from poker.evaluator import evaluate_hand

HOUSE_MODEL = "house-llm"
_SYMBOL_TO_SUIT = {symbol: suit for suit, symbol in SUIT_SYMBOL.items()}
_FACE = {"J": 11, "Q": 12, "K": 13, "A": 14, "T": 10, "10": 10}


def parse_display_card(text: str) -> Card:
    raw = (text or "").strip()
    if len(raw) < 2:
        raise ValueError(f"invalid card: {text}")
    suit_char = raw[-1]
    rank_token = raw[:-1].upper().replace("10", "T")
    if suit_char in _SYMBOL_TO_SUIT:
        suit = _SYMBOL_TO_SUIT[suit_char]
    else:
        suit = suit_char.lower()
    rank = _FACE.get(rank_token) or RANK_VALUE.get(rank_token)
    if rank is None:
        raise ValueError(f"invalid card: {text}")
    return Card(rank, suit)


def house_decide(
    player: Player,
    view: dict[str, Any],
    rng: random.Random | None = None,
    reason: str = "",
) -> Decision:
    """Pick a legal Hold'em action from hole cards, board, and pot odds."""
    rng = rng or random.Random()
    legal = view.get("legal") or {}
    actions: list[str] = list(legal.get("actions") or [])
    if not actions:
        return Decision(action="check", thought="Nothing to do this street.", source=HOUSE_MODEL)

    strength, label = _hand_strength(player, view)
    strength = min(1.0, max(0.0, strength + rng.uniform(-0.04, 0.04)))
    to_call = int(legal.get("to_call") or 0)
    min_to = int(legal.get("min_to") or 0)
    max_to = int(legal.get("max_to") or 0)
    pot = int(view.get("pot") or 0)
    street_bet = int(view.get("your_street_bet") or player.street_bet)
    price = to_call / max(1, pot + to_call)

    action, amount = _choose_action(actions, strength, to_call, price, min_to, max_to, pot, street_bet, rng)
    why = reason.strip() or "no API key"
    thought = _thought(action, label, why)
    return Decision(action=action, amount=amount, thought=thought, source=HOUSE_MODEL)


def _hand_strength(player: Player, view: dict[str, Any]) -> tuple[float, str]:
    hole = list(player.hole or [])
    if len(hole) < 2:
        try:
            hole = [parse_display_card(code) for code in (view.get("hole") or [])]
        except ValueError:
            hole = []
    if len(hole) < 2:
        return 0.25, "an unknown hand"

    board: list[Card] = []
    for code in view.get("board") or []:
        try:
            board.append(parse_display_card(str(code)))
        except ValueError:
            continue

    if len(board) < 3:
        return _preflop_strength(hole)

    rank = evaluate_hand(hole + board)
    table = {0: 0.22, 1: 0.48, 2: 0.68, 3: 0.78, 4: 0.84, 5: 0.88, 6: 0.93, 7: 0.97, 8: 0.99}
    score = table.get(rank.category, 0.3)
    if rank.category == 1:
        pair_rank = rank.score[1]
        score += min(0.12, pair_rank / 140.0)
    return min(0.99, score), rank.name.lower()


def _preflop_strength(hole: list[Card]) -> tuple[float, str]:
    high, low = sorted(hole, key=lambda card: card.rank, reverse=True)
    suited = high.suit == low.suit
    pair = high.rank == low.rank
    gap = high.rank - low.rank
    if pair:
        score = 0.52 + (high.rank / 14.0) * 0.46
        return min(0.99, score), f"pocket {high.display_rank}s"
    score = (high.rank * 0.65 + low.rank * 0.35) / 14.0
    if suited:
        score += 0.07
    if gap == 1:
        score += 0.06
    elif gap == 2:
        score += 0.03
    elif gap >= 5:
        score -= 0.05
    if high.rank == 14 and low.rank >= 10:
        score += 0.08
    label = f"{high.display_rank}{low.display_rank}{'s' if suited else 'o'}"
    return min(0.95, max(0.12, score)), label


def _choose_action(
    actions: list[str],
    strength: float,
    to_call: int,
    price: float,
    min_to: int,
    max_to: int,
    pot: int,
    street_bet: int,
    rng: random.Random,
) -> tuple[str, int | None]:
    aggressive = "raise" if "raise" in actions else ("bet" if "bet" in actions else None)

    if to_call > 0:
        if "fold" in actions and (
            strength <= 0.22
            or (strength <= 0.42 and price >= 0.35)
            or strength + 0.18 < price
        ):
            return "fold", None
        if strength >= 0.70 and aggressive:
            return aggressive, _size(min_to, max_to, pot, street_bet, strength, rng)
        if "call" in actions:
            return "call", None
        if strength < 0.45 and "fold" in actions:
            return "fold", None
        if aggressive:
            return aggressive, _size(min_to, max_to, pot, street_bet, strength, rng)
        if "allin" in actions and strength >= 0.75:
            return "allin", None
        return actions[0], None

    if strength >= 0.58 and aggressive:
        return aggressive, _size(min_to, max_to, pot, street_bet, strength, rng)
    if "check" in actions:
        return "check", None
    if aggressive:
        return aggressive, min_to or None
    return actions[0], None


def _size(
    min_to: int,
    max_to: int,
    pot: int,
    street_bet: int,
    strength: float,
    rng: random.Random,
) -> int:
    if max_to <= 0:
        return min_to
    fraction = 0.45 + strength * 0.7 + rng.uniform(-0.05, 0.08)
    target = street_bet + max(min_to - street_bet, int(pot * fraction))
    if min_to and max_to:
        return max(min_to, min(max_to, target))
    return max(min_to, min(max_to or target, target))


def _thought(action: str, label: str, why: str) -> str:
    lines = {
        "fold": f"House LLM ({why}) — {label} is not worth this price.",
        "check": f"House LLM ({why}) — {label}. Checking and seeing a card.",
        "call": f"House LLM ({why}) — {label} is good enough to continue.",
        "bet": f"House LLM ({why}) — betting {label} for value / pressure.",
        "raise": f"House LLM ({why}) — raising with {label}.",
        "allin": f"House LLM ({why}) — shoving {label}.",
    }
    return lines.get(action, f"House LLM ({why}) — playing {label}.")
