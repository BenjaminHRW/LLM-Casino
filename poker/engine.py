"""Texas Hold'em table engine for three players."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Protocol

from poker.cards import Card, Deck
from poker.evaluator import HandRank, describe_hole, evaluate_hand
from poker.personas import PlayerConfig

STREETS = ("preflop", "flop", "turn", "river")
Street = str
Phase = str  # idle | betting | dealing | showdown | complete


class DecisionMaker(Protocol):
    def decide(self, player: Player, view: dict[str, Any]) -> Decision: ...


@dataclass
class Decision:
    action: str
    amount: int | None = None
    thought: str = ""
    source: str = "llm"


@dataclass
class Player:
    seat: int
    name: str
    model: str
    persona: str
    buyin: int
    stack: int
    hole: list[Card] = field(default_factory=list)
    street_bet: int = 0
    total_in: int = 0
    folded: bool = False
    all_in: bool = False
    last_action: str = ""
    last_thought: str = ""
    thinking: bool = False
    api_key: str = ""
    base_url: str = ""

    @property
    def in_hand(self) -> bool:
        return not self.folded

    @property
    def can_act(self) -> bool:
        return not self.folded and not self.all_in and self.stack > 0


@dataclass
class LogEvent:
    kind: str
    street: str
    message: str
    thought: str = ""
    actor: str = ""
    source: str = ""


@dataclass
class StepResult:
    kind: str
    message: str
    snapshot: dict[str, Any]


class Table:
    def __init__(
        self,
        configs: list[PlayerConfig],
        small_blind: int = 10,
        big_blind: int = 20,
        rng: random.Random | None = None,
    ) -> None:
        if len(configs) != 3:
            raise ValueError("this table is 3-handed")
        self.small_blind = small_blind
        self.big_blind = big_blind
        self._rng = rng or random.Random()
        self.players = [
            Player(
                seat=index,
                name=cfg.name,
                model=cfg.model,
                persona=cfg.persona,
                buyin=cfg.buyin,
                stack=cfg.buyin,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
            )
            for index, cfg in enumerate(configs)
        ]
        self.dealer = 0
        self.hand_number = 0
        self.board: list[Card] = []
        self.deck = Deck(self._rng)
        self.street: Street = "preflop"
        self.phase: Phase = "idle"
        self.current_bet = 0
        self.min_raise = big_blind
        self.pending: set[int] = set()
        self.actor: int | None = None
        self.log: list[LogEvent] = []
        self.winners: list[str] = []
        self.showdown_ranks: dict[int, str] = {}
        self.last_pot = 0

    def apply_config(self, configs: list[PlayerConfig], reset_stacks: bool = False) -> None:
        for player, cfg in zip(self.players, configs, strict=True):
            player.name = cfg.name
            player.model = cfg.model
            player.persona = cfg.persona
            player.buyin = cfg.buyin
            player.api_key = cfg.api_key
            player.base_url = cfg.base_url
            if reset_stacks or self.phase == "idle":
                player.stack = cfg.buyin
                player.folded = False
                player.all_in = False
                player.hole = []
                player.last_action = ""
                player.last_thought = ""
                player.total_in = 0
                player.street_bet = 0

    def reset_table(self, configs: list[PlayerConfig]) -> None:
        self.apply_config(configs, reset_stacks=True)
        self.phase = "idle"
        self.board = []
        self.log = []
        self.winners = []
        self.showdown_ranks = {}
        self.actor = None
        self.hand_number = 0
        self.dealer = 0
        self.last_pot = 0

    @property
    def pot(self) -> int:
        return sum(player.total_in for player in self.players)

    @property
    def live_players(self) -> list[Player]:
        return [player for player in self.players if player.in_hand]

    @property
    def complete(self) -> bool:
        return self.phase in {"complete", "idle"}

    def sb_index(self) -> int:
        return (self.dealer + 1) % 3

    def bb_index(self) -> int:
        return (self.dealer + 2) % 3

    def current_player(self) -> Player | None:
        if self.actor is None:
            return None
        return self.players[self.actor]

    def to_call(self, player: Player) -> int:
        return max(0, self.current_bet - player.street_bet)

    def legal_actions(self, player: Player) -> dict[str, Any]:
        if not player.can_act:
            return {"actions": [], "to_call": 0, "min_to": 0, "max_to": 0}
        to_call = self.to_call(player)
        actions: list[str] = []
        min_to = 0
        max_to = player.street_bet + player.stack
        if to_call == 0:
            actions.append("check")
            if player.stack > 0:
                actions.append("bet")
                actions.append("allin")
                min_to = min(max(self.big_blind, self.min_raise), max_to)
        else:
            actions.append("fold")
            actions.append("call")
            if player.stack > to_call:
                actions.append("raise")
                actions.append("allin")
                min_to = min(self.current_bet + self.min_raise, max_to)
            elif player.stack > 0:
                actions.append("allin")
        return {
            "actions": actions,
            "to_call": to_call,
            "min_to": min_to,
            "max_to": max_to,
        }

    def view_for(self, player: Player) -> dict[str, Any]:
        legal = self.legal_actions(player)
        others = []
        for other in self.players:
            if other.seat == player.seat:
                continue
            others.append(
                {
                    "name": other.name,
                    "stack": other.stack,
                    "street_bet": other.street_bet,
                    "folded": other.folded,
                    "all_in": other.all_in,
                    "last_action": other.last_action,
                }
            )
        return {
            "street": self.street,
            "hand_number": self.hand_number,
            "pot": self.pot,
            "board": [str(card) for card in self.board],
            "hole": [str(card) for card in player.hole],
            "your_stack": player.stack,
            "your_street_bet": player.street_bet,
            "legal": legal,
            "history": [event.message for event in self.log[-12:]],
            "others": others,
            "blinds": {"sb": self.small_blind, "bb": self.big_blind},
            "persona": player.persona,
            "name": player.name,
        }

    def snapshot(self) -> dict[str, Any]:
        actor = self.current_player()
        return {
            "phase": self.phase,
            "street": self.street if self.phase != "idle" else "",
            "hand_number": self.hand_number,
            "pot": self.last_pot if self.phase == "complete" else self.pot,
            "pot_label": "AWARDED" if self.phase == "complete" and self.last_pot else "POT",
            "board": [self._card_dict(card) for card in self.board],
            "dealer": self.dealer,
            "sb": self.sb_index() if self.phase != "idle" else None,
            "bb": self.bb_index() if self.phase != "idle" else None,
            "actor": self.actor,
            "actor_name": actor.name if actor else "",
            "winners": list(self.winners),
            "showdown_ranks": dict(self.showdown_ranks),
            "complete": self.phase == "complete",
            "idle": self.phase == "idle",
            "players": [self._player_dict(player) for player in self.players],
            "log": [
                {
                    "kind": event.kind,
                    "street": event.street,
                    "message": event.message,
                    "thought": event.thought,
                    "actor": event.actor,
                }
                for event in self.log[-40:]
            ],
        }

    def step(self, client: DecisionMaker) -> StepResult:
        if self.phase == "idle":
            return self.start_hand()
        if self.phase == "complete":
            return StepResult("complete", "Hand complete. Deal a new hand to continue.", self.snapshot())

        live = self.live_players
        if len(live) == 1:
            return self._award_fold(live[0])

        if self.phase == "betting" and self._betting_closed():
            if len(self.board) == 5:
                return self._showdown()
            return self._deal_next_street()

        if self.phase != "betting":
            if len(self.board) == 5:
                return self._showdown()
            return self._deal_next_street()

        player = self.current_player()
        if player is None or not player.can_act:
            self._skip_to_next_actor()
            player = self.current_player()
            if player is None:
                if len(self.board) == 5:
                    return self._showdown()
                return self._deal_next_street()

        player.thinking = True
        view = self.view_for(player)
        try:
            decision = client.decide(player, view)
        finally:
            player.thinking = False
        applied = self._apply(player, decision)
        self._after_action(player)
        live = self.live_players
        extra = ""
        if len(live) == 1:
            fold_result = self._award_fold(live[0])
            return StepResult("action", f"{applied.message} {fold_result.message}", self.snapshot())
        if self._betting_closed():
            if len(self.board) == 5:
                show = self._showdown()
                extra = " " + show.message
            else:
                dealt = self._deal_next_street()
                extra = " " + dealt.message
        return StepResult("action", applied.message + extra, self.snapshot())

    def start_hand(self) -> StepResult:
        self._return_unsettled()
        if self.hand_number > 0:
            self.dealer = (self.dealer + 1) % 3
        self.hand_number += 1
        self.deck = Deck(self._rng)
        self.board = []
        self.street = "preflop"
        self.phase = "betting"
        self.current_bet = self.big_blind
        self.min_raise = self.big_blind
        self.winners = []
        self.showdown_ranks = {}
        self.last_pot = 0
        self.log = []
        for player in self.players:
            if player.stack <= 0:
                player.stack = player.buyin
                self._note("system", f"{player.name} rebuys to ${player.buyin:,}.")
            player.hole = []
            player.street_bet = 0
            player.total_in = 0
            player.folded = False
            player.all_in = False
            player.last_action = ""
            player.last_thought = ""
            player.thinking = False
        for player in self.players:
            player.hole = self.deck.deal(2)
        sb = self.players[self.sb_index()]
        bb = self.players[self.bb_index()]
        self._post_blind(sb, self.small_blind, "SB")
        self._post_blind(bb, self.big_blind, "BB")
        self.current_bet = max(player.street_bet for player in self.players)
        self.pending = {player.seat for player in self.players if player.can_act}
        self.actor = self._first_to_act("preflop")
        self._note(
            "deal",
            f"Hand #{self.hand_number} dealt. {sb.name} posts SB ${self.small_blind}, "
            f"{bb.name} posts BB ${self.big_blind}.",
        )
        if self.actor is not None:
            self._note("to_act", f"{self.players[self.actor].name} to act preflop.")
        return StepResult("deal", f"Hand #{self.hand_number} dealt.", self.snapshot())

    def _card_dict(self, card: Card) -> dict[str, str]:
        return {
            "rank": card.display_rank,
            "suit": card.symbol,
            "color": card.color,
            "code": card.code,
            "text": str(card),
        }

    def _player_dict(self, player: Player) -> dict[str, Any]:
        return {
            "seat": player.seat,
            "name": player.name,
            "model": player.model,
            "stack": player.stack,
            "hole": [self._card_dict(card) for card in player.hole],
            "street_bet": player.street_bet,
            "total_in": player.total_in,
            "folded": player.folded,
            "all_in": player.all_in,
            "last_action": player.last_action,
            "last_thought": player.last_thought,
            "thinking": player.thinking,
            "is_dealer": player.seat == self.dealer and self.phase != "idle",
            "is_sb": player.seat == self.sb_index() and self.phase != "idle",
            "is_bb": player.seat == self.bb_index() and self.phase != "idle",
            "is_actor": player.seat == self.actor and self.phase == "betting",
        }

    def _note(self, kind: str, message: str, thought: str = "", actor: str = "", source: str = "") -> None:
        self.log.append(
            LogEvent(
                kind=kind,
                street=self.street,
                message=message,
                thought=thought,
                actor=actor,
                source=source,
            )
        )

    def _return_unsettled(self) -> None:
        """Give back chips in the middle if a hand is abandoned mid-pot."""
        for player in self.players:
            if player.total_in:
                player.stack += player.total_in
                player.total_in = 0
            player.street_bet = 0

    def _post_blind(self, player: Player, amount: int, label: str) -> None:
        posted = self._put(player, amount)
        player.last_action = f"posts {label} ${posted}"
        if player.stack == 0:
            player.all_in = True
        self._note("blind", f"{player.name} posts {label} ${posted}.", actor=player.name)

    def _put(self, player: Player, amount: int) -> int:
        pay = min(max(0, amount), player.stack)
        player.stack -= pay
        player.street_bet += pay
        player.total_in += pay
        if player.stack == 0:
            player.all_in = True
        return pay

    def _first_to_act(self, street: str) -> int | None:
        order = self._action_order(street)
        for seat in order:
            if self.players[seat].can_act:
                return seat
        return None

    def _action_order(self, street: str) -> list[int]:
        if street == "preflop":
            start = (self.bb_index() + 1) % 3
        else:
            start = (self.dealer + 1) % 3
        return [(start + offset) % 3 for offset in range(3)]

    def _betting_closed(self) -> bool:
        live = self.live_players
        if len(live) <= 1:
            return True
        can_act = [player for player in live if player.can_act]
        if len(can_act) == 0:
            return True
        if len(can_act) == 1 and all(
            player.street_bet >= self.current_bet or player.all_in for player in live
        ):
            return True
        if self.pending:
            return False
        return all(player.street_bet == self.current_bet or player.all_in for player in live)

    def _skip_to_next_actor(self) -> None:
        if not self.pending:
            self.actor = None
            return
        order = self._action_order(self.street)
        if self.actor is None:
            start_at = 0
        else:
            start_at = (order.index(self.actor) + 1) % 3
        for offset in range(3):
            seat = order[(start_at + offset) % 3]
            if seat in self.pending and self.players[seat].can_act:
                self.actor = seat
                return
        self.actor = None

    def _after_action(self, player: Player) -> None:
        self.pending.discard(player.seat)
        self._skip_to_next_actor()

    def _reopen(self, aggressor: Player) -> None:
        self.pending = {
            player.seat
            for player in self.players
            if player.can_act and player.seat != aggressor.seat
        }

    def _apply(self, player: Player, decision: Decision) -> StepResult:
        legal = self.legal_actions(player)
        action = (decision.action or "").lower().strip()
        if action == "all-in":
            action = "allin"
        if action not in legal["actions"]:
            if "check" in legal["actions"]:
                action = "check"
            elif "call" in legal["actions"]:
                action = "call"
            elif "fold" in legal["actions"]:
                action = "fold"
            else:
                action = legal["actions"][0] if legal["actions"] else "check"
        thought = (decision.thought or "").strip()
        player.last_thought = thought
        to_call = legal["to_call"]
        min_to = legal["min_to"]
        max_to = legal["max_to"]

        if action == "fold":
            player.folded = True
            player.last_action = "fold"
            self._note("action", f"{player.name} folds.", thought, player.name, decision.source)
            return StepResult("action", f"{player.name} folds.", self.snapshot())

        if action == "check":
            player.last_action = "check"
            self._note("action", f"{player.name} checks.", thought, player.name, decision.source)
            return StepResult("action", f"{player.name} checks.", self.snapshot())

        if action == "call":
            paid = self._put(player, to_call)
            player.last_action = f"call ${paid}" if paid else "call"
            if player.all_in:
                player.last_action = f"all-in ${paid}"
            self._note(
                "action",
                f"{player.name} {player.last_action}.",
                thought,
                player.name,
                decision.source,
            )
            return StepResult("action", f"{player.name} {player.last_action}.", self.snapshot())

        if action == "allin":
            paid = self._put(player, player.stack)
            new_bet = player.street_bet
            raise_size = new_bet - self.current_bet
            if new_bet > self.current_bet:
                if raise_size >= self.min_raise:
                    self.min_raise = raise_size
                    self._reopen(player)
                self.current_bet = max(self.current_bet, new_bet)
            player.last_action = f"all-in ${paid}"
            self._note(
                "action",
                f"{player.name} shoves all-in (${paid} more).",
                thought,
                player.name,
                decision.source,
            )
            return StepResult("action", f"{player.name} {player.last_action}.", self.snapshot())

        target = decision.amount if decision.amount is not None else min_to
        try:
            target = int(target)
        except (TypeError, ValueError):
            target = min_to
        target = max(min_to, min(target, max_to))
        pay = max(0, target - player.street_bet)
        opening_bet = self.current_bet == 0
        paid = self._put(player, pay)
        new_bet = player.street_bet
        raise_size = new_bet - self.current_bet
        if new_bet > self.current_bet:
            self.min_raise = max(self.big_blind, raise_size if raise_size > 0 else self.big_blind)
            self.current_bet = new_bet
            self._reopen(player)
        if player.all_in:
            player.last_action = f"all-in ${paid}"
        elif opening_bet:
            player.last_action = f"bets ${new_bet}"
        else:
            player.last_action = f"raises to ${new_bet}"
        self._note(
            "action",
            f"{player.name} {player.last_action}.",
            thought,
            player.name,
            decision.source,
        )
        return StepResult("action", f"{player.name} {player.last_action}.", self.snapshot())

    def _deal_next_street(self) -> StepResult:
        for player in self.players:
            player.street_bet = 0
        self.current_bet = 0
        self.min_raise = self.big_blind
        if len(self.board) == 0:
            self.deck.deal(1)
            self.board.extend(self.deck.deal(3))
            self.street = "flop"
            label = "Flop"
        elif len(self.board) == 3:
            self.deck.deal(1)
            self.board.extend(self.deck.deal(1))
            self.street = "turn"
            label = "Turn"
        elif len(self.board) == 4:
            self.deck.deal(1)
            self.board.extend(self.deck.deal(1))
            self.street = "river"
            label = "River"
        else:
            return self._showdown()
        board_text = " ".join(str(card) for card in self.board)
        can_act = [player for player in self.live_players if player.can_act]
        if len(can_act) >= 2:
            self.phase = "betting"
            self.pending = {player.seat for player in can_act}
            self.actor = self._first_to_act(self.street)
        else:
            self.phase = "dealing"
            self.pending = set()
            self.actor = None
        self._note("street", f"{label}: {board_text}")
        return StepResult("street", f"{label}: {board_text}", self.snapshot())

    def _award_fold(self, winner: Player) -> StepResult:
        pot = self.pot
        self.last_pot = pot
        winner.stack += pot
        for player in self.players:
            player.total_in = 0
        self.winners = [winner.name]
        self.phase = "complete"
        self.actor = None
        self.pending = set()
        self._note("result", f"{winner.name} wins ${pot:,} as everyone else folded.")
        return StepResult("fold_win", f"{winner.name} wins ${pot:,}.", self.snapshot())

    def _showdown(self) -> StepResult:
        self.phase = "showdown"
        self.actor = None
        self.pending = set()
        self.last_pot = self.pot
        live = self.live_players
        ranks: dict[int, HandRank] = {}
        for player in live:
            ranks[player.seat] = evaluate_hand(player.hole + self.board)
            self.showdown_ranks[player.seat] = ranks[player.seat].name
            self._note(
                "showdown",
                f"{player.name} shows {describe_hole(player.hole)} — {ranks[player.seat].name}.",
                actor=player.name,
            )
        awarded = self._settle_pots(ranks)
        self.phase = "complete"
        names = ", ".join(self.winners)
        self._note("result", f"Pot awarded to {names}. " + "; ".join(awarded))
        return StepResult("showdown", f"Showdown: {names} win.", self.snapshot())

    def _settle_pots(self, ranks: dict[int, HandRank]) -> list[str]:
        contributors = [player for player in self.players if player.total_in > 0]
        levels = sorted({player.total_in for player in contributors})
        prev = 0
        summaries: list[str] = []
        winners: list[str] = []
        for level in levels:
            in_level = [player for player in contributors if player.total_in >= level]
            amount = (level - prev) * len(in_level)
            prev = level
            if amount <= 0:
                continue
            contenders = [player for player in in_level if not player.folded]
            if not contenders:
                continue
            best = max(ranks[player.seat] for player in contenders)
            pot_winners = [player for player in contenders if ranks[player.seat] == best]
            share, remainder = divmod(amount, len(pot_winners))
            for index, winner in enumerate(pot_winners):
                prize = share + (1 if index < remainder else 0)
                winner.stack += prize
            names = ", ".join(player.name for player in pot_winners)
            for player in pot_winners:
                if player.name not in winners:
                    winners.append(player.name)
            summaries.append(f"{names} take ${amount:,} with {best.name}")
        self.winners = winners
        for player in self.players:
            player.total_in = 0
        return summaries
