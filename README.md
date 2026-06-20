[Vietnamese](README-VI.md) | English

# Travel Agent

> A multi-agent travel advisor that plans itineraries, recommends stays & dining, and estimates trip costs from a single natural-language request.

A supervisor routes each turn to three specialist agents — itinerary, recommendation, cost — which call real data tools (Wikipedia, DuckDuckGo, Geoapify, live flight prices), then synthesizes one answer. The supervisor knows its three capabilities and **refuses honestly** when asked for anything outside them — bookings, visas, weather — instead of fabricating. Replies follow the user's language (Vietnamese, English, or otherwise).

Built with LangGraph, FastAPI, Vue 3, and a local Ollama model.

---

<video src="docs/demo.mp4" controls width="100%" style="max-width:800px;border-radius:8px"></video>

---

---

## Quickstart

**Prereqs:** Python 3.13 + [uv](https://docs.astral.sh/uv/), [bun](https://bun.sh/), [Ollama](https://ollama.com/).

```bash
# 1. Backend
cd backend && uv sync && cp .env.example .env
uv run uvicorn app.main:app --app-dir src --reload      # :8000

# 2. Frontend (new terminal)
cd frontend && bun install && bun run dev               # :5173

# 3. Model
ollama pull gemma4:12b-it-qat                           # set OLLAMA_MODEL in .env if different
```

Open **http://localhost:5173**. Full config (LLM, Geoapify key, DB paths) in [`backend/README.md`](backend/README.md).

---

## Go deeper

| Doc | What's inside |
|---|---|
| 📐 [Architecture](docs/architecture.md) | Graph design, capabilities, 4-action routing, honest refusal, tool-calling, multi-turn memory |
| 🔌 [API](docs/api.md) | REST + SSE endpoints, event sequence, request/response schemas |

---

## License

[MIT](LICENSE).
