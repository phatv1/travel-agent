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


@pytest.fixture(autouse=True)
def _clean_tables():
    with repo._connect() as conn:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
    yield


def test_repo_add_message_autotitle_cascade() -> None:
    s = repo.create_session()
    assert s["title"] == "Cuộc trò chuyện mới"

    changed = repo.autotitle_if_default(s["id"], "Đi Đà Nẵng 3 ngày\nngười")
    assert changed is True
    retitled = repo.get_session(s["id"])
    assert retitled is not None
    assert retitled["title"] == "Đi Đà Nẵng 3 ngày người"

    repo.add_message(s["id"], role="user", content="hi")
    msg = repo.add_message(
        s["id"], role="assistant", content="hello", tool_calls=[{"name": "x"}]
    )
    assert msg["tool_calls"] == [{"name": "x"}]

    full = repo.get_session(s["id"])
    assert full is not None
    assert len(full["messages"]) == 2
    assert full["messages"][1]["tool_calls"] == [{"name": "x"}]

    # Title already set → autotitle is a no-op.
    assert repo.autotitle_if_default(s["id"], "other") is False

    assert repo.delete_session(s["id"]) is True
    assert repo.get_session(s["id"]) is None
    assert repo.delete_session(s["id"]) is False


def _client() -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://test")


def test_session_api_crud_and_404() -> None:
    async def run() -> None:
        async with _client() as c:
            created = (await c.post("/sessions")).json()
            assert created["title"] == "Cuộc trò chuyện mới"
            sid = created["id"]

            assert len((await c.get("/sessions")).json()) == 1

            detail = (await c.get(f"/sessions/{sid}")).json()
            assert detail["messages"] == []

            renamed = (await c.patch(f"/sessions/{sid}", json={"title": "Đà Nẵng"})).json()
            assert renamed["title"] == "Đà Nẵng"

            # Missing session → 404, not swallowed into 500 by the global handler.
            assert (await c.get("/sessions/nope")).status_code == 404

            assert (await c.delete(f"/sessions/{sid}")).status_code == 204
            assert (await c.get(f"/sessions/{sid}")).status_code == 404

    anyio.run(run)
