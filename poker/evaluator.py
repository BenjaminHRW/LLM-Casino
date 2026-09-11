"""5-card and 7-card Texas Hold'em hand evaluation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from poker.cards import RANK_NAME, Card

CATEGORY = {
    0: "High Card",
    1: "Pair",
    2: "Two Pair",
    3: "Three of a Kind",
    4: "Straight",
    5: "Flush",
    6: "Full House",
    7: "Four of a Kind",
    8: "Straight Flush",
}


@dataclass(frozen=True, order=True)
class HandRank:
    score: tuple[int, ...]
    name: str = field(compare=False)

    @property
    def category(self) -> int:
        return self.score[0]


def _straight_high(ranks: list[int]) -> int | None:
    uniq = sorted(set(ranks))
    if len(uniq) != 5:
        return None
    if uniq[-1] - uniq[0] == 4:
        return uniq[-1]
    if uniq == [2, 3, 4, 5, 14]:
        return 5
    return None


def evaluate_five(cards: list[Card]) -> HandRank:
    if len(cards) != 5:
        raise ValueError("evaluate_five expects 5 cards")
    ranks = sorted((card.rank for card in cards), reverse=True)
    flush = len({card.suit for card in cards}) == 1
    straight = _straight_high(ranks)
    counts = Counter(ranks)
    by_freq = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    freqs = sorted(counts.values(), reverse=True)

    if flush and straight is not None:
        label = "Royal Flush" if straight == 14 else f"Straight Flush, {RANK_NAME[straight]} high"
        return HandRank((8, straight), label)
    if freqs == [4, 1]:
        quad, kicker = by_freq[0][0], by_freq[1][0]
        return HandRank((7, quad, kicker), f"Four of a Kind, {RANK_NAME[quad]}s")
    if freqs == [3, 2]:
        trips, pair = by_freq[0][0], by_freq[1][0]
        return HandRank(
            (6, trips, pair),
            f"Full House, {RANK_NAME[trips]}s over {RANK_NAME[pair]}s",
        )
    if flush:
        return HandRank((5, *ranks), f"Flush, {RANK_NAME[ranks[0]]} high")
    if straight is not None:
        return HandRank((4, straight), f"Straight, {RANK_NAME[straight]} high")
    if freqs == [3, 1, 1]:
        trips = by_freq[0][0]
        kickers = sorted((rank for rank, count in counts.items() if count == 1), reverse=True)
        return HandRank((3, trips, *kickers), f"Three of a Kind, {RANK_NAME[trips]}s")
    if freqs == [2, 2, 1]:
        pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
        kicker = next(rank for rank, count in counts.items() if count == 1)
        return HandRank(
            (2, pairs[0], pairs[1], kicker),
            f"Two Pair, {RANK_NAME[pairs[0]]}s and {RANK_NAME[pairs[1]]}s",
        )
    if freqs == [2, 1, 1, 1]:
        pair = by_freq[0][0]
        kickers = sorted((rank for rank, count in counts.items() if count == 1), reverse=True)
        return HandRank((1, pair, *kickers), f"Pair of {RANK_NAME[pair]}s")
    return HandRank((0, *ranks), f"High Card, {RANK_NAME[ranks[0]]}")


def evaluate_hand(cards: list[Card]) -> HandRank:
    if len(cards) < 5:
        raise ValueError("need at least 5 cards")
    if len(cards) == 5:
        return evaluate_five(cards)
    return max(evaluate_five(list(combo)) for combo in combinations(cards, 5))


def describe_hole(cards: list[Card]) -> str:
    return " ".join(str(card) for card in cards)
