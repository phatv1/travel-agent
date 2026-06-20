# Backend

FastAPI app + LangGraph supervisor graph, running a local Ollama model. Entry point: `src/app/main.py`.

> See the [root README](../README.md) for the elevator pitch, [architecture.md](../docs/architecture.md) for the full design (graph, routing, reasoning), [api.md](../docs/api.md) for endpoints.

---

## Module map

```
src/app/
├── agents/          # supervisor + 3 domain agents + _llm helper
│   ├── supervisor.py     # capability-aware routing (4 actions)
│   ├── itinerary.py recommendation.py cost.py
│   └── _llm.py           # invoke_structured (retry) + error_label
├── graph/           # graph wiring + streaming
│   ├── builder.py        # supervisor → router → agents → synthesize
│   ├── runner.py stream.py synthesis.py trace.py
├── tools/           # real data sources + tool-calling loop
│   ├── search.py (Wiki+DDG) geo.py (Geoapify) flight.py (fast-flights)
│   ├── cost.py loop.py
├── schemas/         # Pydantic: state, trip, itinerary, recommendation, cost, api, session
├── repositories/    # sessions.py — SQLite behind small fns
├── llms/            # factory.py — Ollama (env-driven model/thinking/temperature)
└── main.py          # FastAPI app, lifespan (checkpointer), endpoints
```

---

## Dev commands

```bash
uv sync                                                 # install deps
uv run uvicorn app.main:app --app-dir src --reload       # dev server → :8000
uv run pytest                                           # fast tests (mocked LLM)
RUN_OLLAMA_TESTS=1 uv run pytest tests/test_generalization.py   # 36 real-LLM cases
uv run ruff check .                                     # lint
uv run ruff check . --fix                               # lint + autofix
uv run pyright                                          # type check (0 errors enforced)
```

Swagger UI: http://localhost:8000/docs

---

## Environment

Copy `.env.example` to `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_MODEL` | `gemma4:12b-it-qat` | Model name (must be `ollama pull`ed). |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server. |
| `OLLAMA_THINKING` | `off` | `off` \| `auto` \| `on` \| `low` \| `medium` \| `high`. |
| `OLLAMA_TEMPERATURE` | `0.2` | Sampling temperature. |
| `GEOAPIFY_API_KEY` | _(empty)_ | For recommendation POIs. Empty → graceful fallback. |
| `VITE_ORIGIN` | `http://localhost:5173` | CORS origin for the dev frontend. |
| `TRAVEL_DB_PATH` | `db.sqlite3` | Sessions/messages DB (auto-created). |
| `TRAVEL_CHECKPOINT_DB_PATH` | `checkpoint.sqlite3` | Multi-turn memory (auto-created). |

> `.env` is gitignored. Never commit real keys.
