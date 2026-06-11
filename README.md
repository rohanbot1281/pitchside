# Pitchside

A chatbot that answers World Cup questions by actually going and getting the data instead of guessing. Ask it who wins the USMNT opener and it looks up the fixture, runs a match simulation, and gives you probabilities it can back up. You watch all of this happen live in the UI, tool calls included.

I built this during the 2026 World Cup itself, starting the day Mexico played South Africa in the opener. My other two World Cup projects predict things. This one talks, and it uses one of those models as a tool.

So when you ask "Who's likely to win the USMNT's opener?", the agent calls `get_fixtures`, finds USA vs Paraguay (June 12, SoFi Stadium), feeds both teams into `simulate_match`, and answers with the actual numbers from the simulation. It decides that chain on its own. Nothing in my code says "fixture questions need two tools."

## Architecture

```
┌─────────────┐   SSE stream    ┌──────────────────────────────────┐
│  React UI   │ ◄────────────── │  FastAPI                         │
│  chat +     │                 │  ┌────────────────────────────┐  │
│  tool trace │ ──────────────► │  │  Agent loop (Claude)       │  │
└─────────────┘   POST /chat    │  │  multi-step tool use       │  │
                                │  └──────┬─────────────────────┘  │
                                │         │ dispatch               │
                                │  ┌──────┴──────┬──────────────┐  │
                                │  │ get_fixtures│ simulate_    │  │
                                │  │ live adapter│ match        │  │
                                │  │ w/ mock     │ Dixon-Coles  │  │
                                │  │ fallback    │              │  │
                                │  ├─────────────┴──────────────┤  │
                                │  │ search_knowledge           │  │
                                │  │ FAISS + MiniLM embeddings  │  │
                                │  └────────────────────────────┘  │
                                └──────────────────────────────────┘
```

## The three tools

**`get_fixtures`** wraps football-data.org's World Cup feed, with bundled mock data (real opening-week fixtures) as a fallback. The demo runs end to end without a second API key, and the agent gets the same schema either way, so it never knows which source it hit.

**`simulate_match`** is a Dixon-Coles model: each team has attack and defence multipliers that drive Poisson goal expectations, with the tau correction for how often low scores like 0-0 and 1-1 actually happen. I compute outcome probabilities from the full joint score matrix instead of Monte Carlo, so the same matchup always returns the same numbers. All 48 qualified teams are covered, and team names resolve through aliases (USA, USMNT, Turkey, Türkiye all work). The ratings here are rough tiers I set by hand. The real version, fit by maximum likelihood on historical internationals, lives in my World Cup forecasting repo, and this tool is built to be pointed at that API instead.

**`search_knowledge`** is RAG over docs I wrote covering the 12 groups, the advancement rules, the 16 venues, and World Cup history. Docs get chunked by heading, embedded locally with all-MiniLM-L6-v2 (free, runs on CPU), and searched through FAISS with cosine similarity.

## Evals

Agents fail quietly. They call the wrong tool, or they state facts their tools never returned, and the answer still reads fine. The `evals/` folder measures both failure modes:

- **Tool selection**: 8 golden questions, each tagged with the tools the agent has to call. One of them requires chaining a fixture lookup into a simulation.
- **Groundedness**: keyword assertions on the final answer, plus an optional `--judge` flag that has a second model score how faithful the answer is to the actual tool outputs, 1 to 5.

Results land in `evals/results.json` so I can diff runs after changing the prompt or the model. There's also a pytest suite (`evals/test_units.py`) for the simulator math, alias resolution, fixture filtering, and chunking. That one needs no API key.

Worth admitting: the very first question I asked in the UI exposed a bug. The agent filtered fixtures by "USA" but the data says "United States", so the tool returned zero matches. The agent recovered by pulling the fixture from the knowledge base instead, which was cool to watch, but the trace made the bug obvious and I patched the filter to resolve aliases. That trace card UI earns its keep.

## Run it

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env        # add your ANTHROPIC_API_KEY
python -m app.rag.ingest          # build the FAISS index (one time, ~30s)
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Optional: a free `FOOTBALL_DATA_API_KEY` from football-data.org switches fixtures from mock data to live scores.

```bash
# Tests and evals
cd backend
pytest evals/test_units.py        # deterministic, no key needed
python -m evals.run_evals         # full agent evals (needs key)
python -m evals.run_evals --judge # adds LLM-judge faithfulness scoring
```

## Decisions I'd defend

- The UI shows every tool call as a card with the name, arguments, a one-line summary, and expandable raw JSON. Watching the agent work is the whole point of the demo.
- Things degrade instead of crashing. No football-data key? Mock fixtures. Unknown team name? The simulator returns a structured error the agent can read and recover from.
- The backend emits four event types over SSE (`text`, `tool_call`, `tool_result`, `done`) and the frontend just renders that stream. Keeping one contract made both sides simpler.

## Stack

Python, FastAPI, Anthropic API (tool use + streaming), FAISS, sentence-transformers, NumPy, React, Vite
