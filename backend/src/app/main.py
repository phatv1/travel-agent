"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.graph.runner import run_travel
from app.graph.trace import build_trace
from app.repositories import sessions as sessions_repo
from app.schemas.api import ChatRequest, ChatResponse
from app.schemas.session import SessionDetail, SessionSummary, SessionTitleUpdate


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sessions_repo.init_db()
    yield


app = FastAPI(title="Travel Agent API", lifespan=lifespan)


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

    result = await run_travel(request.message)
    trace = build_trace(request.message, result)
    assistant = sessions_repo.add_message(
        session_id,
        role="assistant",
        content=result.get("final_answer", ""),
        tool_calls=[t.model_dump() for t in trace],
    )

    return ChatResponse(
        session_id=session_id,
        message_id=assistant["id"],
        final_answer=result.get("final_answer", ""),
        itinerary=result.get("itinerary"),
        recommendations=result.get("recommendations"),
        cost_report=result.get("cost_report"),
        tool_calls=trace,
    )
