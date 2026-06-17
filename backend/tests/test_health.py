import anyio
import httpx2

from app.main import app


def test_health() -> None:
    async def call() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/health")

    response = anyio.run(call)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
