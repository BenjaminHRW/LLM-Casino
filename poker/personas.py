"""Default 3-AI seating and persona copy."""

from __future__ import annotations

from dataclasses import dataclass, replace

MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o4-mini",
    "claude-3-5-sonnet-latest",
    "claude-sonnet-4-0",
    "gemini-2.0-flash",
    "llama-3.3-70b-versatile",
]


def provider_of(model: str) -> str:
    name = (model or "").lower()
    if "claude" in name:
        return "anthropic"
    if "gemini" in name:
        return "gemini"
    return "openai"


def key_label(model: str) -> str:
    provider = provider_of(model)
    if provider == "anthropic":
        return "Anthropic API key"
    if provider == "gemini":
        return "Gemini API key"
    return "API key"


@dataclass
class PlayerConfig:
    name: str
    model: str
    persona: str
    buyin: int = 1000
    api_key: str = ""
    base_url: str = ""


DEFAULT_PLAYERS: list[PlayerConfig] = [
    PlayerConfig(
        name="Vega",
        model="gpt-4o-mini",
        buyin=1000,
        persona=(
            "You are Vega, The Professor: a tight-aggressive GTO student. "
            "You value position, pot odds, and range advantage. You 3-bet "
            "strong hands and premium bluffs, rarely spew, and explain your "
            "read like a coach. Prefer small value bets; fold trash without the odds."
        ),
    ),
    PlayerConfig(
        name="Nova",
        model="claude-3-5-sonnet-latest",
        buyin=1000,
        persona=(
            "You are Nova, The Maniac: a loose-aggressive table captain. You "
            "love pressure, overbets, and thin value. You bluff more than GTO, "
            "especially when you smell weakness, but you still fold the true "
            "trash when the price is terrible. Your thoughts are cocky and short."
        ),
    ),
    PlayerConfig(
        name="Orion",
        model="gemini-2.0-flash",
        buyin=1000,
        persona=(
            "You are Orion, The Trap Artist: a patient, sticky player who "
            "slowplays monsters, check-raises flops, and hunts payoffs. You "
            "call more than you bet when you have a disguised strong hand, and "
            "you fold quietly when you are drawing dead. Thoughts are calm and sly."
        ),
    ),
]


def clone_defaults() -> list[PlayerConfig]:
    return [replace(player) for player in DEFAULT_PLAYERS]
