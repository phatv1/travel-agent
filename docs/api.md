# API

REST + SSE endpoints for the Travel Agent backend. Base URL in dev: `http://localhost:8000`. Swagger UI at `/docs`.

---

## CORS

The backend allows `VITE_ORIGIN` (default `http://localhost:5173`). In dev the SSE stream is fetched **cross-origin directly from the backend**, not through the Vite proxy — the proxy buffers `text/event-stream` and would kill the live token stream. JSON endpoints still go through the proxy. In production (same origin) this is a no-op.

---

## Endpoints

| Method | Path | Purpose | Body / Param |
|---|---|---|---|
| `GET` | `/health` | Liveness | — |
| `GET` | `/sessions` | List session summaries | — |
| `POST` | `/sessions` | Create empty session | — |
| `GET` | `/sessions/{id}` | Session detail + messages | — |
| `PATCH` | `/sessions/{id}` | Rename | `{ "title": "..." }` |
| `DELETE` | `/sessions/{id}` | Delete session + messages | — |
| `POST` | `/chat` | Run graph, return full response | `ChatRequest` |
| `POST` | `/chat/stream` | Run graph as **SSE** (primary) | `ChatRequest` |

---

## `POST /chat/stream` (SSE) — the primary endpoint

Starts the graph and streams events. If `session_id` is omitted, a session is created and announced in the first `session` event.

### Event sequence

```
session                          ← { session_id } immediately
: ping                           ← heartbeat (proxy/keep-alive)
node_start   (supervisor)
node_end     (supervisor)        ← action + trip_request in output
node_start   (itinerary)         ← (one per planned agent)
tool_start   (list_attractions)
tool_end     (list_attractions)
tool_start   (get_place_info)
tool_end     (get_place_info)
node_end     (itinerary)
node_start   (recommendation) ...
node_start   (cost) ...
final                            ← repeated, token-by-token answer chunks
done                             ← { session_id, message_id, final_answer, errors? }
```

Clarify / direct / refuse turns still emit `node_start`/`node_end` for `supervisor`, then skip straight to `final` + `done` (no agents run).

### Event payloads

| Event | Key fields |
|---|---|
| `session` | `session_id` |
| `node_start` | `name`, `label`, `icon`, `started_at` (epoch ms) |
| `node_end` | `name`, `output`, `finished_at` |
| `tool_start` | `name`, `node` (parent), `input`, `started_at` |
| `tool_end` | `name`, `node`, `output`, `finished_at` |
| `final` | `final_answer` (a chunk or the accumulated string) |
| `error` | `message` |
| `done` | `session_id`, `message_id`, `final_answer`, `errors` |

Each line is `event: <name>\ndata: <json>\n\n`. The assistant message (with reconstructed trace + authoritative answer) is persisted **once**, at `done`.

### Example: stream with curl

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a 3-day Da Nang trip, 2 people, 15M VND budget"}'
```

`-N` disables curl's buffering so events print as they arrive.

---

## `POST /chat` (non-streaming)

Runs the graph end-to-end and returns the full `ChatResponse`. Useful for scripting or when streaming isn't needed.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Recommend hotels in Hoi An"}'
```

```json
{
  "session_id": "abc123",
  "message_id": "msg456",
  "final_answer": "Here are a few hotels in Hoi An...",
  "itinerary": null,
  "recommendations": { "...": "..." },
  "cost_report": null,
  "tool_calls": [ /* ToolCallData trace for the thinking panel */ ],
  "errors": null
}
```

---

## Schemas

### `ChatRequest`

| Field | Type | Notes |
|---|---|---|
| `message` | `str` | Required. The user's travel question. |
| `session_id` | `str \| null` | If null, a new session is created. |

### `ChatResponse`

| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | Created if request omitted it. |
| `message_id` | `str` | The persisted assistant message id. |
| `final_answer` | `str` | Natural-language answer. |
| `itinerary` | `dict \| null` | Day-by-day plan, if produced. |
| `recommendations` | `dict \| null` | Hotels/restaurants, if produced. |
| `cost_report` | `dict \| null` | Cost estimate, if produced. |
| `tool_calls` | `list[ToolCallData] \| null` | Trace for the thinking panel. |
| `errors` | `list[str] \| null` | Node-level errors, if any (graph never 500s on agent failure). |

### `ToolCallData`

| Field | Type | Notes |
|---|---|---|
| `name`, `label`, `icon` | `str` | Display. `icon` defaults to `🔧`. |
| `status` | `str` | `running` \| `done`. |
| `input` | `dict \| null` | Tool/node input. |
| `output` | `dict \| str \| null` | Tool/node output (JSON-string is decoded by the frontend). |
| `kind` | `str` | `node` \| `tool`. |
| `node` | `str \| null` | Parent node for tools. |
| `started_at`, `finished_at` | `int \| null` | Epoch ms, for real durations (not fake countdowns on reload). |

### Session models

| Model | Fields |
|---|---|
| `SessionSummary` | `id`, `title`, `created_at`, `updated_at` |
| `SessionDetail` | `SessionSummary` + `messages: list[MessageOut]` |
| `MessageOut` | `id`, `role` (`user` \| `assistant`), `content`, `tool_calls`, `error`, `created_at` |
| `SessionTitleUpdate` | `title` |

---

## Errors

| Status | When |
|---|---|
| `404` | `session_id` provided but not found (on `/chat`, `/chat/stream`, session endpoints). |
| `500` | Unhandled exception in the graph. A global handler returns `{"detail": "<msg>"}`. Agent-level failures are **not** 500s — they're captured into `errors` and the graph completes with a degraded answer. |

---

## Frontend integration notes

- Use `fetch` + a `ReadableStream` reader, not `EventSource` — EventSource is GET-only and we POST the `ChatRequest` body.
- Decode each chunk by splitting on `\n\n`, parsing `event:` and `data:` lines.
- For `final` events, treat `final_answer` as an accumulating string and re-render token-by-token (typewriter).
- Persist `started_at`/`finished_at` from the events so the thinking trace shows real durations on reload instead of fake countdowns.
