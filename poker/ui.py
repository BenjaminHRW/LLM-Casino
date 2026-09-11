"""HTML table view: green oval felt, seats, cards, thought bubbles."""

from __future__ import annotations

import html
from typing import Any

CSS = """
.casino * { box-sizing: border-box; }
.casino {
  position: relative;
  width: 100%;
  height: 500px;
  font-family: "Trebuchet MS", "Segoe UI", sans-serif;
  color: #f6f0e4;
}
.casino .felt {
  position: absolute;
  left: 11%;
  right: 11%;
  top: 148px;
  height: 240px;
  background: radial-gradient(ellipse at center, #36a85d 0%, #1b7a3e 46%, #0e4a26 80%);
  border: 14px solid #5a3016;
  border-radius: 50%;
  box-shadow:
    0 0 0 6px #d4af37,
    0 0 0 10px #24120a,
    0 18px 40px rgba(0, 0, 0, 0.45),
    inset 0 0 70px rgba(0, 0, 0, 0.25);
}
.casino .center {
  position: absolute;
  left: 50%;
  top: 70%;
  transform: translate(-50%, -50%);
  text-align: center;
  width: 78%;
}
.casino .street {
  letter-spacing: 0.28em;
  font-size: 11px;
  color: #d7eccf;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.casino .pot {
  font-size: 20px;
  font-weight: 700;
  color: #e4c56a;
  text-shadow: 0 2px 0 #0b2414;
  margin-bottom: 8px;
}
.casino .board {
  display: flex;
  gap: 7px;
  justify-content: center;
  min-height: 64px;
}
.casino .seat {
  position: absolute;
  width: 196px;
  text-align: center;
  z-index: 3;
}
.casino .seat.s0 { left: 50%; top: 2px; transform: translateX(-50%); }
.casino .seat.s1 { left: 18px; bottom: 8px; }
.casino .seat.s2 { right: 18px; bottom: 8px; }
.casino .seat.actor .chip-card {
  box-shadow: 0 0 0 3px #f3d789, 0 8px 18px rgba(0,0,0,0.35);
}
.casino .seat.folded { opacity: 0.48; }
.casino .chip-card {
  background: linear-gradient(180deg, #1a2438, #121826);
  border: 1px solid #3b4a63;
  border-radius: 14px;
  padding: 7px 8px 8px;
}
.casino .name { font-size: 15px; font-weight: 700; }
.casino .model { font-size: 10px; color: #9eb0c8; margin-top: 1px; }
.casino .stack { color: #8ee0a2; font-weight: 700; font-size: 13px; margin-top: 2px; }
.casino .badges { margin: 3px 0 4px; min-height: 16px; }
.casino .badge {
  display: inline-block;
  font-size: 10px;
  letter-spacing: 0.08em;
  padding: 2px 6px;
  border-radius: 999px;
  margin: 0 2px;
  background: #314057;
  color: #f6f0e4;
}
.casino .badge.d { background: #d4af37; color: #1a1404; font-weight: 700; }
.casino .badge.sb { background: #355f9a; }
.casino .badge.bb { background: #8a2f2f; }
.casino .badge.in { background: #7a2a8a; }
.casino .action { font-size: 11px; color: #f0d48a; min-height: 14px; }
.casino .hole { display: flex; gap: 5px; justify-content: center; margin-top: 5px; }
.casino .card {
  width: 42px;
  height: 58px;
  border-radius: 6px;
  background: #fbf7ee;
  border: 1px solid #cfc4aa;
  position: relative;
  box-shadow: 0 3px 7px rgba(0,0,0,0.25);
}
.casino .card .r {
  position: absolute;
  top: 4px;
  left: 5px;
  font-weight: 800;
  font-size: 13px;
  line-height: 1;
}
.casino .card.ten .r { font-size: 11px; letter-spacing: -0.5px; }
.casino .card .s {
  position: absolute;
  right: 4px;
  bottom: 3px;
  font-size: 16px;
}
.casino .card.red { color: #c31414; }
.casino .card.black { color: #1b1b1b; }
.casino .card.slot {
  background: rgba(255,255,255,0.08);
  border: 1px dashed rgba(255,255,255,0.28);
  box-shadow: none;
}
.casino .card.winner { box-shadow: 0 0 0 2px #e4c56a; }
.casino .bubble {
  position: absolute;
  max-width: 230px;
  background: #fffaf0;
  color: #1d2433;
  border-radius: 14px;
  padding: 7px 11px;
  font-size: 12px;
  line-height: 1.35;
  box-shadow: 0 8px 18px rgba(0,0,0,0.25);
  z-index: 5;
}
.casino .bubble b { color: #6a4a12; }
.casino .bubble.b0 { left: calc(50% + 108px); top: 4px; }
.casino .bubble.b1 { left: 16px; top: 150px; }
.casino .bubble.b2 { right: 16px; top: 150px; }
.casino .bubble.thinking { font-style: italic; color: #445; }
.casino .status {
  position: absolute;
  top: 4px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: #f3e6c0;
}
.casino .winner-banner {
  margin-top: 6px;
  color: #ffe7a3;
  font-weight: 700;
  font-size: 13px;
}
"""


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _cards_html(cards: list[dict[str, str]], slots: int | None = None, winner: bool = False) -> str:
    items = list(cards)
    extras = max(0, (slots or len(items)) - len(items))
    html_parts = []
    for card in items:
        klass = "card red" if card.get("color") == "red" else "card black"
        if winner:
            klass += " winner"
        if card.get("rank") == "10":
            klass += " ten"
        html_parts.append(
            f'<div class="{klass}"><div class="r">{_esc(card["rank"])}</div>'
            f'<div class="s">{_esc(card["suit"])}</div></div>'
        )
    for _ in range(extras):
        html_parts.append('<div class="card slot"></div>')
    return "".join(html_parts)


