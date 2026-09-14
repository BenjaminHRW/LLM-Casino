"""Streamlit dashboard: configure 3 AI players and watch a Hold'em hand."""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from poker.engine import Table
from poker.llm import LLMClient, secret_or_env
from poker.personas import DEFAULT_PLAYERS, MODELS, PlayerConfig, clone_defaults, key_label, provider_of
from poker.ui import CSS, render_table

st.set_page_config(page_title="AI Poker Casino", layout="wide", page_icon="🃏")

MAX_STEPS = 80


def _secrets() -> dict[str, Any]:
    try:
        return dict(st.secrets)
    except Exception:
        return {}


def _env_key_for_model(model: str) -> str:
    secrets = _secrets()
    provider = provider_of(model)
    if provider == "anthropic":
        return secret_or_env("ANTHROPIC_API_KEY", secrets)
    if provider == "gemini":
        return secret_or_env("GEMINI_API_KEY", secrets)
    return secret_or_env("OPENAI_API_KEY", secrets)


def _env_base_url() -> str:
    return secret_or_env("OPENAI_BASE_URL", _secrets())


def _configs_from_widgets() -> list[PlayerConfig]:
    configs: list[PlayerConfig] = []
    for seat in range(3):
        configs.append(
            PlayerConfig(
                name=st.session_state[f"p{seat}_name"],
                model=st.session_state[f"p{seat}_model"],
                persona=st.session_state[f"p{seat}_persona"],
                buyin=int(st.session_state[f"p{seat}_buyin"]),
                api_key=str(st.session_state.get(f"p{seat}_api_key") or "").strip(),
                base_url=str(st.session_state.get(f"p{seat}_base_url") or "").strip(),
            )
        )
    return configs


def _init_state() -> None:
    if "table" not in st.session_state:
        defaults = clone_defaults()
        st.session_state.table = Table(defaults)
        st.session_state.status = "Deal a hand. Empty or invalid API keys use the built-in House LLM."
        for seat, cfg in enumerate(defaults):
            st.session_state[f"p{seat}_name"] = cfg.name
            st.session_state[f"p{seat}_model"] = cfg.model if cfg.model in MODELS else MODELS[0]
            st.session_state[f"p{seat}_persona"] = cfg.persona
            st.session_state[f"p{seat}_buyin"] = cfg.buyin
            st.session_state[f"p{seat}_api_key"] = _env_key_for_model(cfg.model)
            st.session_state[f"p{seat}_base_url"] = _env_base_url() if provider_of(cfg.model) == "openai" else ""


_init_state()
table: Table = st.session_state.table

