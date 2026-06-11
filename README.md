# Pitchside

An agentic analyst for the 2026 FIFA World Cup. Ask it anything about the tournament and watch it work: the agent decides which tools it needs, chains them across multiple reasoning steps, and streams its full trace — tool calls included — into a live chat UI.

Built and operated during the tournament itself (June 11 – July 19, 2026).

**Ask:** *"Who's likely to win the USMNT's opener? Give me probabilities."*
**The agent:** calls `get_fixtures` to find the match (USA vs Paraguay, June 12, SoFi Stadium) → feeds both teams into `simulate_match`, a Dixon-Coles model → answers with grounded win/draw/loss probabilities, citing its own simulation.

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

### The three tools

- **`get_fixtures`** — adapter over football-data.org's World Cup feed with a bundled mock fallback (real opening-week fixtures), so the demo runs end to end with zero extra API keys. The agent receives an identical schema either way.
- **`simulate_match`** — a Dixon-Coles match model: per-team attack/defence multipliers drive Poisson goal expectations with the DC tau correction for low-score dependence. Outcome probabilities are computed analytically from the joint score matrix, so results are deterministic. Covers all 48 qualified teams with alias resolution (USA/USMNT, Turkey/Türkiye). Ratings here are illustrative tiers; the production version is fit by maximum likelihood in my [World Cup forecasting project](../) and this tool is designed to be pointed at that API instead.
- **`search_knowledge`** — RAG over a curated knowledge base (the 12 groups, format and advancement rules, the 16 venues, World Cup history). Markdown docs are chunked by heading, embedded locally with `all-MiniLM-L6-v2` (no embedding API cost), and searched via FAISS cosine similarity.

### Evals

Agent systems fail quietly — usually by calling the wrong tool or asserting facts their tools never returned. `evals/` measures both:

- **Tool-selection accuracy** — 8 golden questions, each annotated with the tools the agent *must* call (including a chained case that requires fixture lookup → simulation).
- **Groundedness** — deterministic keyword assertions on the final answer, plus an optional `--judge` flag that adds an LLM-judge faithfulness score (1–5) of the answer against the actual tool outputs.

Results write to `evals/results.json` so runs can be diffed across prompt or model changes. There's also a no-key pytest suite (`evals/test_units.py`) covering the simulator math, alias resolution, fixture filtering, and chunking.

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

Optional: add a free `FOOTBALL_DATA_API_KEY` from football-data.org to switch fixtures from bundled mock data to live scores.

```bash
# Tests and evals
cd backend
pytest evals/test_units.py        # deterministic, no key needed
python -m evals.run_evals         # full agent evals (needs key)
python -m evals.run_evals --judge # + LLM-judge faithfulness scoring
```

## Design notes

- **Visible reasoning.** The UI renders every tool call as a trace card — name, arguments, a one-line result summary, expandable raw JSON. Agent transparency is the demo.
- **Graceful degradation.** No football-data key → mock fixtures. Unknown team → structured error the agent can recover from, rather than an exception.
- **One streaming contract.** The backend emits typed events (`text`, `tool_call`, `tool_result`, `done`) over SSE; the frontend is a thin renderer of that event stream.

## Stack

Python · FastAPI · Anthropic API (tool use + streaming) · FAISS · sentence-transformers · NumPy · React · Vite
