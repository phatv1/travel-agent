"""Multi-turn memory tests: the checkpointer persists history across turns.

Covers the core of the memory feature: the same ``thread_id`` (= session_id)
accumulates message history so a follow-up like "thêm 1 ngày nữa" is resolved
against the prior conversation, not seen in isolation.

Uses the in-memory checkpointer (production uses ``AsyncSqliteSaver``). The graph
behavior with respect to multi-turn state is identical regardless of the saver
backend — this isolates the multi-turn LOGIC from storage I/O.
"""

from types import SimpleNamespace
from typing import cast

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from app.agents import supervisor as supervisor_module
from app.agents.supervisor import SupervisorDecision
from app.graph import synthesis as synthesis_module
from app.graph.builder import build_travel_graph
from app.schemas.state import InputState
from app.schemas.trip import TripRequest


def _cfg(thread_id: str) -> RunnableConfig:
    """Typed RunnableConfig for a checkpointed thread (avoids inline dict typing)."""
    return {"configurable": {"thread_id": thread_id}}


def _wire_direct_reply(monkeypatch) -> None:
    """Mock supervisor (empty plan) + synthesis LLM so turns run without Ollama."""
    monkeypatch.setattr(
        supervisor_module,
        "invoke_structured",
        lambda *a, **k: SupervisorDecision(
            action="direct",
            trip_request=TripRequest(destination="Đà Nẵng", time_preference="3 ngày"),
            steps=[],  # direct-reply path -> synthesize without domain agents
        ),
    )
    monkeypatch.setattr(
        synthesis_module,
        "get_llm",
        lambda: SimpleNamespace(invoke=lambda _msgs: SimpleNamespace(content="ok")),
    )


def test_history_accumulates_across_turns_under_same_thread(monkeypatch) -> None:
    # Capture the messages each supervisor turn actually saw.
    seen: list[list] = []

    def _supervisor(*args, **_kwargs):
        seen.append(list(args[2]))  # [SystemMessage, *conversation]
        return SupervisorDecision(
            action="direct",
            trip_request=TripRequest(destination="Đà Nẵng", time_preference="3 ngày"),
            steps=[],
        )

    monkeypatch.setattr(supervisor_module, "invoke_structured", _supervisor)
    monkeypatch.setattr(
        synthesis_module,
        "get_llm",
        lambda: SimpleNamespace(invoke=lambda _msgs: SimpleNamespace(content="ok")),
    )

    graph = build_travel_graph(checkpointer=MemorySaver())
    cfg = _cfg("trip-1")

    graph.invoke({"messages": [HumanMessage(content="Đà Nẵng 3 ngày")]}, config=cfg)
    graph.invoke({"messages": [HumanMessage(content="thêm 1 ngày")]}, config=cfg)

    # Turn 1 saw only turn 1's user message (besides the system prompt).
    turn1 = [getattr(m, "content", "") for m in seen[0]]
    assert any("Đà Nẵng 3 ngày" in c for c in turn1)

    # Turn 2 saw BOTH turns — and turn 1's assistant reply (AIMessage) is in
    # history too, proving synthesize's AIMessage is checkpointed. Without it,
    # follow-ups would lose the prior answer's context.
    turn2 = seen[1]
    turn2_contents = [getattr(m, "content", "") for m in turn2]
    assert any("Đà Nẵng 3 ngày" in c for c in turn2_contents)
    assert any("thêm 1 ngày" in c for c in turn2_contents)
    assert any(isinstance(m, AIMessage) for m in turn2)

    # The checkpointed thread holds all 4 messages: u1, a1, u2, a2.
    snapshot = graph.get_state(cfg)
    assert len(snapshot.values["messages"]) == 4


def test_threads_are_isolated(monkeypatch) -> None:
    # Different thread_id => independent conversations; thread B must NOT see
    # thread A's history.
    _wire_direct_reply(monkeypatch)
    graph = build_travel_graph(checkpointer=MemorySaver())

    graph.invoke(
        {"messages": [HumanMessage(content="Đà Nẵng 3 ngày")]}, config=_cfg("A")
    )
    graph.invoke(
        {"messages": [HumanMessage(content="Hà Nội 2 ngày")]}, config=_cfg("B")
    )

    # Thread B's checkpoint has only its own 2 messages — none from A.
    msgs = graph.get_state(_cfg("B")).values["messages"]
    assert len(msgs) == 2
    assert "Hà Nội 2 ngày" in msgs[0].content
    assert all("Đà Nẵng" not in getattr(m, "content", "") for m in msgs)


def test_errors_do_not_leak_across_turns(monkeypatch) -> None:
    # Seed an errors entry on turn 1; the supervisor resets it to [] at turn
    # start, so neither turn persists the failure. last-write-wins (no reducer)
    # is what makes this safe with a checkpointer attached.
    _wire_direct_reply(monkeypatch)
    graph = build_travel_graph(checkpointer=MemorySaver())
    cfg = _cfg("err-1")

    # Seed an errors entry directly into the checkpointed state. input_schema
    # filters extra keys, so use update_state (with as_node so it persists).
    graph.update_state(cfg, {"errors": ["stale failure"]}, as_node="supervisor")
    assert graph.get_state(cfg).values.get("errors", []) == ["stale failure"]

    graph.invoke(
        cast(InputState, {"messages": [HumanMessage(content="turn 1")]}), config=cfg
    )
    assert graph.get_state(cfg).values.get("errors", []) == []

    graph.invoke(
        cast(InputState, {"messages": [HumanMessage(content="turn 2")]}), config=cfg
    )
    assert graph.get_state(cfg).values.get("errors", []) == []


def test_stream_extracts_final_answer_when_synthesize_returns_aimessage() -> None:
    # Regression: synthesize returns {"final_answer": str, "messages": [AIMessage]}
    # so the checkpointer persists the assistant reply. The raw AIMessage makes
    # the dict non-JSON-serializable; _safe_jsonable must recurse (not stringify
    # the whole dict) or _extract_final_answer returns None and the chat bubble
    # renders empty.
    from langchain_core.messages import AIMessage

    from app.graph.stream import _extract_final_answer, _safe_jsonable

    raw = {
        "final_answer": "Để mình tư vấn chính xác nhất...",
        "messages": [AIMessage(content="Để mình tư vấn chính xác nhất...")],
    }

    safe = _safe_jsonable(raw)
    # The dict structure must survive (not collapse to a repr string).
    assert isinstance(safe, dict)
    assert safe["final_answer"] == "Để mình tư vấn chính xác nhất..."
    # And the answer must extract from the raw output.
    assert _extract_final_answer(raw) == "Để mình tư vấn chính xác nhất..."
