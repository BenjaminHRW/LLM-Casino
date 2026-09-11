# AI Poker Casino

Local Streamlit dashboard for a **3-handed no-limit Texas Hold’em** table. Each seat is an AI: pick a model, paste that provider’s API key in the same seat menu, edit a persona prompt, then watch them play with live thought bubbles.

Every seat **requires an API key**. There is no mock player.

## Features

- Real Hold’em flow: blinds, hole cards, preflop / flop / turn / river betting, side pots, showdown
- Sidebar config per seat: name, model picker, **API key**, optional OpenAI-compatible base URL, buy-in, persona
- Green oval felt table: cards, pot, dealer/SB/BB badges, stacks
- Thought bubbles as each AI acts
- **Next Turn** — one action (or the next street / showdown)
- **Run Simulation** — play out the rest of the hand and update the UI as it goes

## Run locally

Python 3.10+ recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually <http://localhost:8501>).

In the sidebar, for each of the three seats:

1. Pick an **LLM model**
2. Paste the matching **API key** in the field directly under it
3. (GPT / Llama / o-series only) optionally set an API base URL

**Next Turn** and **Run Simulation** stay disabled until all three seats have a key.

## LLM keys

Keys are read from the seat menu first. On first load, empty fields are prefilled from env vars or `.streamlit/secrets.toml` if those are set.

| Seat model | Key field | Typical env var |
| --- | --- | --- |
| `gpt-*`, `o4-*`, `llama-*` | API key (+ optional base URL) | `OPENAI_API_KEY`, `OPENAI_BASE_URL` |
| name contains `claude` | Anthropic API key | `ANTHROPIC_API_KEY` |
| name contains `gemini` | Gemini API key | `GEMINI_API_KEY` |

Same OpenAI-compatible key can be pasted on every GPT seat, or use Groq / OpenRouter / Ollama by setting that seat’s base URL.

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
streamlit run app.py
```

## Tests

```bash
pip install pytest
pytest
```

## Layout

```
app.py                 Streamlit UI
poker/engine.py        Hold’em rules, pots, streets
poker/evaluator.py     5- and 7-card rankings
poker/llm.py           OpenAI / Anthropic / Gemini (per-seat keys)
poker/ui.py            Table HTML (felt, seats, bubbles)
poker/personas.py      Default names, models, prompts
```
