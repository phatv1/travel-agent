"""SQLite persistence for chat sessions and messages."""

import json
import os
import sqlite3
import time
import uuid

DEFAULT_DB_PATH = "db.sqlite3"


def _db_path() -> str:
    return os.environ.get("TRAVEL_DB_PATH", DEFAULT_DB_PATH)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id         TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL DEFAULT '',
                tool_calls TEXT,
                error      TEXT,
                created_at INTEGER NOT NULL
            );
            """
        )


def _now() -> int:
    return int(time.time())


def list_sessions() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def create_session(title: str = "Cuộc trò chuyện mới") -> dict:
    sid = str(uuid.uuid4())
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (sid, title, now, now),
        )
    return {"id": sid, "title": title, "created_at": now, "updated_at": now}


def _messages_of(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, role, content, tool_calls, error, created_at "
        "FROM messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    return [_msg_dict(r) for r in rows]


def _msg_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "tool_calls": json.loads(row["tool_calls"]) if row["tool_calls"] else None,
        "error": row["error"],
        "created_at": row["created_at"],
    }


def get_session(session_id: str) -> dict | None:
    with _connect() as conn:
        s = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if s is None:
            return None
        result = dict(s)
        result["messages"] = _messages_of(conn, session_id)
        return result


def rename_session(session_id: str, title: str) -> dict | None:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, session_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return dict(row)


def delete_session(session_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cur.rowcount > 0


def add_message(
    session_id: str,
    role: str,
    content: str = "",
    tool_calls: list[dict] | None = None,
    error: str | None = None,
) -> dict:
    mid = str(uuid.uuid4())
    now = _now()
    tc_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, tool_calls, error, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mid, session_id, role, content, tc_json, error, now),
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    return {
        "id": mid,
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "error": error,
        "created_at": now,
    }


def autotitle_if_default(session_id: str, message: str) -> bool:
    """Set the session title from the first user message, only if still the default."""
    title = " ".join(message.strip().split())[:40] or "Cuộc trò chuyện mới"
    now = _now()
    with _connect() as conn:
        s = conn.execute("SELECT title FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if s is None or s["title"] != "Cuộc trò chuyện mới":
            return False
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, session_id),
        )
        return True
