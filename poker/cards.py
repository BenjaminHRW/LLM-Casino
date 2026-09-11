"""Playing cards and a shuffled deck."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VALUE = {rank: index for index, rank in enumerate(RANKS, start=2)}
RANK_NAME = {
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
    11: "Jack",
    12: "Queen",
    13: "King",
    14: "Ace",
}
SUIT_SYMBOL = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_NAME = {"s": "spades", "h": "hearts", "d": "diamonds", "c": "clubs"}
SUIT_COLOR = {"s": "black", "h": "red", "d": "red", "c": "black"}


@dataclass(frozen=True, order=True)
class Card:
    rank: int
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANK_VALUE.values():
            raise ValueError(f"invalid rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"invalid suit: {self.suit}")

    @property
    def rank_code(self) -> str:
        return RANKS[self.rank - 2]

    @property
    def display_rank(self) -> str:
        return {11: "J", 12: "Q", 13: "K", 14: "A"}.get(self.rank, str(self.rank))

    @property
    def symbol(self) -> str:
        return SUIT_SYMBOL[self.suit]

    @property
    def color(self) -> str:
        return SUIT_COLOR[self.suit]

    @property
    def code(self) -> str:
        return f"{self.rank_code}{self.suit}"

    def __str__(self) -> str:
        return f"{self.display_rank}{self.symbol}"


def card_from_code(code: str) -> Card:
    code = code.strip()
    if len(code) < 2:
        raise ValueError(f"invalid card code: {code}")
    rank_code, suit = code[:-1], code[-1].lower()
    if rank_code == "10":
        rank_code = "T"
    rank_code = rank_code.upper()
    if rank_code not in RANK_VALUE or suit not in SUITS:
        raise ValueError(f"invalid card code: {code}")
    return Card(RANK_VALUE[rank_code], suit)


def parse_cards(codes: Iterable[str]) -> list[Card]:
    return [card_from_code(code) for code in codes]


class Deck:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self.cards: list[Card] = []
        self.reset()

    def reset(self) -> None:
        self.cards = [Card(rank, suit) for suit in SUITS for rank in range(2, 15)]
        self._rng.shuffle(self.cards)

    def deal(self, n: int = 1) -> list[Card]:
        if n > len(self.cards):
            raise ValueError("deck is empty")
        dealt = self.cards[:n]
        self.cards = self.cards[n:]
        return dealt

    def deal_one(self) -> Card:
        return self.deal(1)[0]
