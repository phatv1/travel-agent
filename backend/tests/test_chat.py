import os
import tempfile

# Isolate the SQLite DB to a temp file for this test module.
_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["TRAVEL_DB_PATH"] = _DB

import anyio  # noqa: E402
import httpx2  # noqa: E402
import pytest  # noqa: E402
from langchain_core.messages import HumanMessage  # noqa: E402

from app.agents.supervisor import supervisor  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import sessions as repo  # noqa: E402

repo.init_db()

# Full-graph integration test: ~1-2 min on local Ollama. Opt-in so the default
# `pytest` run stays fast; enable with RUN_OLLAMA_TESTS=1.
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_OLLAMA_TESTS"),
    reason="set RUN_OLLAMA_TESTS=1 to run the Ollama integration test",
)


def test_chat_persists_and_returns_trace() -> None:
    message = "Đi Đà Nẵng 3 ngày, 2 người. Lên lịch, gợi ý quán ăn, ước chi phí."

    async def call() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post("/chat", json={"message": message})

    response = anyio.run(call)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    assert data["message_id"]
    assert data["final_answer"]
    assert data["itinerary"]["days"]
    assert data["tool_calls"] and len(data["tool_calls"]) == 5

    # Persistence: the session holds the user + assistant exchange and is autotitled.
    session = repo.get_session(data["session_id"])
    assert session is not None
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"
    assert session["title"] != "Cuộc trò chuyện mới"


def test_supervisor_orders_cost_last_and_skips_unscheduled() -> None:
    # Real-LLM contract that mock tests cannot prove: the supervisor's ordered
    # plan must honour the cost data-dependency (cost aggregates itinerary +
    # recommendations, so it must run last), never schedule an agent twice, and
    # emit only known agent names. Plus two semantic checks the model honours
    # reliably: a full request schedules all three; off-topic chat none.
    KNOWN = {"itinerary", "recommendation", "cost"}
    cases = [
        ("full", "Đi Đà Nẵng 5 ngày, 2 người. Lên lịch, gợi ý quán ăn, ước chi phí."),
        ("offtopic", "Cảm ơn bạn nhiều nhé!"),
    ]
    for label, msg in cases:
        out = supervisor({"messages": [HumanMessage(content=msg)]})
        steps = out.get("plan") or []

        assert all(s in KNOWN for s in steps), f"{label}: unknown step in {steps}"
        assert len(steps) == len(set(steps)), f"{label}: duplicate step in {steps}"
        if "cost" in steps:
            assert steps[-1] == "cost", f"{label}: cost must be last, got {steps}"

        if label == "full":
            assert set(steps) == KNOWN, f"full request should schedule all 3, got {steps}"
        else:  # offtopic
            assert steps == [], f"off-topic should schedule nothing, got {steps}"