st.markdown(
    f"""
    <style>
      {CSS}
      .stApp {{ background: radial-gradient(circle at top, #18243a 0%, #0b1220 55%); }}
      h1 {{ letter-spacing: 0.08em; font-size: 1.7rem; margin-bottom: 0.15rem; }}
      div[data-testid="stSidebar"] {{ background: #10192a; }}
      .stAppDeployButton {{ display: none; }}
      div[data-testid="stAlert"] {{ padding: 0.45rem 0.9rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("AI Poker Casino")
    st.caption("3-handed no-limit Hold'em. Paste an API key to use that provider, or leave it blank for the built-in House LLM.")
    sb = st.number_input("Small blind", min_value=1, value=table.small_blind, step=1)
    bb = st.number_input("Big blind", min_value=2, value=table.big_blind, step=1)
    delay = st.slider("Simulation delay (seconds)", 0.1, 2.5, 0.7, 0.1)
    st.divider()
    for seat, default in enumerate(DEFAULT_PLAYERS):
        with st.expander(
            f"Seat {seat + 1}: {st.session_state.get(f'p{seat}_name', default.name)}",
            expanded=True,
        ):
            st.text_input("Name", key=f"p{seat}_name")
            model_value = st.session_state[f"p{seat}_model"]
            if model_value not in MODELS:
                st.session_state[f"p{seat}_model"] = MODELS[0]
            st.selectbox("LLM model", MODELS, key=f"p{seat}_model")
            model_now = st.session_state[f"p{seat}_model"]
            st.text_input(
                key_label(model_now),
                type="password",
                key=f"p{seat}_api_key",
                help="Optional. If this is empty or the provider rejects it, this seat uses the built-in House LLM.",
            )
            if provider_of(model_now) == "openai":
                st.text_input(
                    "API base URL (optional)",
                    key=f"p{seat}_base_url",
                    placeholder="https://api.openai.com/v1",
                    help="OpenAI, Groq, OpenRouter, Ollama, etc.",
                )
            st.number_input("Buy-in / rebuy", min_value=bb * 10, step=50, key=f"p{seat}_buyin")
            st.text_area("Persona prompt", height=140, key=f"p{seat}_persona")
    st.divider()
    if st.button("Reset table & stacks", use_container_width=True):
        configs = _configs_from_widgets()
        table.small_blind = int(sb)
        table.big_blind = int(bb)
        table.reset_table(configs)
        st.session_state.status = "Table reset. Stacks restored to buy-ins."
        st.rerun()

configs = _configs_from_widgets()
table.small_blind = int(sb)
table.big_blind = int(bb)
table.apply_config(configs, reset_stacks=False)
client = LLMClient(default_base_url=_env_base_url())
missing = client.missing_seats(configs)

st.title("🃏 AI Poker Casino")
st.caption("Pick a model and persona per seat. API keys are optional — missing or invalid keys fall back to the built-in House LLM.")
if missing:
    st.info(
        "No API key for "
        + ", ".join(missing)
        + ". Those seats play with the built-in House LLM. Paste a valid key to use the selected cloud model instead."
    )
else:
    st.success("All three seats have API keys. Next Turn and Run Simulation will call those models; a rejected key still falls back to the House LLM.")

b1, b2, b3, b4 = st.columns([1, 1, 1, 2])
new_hand = b1.button("New Hand", use_container_width=True, type="secondary")
next_turn = b2.button("Next Turn", use_container_width=True, type="primary")
run_sim = b3.button("Run Simulation", use_container_width=True, type="primary")

table_slot = st.empty()
status_slot = st.empty()


def paint(snapshot: dict[str, Any] | None = None) -> None:
    snap = snapshot or table.snapshot()
    with table_slot:
        st.html(render_table(snap))
    status_slot.caption(st.session_state.status)


paint()


if new_hand:
    table.apply_config(configs, reset_stacks=False)
    result = table.start_hand()
    st.session_state.status = result.message
    st.rerun()

if next_turn:
    if table.phase == "complete":
        result = table.start_hand()
    else:
        actor = table.current_player()
        if actor and table.phase == "betting":
            actor.thinking = True
            st.session_state.status = f"{actor.name} is thinking…"
            paint()
            time.sleep(min(0.45, delay))
        result = table.step(client)
    st.session_state.status = result.message
    st.rerun()

if run_sim:
    steps = 0
    if table.phase in {"idle", "complete"}:
        result = table.start_hand()
        st.session_state.status = result.message
        paint()
        time.sleep(delay)
        steps += 1
    while table.phase != "complete" and steps < MAX_STEPS:
        actor = table.current_player()
        if actor and table.phase == "betting":
            actor.thinking = True
            st.session_state.status = f"{actor.name} is thinking…"
            paint()
            time.sleep(max(0.15, delay * 0.45))
        result = table.step(client)
        st.session_state.status = result.message
        paint()
        time.sleep(delay)
        steps += 1
    if steps >= MAX_STEPS and table.phase != "complete":
        st.session_state.status = "Stopped after the safety step limit."
    paint()

st.subheader("Action log")
log = table.snapshot()["log"]
if not log:
    st.caption("No actions yet.")
else:
    for event in reversed(log):
        thought = f" — _{event['thought']}_" if event.get("thought") else ""
        st.markdown(f"**{event['street'].upper()}** · {event['message']}{thought}")

with st.expander("How it works"):
    st.markdown(
        """
        API keys are **optional**. Paste a provider key next to a seat to use that
        cloud model. If the field is empty, or the key is rejected, that seat
        plays with the built-in **House LLM** (a local strategy player).

        Claude seats use an Anthropic key, Gemini seats use a Gemini key, and
        GPT / Llama / o-series seats use an OpenAI-compatible key (optional base URL
        for Groq, OpenRouter, or Ollama).

        **Next Turn** takes one visible step: a player action, the next street,
        or showdown. **Run Simulation** plays the rest of the hand, updating the
        table and thought bubbles as it goes.

        Hole cards are shown to you (the floor / spectator). Each model only sees
        its own hole cards in the prompt.
        """
    )
