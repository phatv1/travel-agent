"""Pydantic models for chat session persistence."""

from pydantic import BaseModel, Field


class ToolCallData(BaseModel):
    name: str
    label: str
    icon: str = "🔧"
    status: str
    input: dict | None = None
    output: dict | str | None = None
    # "node" for a graph node, "tool" for a tool called within a node.
    kind: str = "node"
    # Parent node name for tools (e.g. "itinerary"); None for nodes.
    node: str | None = None
    # Epoch milliseconds so the sidebar shows real durations on reload.
    # None for traces rebuilt from the final result (non-streaming path),
    # which has no timing information.
    started_at: int | None = None
    finished_at: int | None = None


class MessageOut(BaseModel):
    id: str
    role: str = Field(description="user | assistant")
    content: str = ""
    tool_calls: list[ToolCallData] | None = None
    error: str | None = None
    created_at: int


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: int
    updated_at: int


class SessionDetail(SessionSummary):
    messages: list[MessageOut] = []


class SessionTitleUpdate(BaseModel):
    title: str
