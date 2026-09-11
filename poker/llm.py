"""Pluggable LLM decision client. Each seat supplies its own API key."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Callable

from poker.engine import Decision, Player
from poker.personas import PlayerConfig, provider_of

ACTION_ALIASES = {
    "fold": "fold",
    "check": "check",
    "call": "call",
    "bet": "bet",
    "raise": "raise",
    "raise_to": "raise",
    "allin": "allin",
    "all-in": "allin",
    "all_in": "allin",
    "shove": "allin",
    "jam": "allin",
}


class MissingAPIKey(RuntimeError):
    """A seat has no API key for its selected model."""


class LLMCallError(RuntimeError):
    """The provider rejected or failed a request."""


def secret_or_env(name: str, secrets: dict[str, Any] | None = None) -> str:
    if secrets:
        value = secrets.get(name)
        if value:
            return str(value)
    return os.environ.get(name, "") or os.environ.get(name.lower(), "")


def parse_decision(text: str, legal: dict[str, Any]) -> Decision:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    data: dict[str, Any] = {}
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = {}
    action_raw = str(data.get("action") or data.get("move") or "").lower().strip()
    action = ACTION_ALIASES.get(action_raw, action_raw)
    amount = data.get("amount")
    if amount is None:
        amount = data.get("raise_to") or data.get("bet")
    thought = str(data.get("thought") or data.get("reason") or "").strip()
    if not thought:
        thought = cleaned[:180] if not data else "Let's see how this street plays."
    if action not in legal.get("actions", []):
        fallback = _safe_fallback(legal)
        thought = f"{thought} (illegal {action or 'empty'} → {fallback})"
        action = fallback
    try:
        amount_int = int(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount_int = None
    return Decision(action=action, amount=amount_int, thought=thought, source="llm")


def _safe_fallback(legal: dict[str, Any]) -> str:
    actions = legal.get("actions") or ["fold"]
    for preferred in ("check", "call", "fold", "allin"):
        if preferred in actions:
            return preferred
    return actions[0]


class LLMClient:
    def __init__(self, timeout: int = 30, default_base_url: str = "") -> None:
        self.timeout = timeout
        self.default_base_url = (default_base_url or "https://api.openai.com/v1").rstrip("/")

    def missing_seats(self, seats: list[Player] | list[PlayerConfig]) -> list[str]:
        return [seat.name for seat in seats if not (seat.api_key or "").strip()]

    def decide(self, player: Player, view: dict[str, Any]) -> Decision:
        if not (player.api_key or "").strip():
            raise MissingAPIKey(
                f"{player.name} needs an API key for {player.model}. "
                "Paste it in that seat’s sidebar next to the model picker."
            )
        try:
            raw = self._complete(player, view)
            decision = parse_decision(raw, view["legal"])
            decision.source = player.model
            if not decision.thought:
                decision.thought = "Going with the math on this one."
            return decision
        except (MissingAPIKey, LLMCallError):
            raise
        except Exception as exc:  # noqa: BLE001 — surface provider failures in the UI
            raise LLMCallError(f"{player.name} ({player.model}) failed: {exc}") from exc

    def _complete(self, player: Player, view: dict[str, Any]) -> str:
        system, user = build_prompt(player, view)
        provider = provider_of(player.model)
        if provider == "anthropic":
            return self._anthropic(player, system, user)
        if provider == "gemini":
            return self._gemini(player, system, user)
        return self._openai(player, system, user)

    def _openai(self, player: Player, system: str, user: str) -> str:
        base = (player.base_url or self.default_base_url).rstrip("/")
        payload = {
            "model": player.model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        return self._post_json(
            f"{base}/chat/completions",
            payload,
            {
                "Authorization": f"Bearer {player.api_key.strip()}",
                "Content-Type": "application/json",
            },
            lambda body: body["choices"][0]["message"]["content"],
            player.name,
        )

    def _anthropic(self, player: Player, system: str, user: str) -> str:
        payload = {
            "model": player.model,
            "max_tokens": 300,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        return self._post_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            {
                "x-api-key": player.api_key.strip(),
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            lambda body: "".join(part.get("text", "") for part in body.get("content", [])),
            player.name,
        )

    def _gemini(self, player: Player, system: str, user: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{player.model}:generateContent?key={player.api_key.strip()}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 300},
        }
        return self._post_json(
            url,
            payload,
            {"Content-Type": "application/json"},
            lambda body: body["candidates"][0]["content"]["parts"][0]["text"],
            player.name,
        )

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        extract: Callable[[Any], str],
        label: str,
    ) -> str:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise LLMCallError(f"{label} HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMCallError(f"{label} could not reach the model API: {exc}") from exc
        try:
            return extract(body)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMCallError(f"{label} got an unexpected API response") from exc


def build_prompt(player: Player, view: dict[str, Any]) -> tuple[str, str]:
    legal = view["legal"]
    system = (
        "You are an AI sitting in a 3-handed no-limit Texas Hold'em hand. "
        "Stay in character. You cannot see opponents' hole cards. "
        "Reply with a single JSON object, no markdown, of the form "
        '{"action":"fold|check|call|bet|raise|allin","amount":null,"thought":"..."}. '
        "amount is the total chips you put in on this street (raise-to), required for bet/raise. "
        "thought is 1-2 sentences of inner monologue for a spectator thought bubble."
    )
    user = (
        f"Persona: {player.persona}\n"
        f"Your name: {player.name}\n"
        f"Street: {view['street']}\n"
        f"Hole cards: {' '.join(view['hole'])}\n"
        f"Board: {' '.join(view['board']) or '(none)'}\n"
        f"Pot: ${view['pot']}\n"
        f"Your stack: ${view['your_stack']}\n"
        f"Your street commitment: ${view['your_street_bet']}\n"
        f"To call: ${legal['to_call']}\n"
        f"Legal actions: {', '.join(legal['actions'])}\n"
        f"If betting/raising, amount between {legal['min_to']} and {legal['max_to']}.\n"
        f"Blinds: {view['blinds']['sb']}/{view['blinds']['bb']}\n"
        f"Opponents: {json.dumps(view['others'])}\n"
        f"Recent action: {json.dumps(view['history'])}\n"
        "Choose one legal action now."
    )
    return system, user