def render_table(snapshot: dict[str, Any]) -> str:
    street = (snapshot.get("street") or "ready").upper()
    phase = snapshot.get("phase") or "idle"
    pot = int(snapshot.get("pot") or 0)
    pot_label = snapshot.get("pot_label") or "POT"
    actor_name = snapshot.get("actor_name") or ""
    if phase == "idle":
        status = "Configure the three AIs, then deal a hand."
    elif phase == "complete":
        winners = ", ".join(snapshot.get("winners") or []) or "the board"
        status = f"Hand complete — {winners} take the pot."
    elif actor_name:
        status = f"{street} — {actor_name} to act"
    else:
        status = f"{street} — running out the board"

    bubbles = []
    seats = []
    winners = set(snapshot.get("winners") or [])
    for player in snapshot.get("players") or []:
        seat = player["seat"]
        classes = [f"seat s{seat}"]
        if player.get("is_actor"):
            classes.append("actor")
        if player.get("folded"):
            classes.append("folded")
        badges = []
        if player.get("is_dealer"):
            badges.append('<span class="badge d">D</span>')
        if player.get("is_sb"):
            badges.append('<span class="badge sb">SB</span>')
        if player.get("is_bb"):
            badges.append('<span class="badge bb">BB</span>')
        if player.get("all_in"):
            badges.append('<span class="badge in">ALL-IN</span>')
        winner = player["name"] in winners and phase == "complete"
        hole = _cards_html(player.get("hole") or [], winner=winner)
        seats.append(
            f'<div class="{" ".join(classes)}"><div class="chip-card">'
            f'<div class="name">{_esc(player["name"])}</div>'
            f'<div class="model">{_esc(player["model"])}</div>'
            f'<div class="stack">${player["stack"]:,}</div>'
            f'<div class="badges">{"".join(badges)}</div>'
            f'<div class="action">{_esc(player.get("last_action"))}</div>'
            f'<div class="hole">{hole}</div></div></div>'
        )
        thought = player.get("last_thought") or ""
        if player.get("thinking"):
            bubbles.append(
                f'<div class="bubble b{seat} thinking"><b>{_esc(player["name"])}</b> is thinking…</div>'
            )
        elif thought:
            bubbles.append(
                f'<div class="bubble b{seat}"><b>{_esc(player["name"])}:</b> {_esc(thought)}</div>'
            )

    board = _cards_html(snapshot.get("board") or [], slots=5)
    winner_banner = ""
    if snapshot.get("winners") and phase == "complete":
        winner_banner = f'<div class="winner-banner">★ {_esc(", ".join(snapshot["winners"]))} ★</div>'

    return f"""
<div class="casino">
  <div class="status">{_esc(status)}</div>
  {''.join(bubbles)}
  {''.join(seats)}
  <div class="felt">
    <div class="center">
      <div class="street">{_esc(street)}</div>
      <div class="pot">{_esc(pot_label)} ${pot:,}</div>
      <div class="board">{board}</div>
      {winner_banner}
    </div>
  </div>
</div>
"""
