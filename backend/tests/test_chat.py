import os

import anyio
import httpx2
import pytest

from app.main import app

# Full-graph integration test: ~50-100s on local Ollama. Opt-in so the default
# `pytest` run stays fast; enable with RUN_OLLAMA_TESTS=1.
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_OLLAMA_TESTS"),
    reason="set RUN_OLLAMA_TESTS=1 to run the Ollama integration test",
)


def test_chat() -> None:
    message = "Đi Đà Nẵng 3 ngày, 2 người. Lên lịch, gợi ý quán ăn, ước chi phí."

    async def call() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post("/chat", json={"message": message})

    response = anyio.run(call)
    assert response.status_code == 200
    data = response.json()
    assert data["final_answer"]
    assert data["itinerary"]["days"]
