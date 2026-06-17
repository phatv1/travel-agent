import os
import tempfile

# Isolate the SQLite DB to a temp file for this test module.
_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["TRAVEL_DB_PATH"] = _DB

import anyio  # noqa: E402
import httpx2  # noqa: E402
import pytest  # noqa: E402

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
