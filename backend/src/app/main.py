"""FastAPI application entrypoint."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.graph.builder import build_travel_graph
from app.graph.runner import run_travel
from app.graph.stream import stream_travel
from app.graph.trace import build_trace
from app.repositories import sessions as sessions_repo
from app.schemas.api import ChatRequest, ChatResponse
from app.schemas.session import SessionDetail, SessionSummary, SessionTitleUpdate


def _checkpoint_db_path() -> str:
    # Separate from the sessions DB: the checkpoint store owns its own schema
    # (checkpoints/writes/migrations) and lifecycle, so keeping it isolated
    # avoids coupling conversation memory to message persistence.
    return os.environ.get("TRAVEL_CHECKPOINT_DB_PATH", "checkpoint.sqlite3")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sessions_repo.init_db()
    # Build the graph once with an async SQLite checkpointer. thread_id
    # (= session_id, passed per request) keys multi-turn memory: the full
    # TravelState, including message history, persists across turns so the
    # supervisor can resolve follow-ups against the prior conversation.
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_db_path()) as saver:
        await saver.setup()
        app.state.travel_graph = build_travel_graph(checkpointer=saver)
        yield


app = FastAPI(title="Travel Agent API", lifespan=lifespan)

# Dev: SSE is read directly from the backend (the Vite proxy buffers text/event-stream,
# which would kill the live token stream), so the frontend calls /chat/stream
# cross-origin. JSON endpoints still go through the proxy. In production both are
# same-origin and this is a no-op.
_allowed_origin = os.getenv("VITE_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sessions", response_model=list[SessionSummary])
def list_sessions() -> list[SessionSummary]:
    return [SessionSummary(**s) for s in sessions_repo.list_sessions()]


@app.post("/sessions", response_model=SessionSummary, status_code=201)
def create_session() -> SessionSummary:
    return SessionSummary(**sessions_repo.create_session())


@app.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: str) -> SessionDetail:
    s = sessions_repo.get_session(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetail(**s)


@app.patch("/sessions/{session_id}", response_model=SessionSummary)
def rename_session(session_id: str, update: SessionTitleUpdate) -> SessionSummary:
    s = sessions_repo.rename_session(session_id, update.title)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionSummary(**s)


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str) -> None:
    sessions_repo.delete_session(session_id)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Stream the travel graph as Server-Sent Events.

    Flow per event: node_start -> (tool_start -> tool_end)* -> node_end, repeated
    per agent; then token events for the final answer; then a `done` event with
    session/message ids. The assistant message is persisted once, after the
    graph finishes, carrying the reconstructed trace and authoritative answer.
    """
    if request.session_id:
        session_id = request.session_id
        if sessions_repo.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session_id = sessions_repo.create_session()["id"]

    sessions_repo.add_message(session_id, role="user", content=request.message)
    sessions_repo.autotitle_if_default(session_id, request.message)

    graph = app.state.travel_graph

    async def _generate() -> AsyncIterator[str]:
        def sse(event: str, payload: dict) -> str:
            body = json.dumps(payload, ensure_ascii=False, default=str)
            return f"event: {event}\ndata: {body}\n\n"

        # Tell the client which session this stream belongs to immediately, plus a
        # heartbeat so proxies/clients don't time out on slow LLM steps.
        yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"
        yield ": ping\n\n"

        trace: list[dict] = []  # reconstructed ToolCallData-shaped steps for persistence
        final_answer = ""
        error_msg: str | None = None

        async for etype, payload in stream_travel(graph, request.message, session_id):
            yield sse(etype, payload)

            if etype == "node_start":
                trace.append(
                    {
                        "name": payload["name"],
                        "label": payload.get("label", ""),
                        "icon": payload.get("icon", ""),
                        "status": "running",
                        "input": {},
                        "kind": "node",
                        "started_at": payload.get("started_at"),
                    }
                )
            elif etype == "node_end":
                for step in reversed(trace):
                    if step["name"] == payload["name"] and step.get("status") == "running":
                        step["status"] = "done"
                        step["output"] = payload.get("output")
                        step["finished_at"] = payload.get("finished_at")
                        break
            elif etype == "tool_start":
                trace.append(
                    {
                        "name": payload["name"],
                        "label": payload["name"],
                        "icon": "🔧",
                        "status": "running",
                        "input": payload.get("input"),
                        "kind": "tool",
                        "node": payload.get("node"),
                        "started_at": payload.get("started_at"),
                    }
                )
            elif etype == "tool_end":
                for step in reversed(trace):
                    if (
                        step.get("kind") == "tool"
                        and step["name"] == payload["name"]
                        and step.get("node") == payload.get("node")
                        and step.get("status") == "running"
                    ):
                        step["status"] = "done"
                        step["output"] = payload.get("output")
                        step["finished_at"] = payload.get("finished_at")
                        break
            elif etype == "final":
                final_answer = payload.get("final_answer", "")
            elif etype == "error":
                error_msg = payload.get("message", "")

        # Persist the assistant turn once, with the live trace + authoritative answer.
        assistant = sessions_repo.add_message(
            session_id,
            role="assistant",
            content=final_answer,
            tool_calls=trace if trace else None,
            error=error_msg,
        )

        yield sse(
            "done",
            {
                "session_id": session_id,
                "message_id": assistant["id"],
                "final_answer": final_answer,
                "errors": [error_msg] if error_msg else None,
            },
        )

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering if behind one
            "Connection": "keep-alive",
        },
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if request.session_id:
        session_id = request.session_id
        if sessions_repo.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session_id = sessions_repo.create_session()["id"]

    sessions_repo.add_message(session_id, role="user", content=request.message)
    sessions_repo.autotitle_if_default(session_id, request.message)

    graph = app.state.travel_graph
    result = await run_travel(graph, request.message, session_id)
    errors = result.get("errors")
    trace = build_trace(request.message, result)
    assistant = sessions_repo.add_message(
        session_id,
        role="assistant",
        content=result.get("final_answer", ""),
        tool_calls=[t.model_dump() for t in trace],
        error="; ".join(errors) if errors else None,
    )

    return ChatResponse(
        session_id=session_id,
        message_id=assistant["id"],
        final_answer=result.get("final_answer", ""),
        itinerary=result.get("itinerary"),
        recommendations=result.get("recommendations"),
        cost_report=result.get("cost_report"),
        tool_calls=trace,
        errors=errors or None,
    )
