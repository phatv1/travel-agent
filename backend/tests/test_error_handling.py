"""Tests for node-level error handling and supervisor short-circuit (no Ollama).

Covers Plan #2: a bad structured-output parse must never crash the graph into a
500; failed nodes record an error and skip, and a supervisor failure routes
straight to a graceful synthesis message.
"""

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel

from app.agents import cost as cost_module
from app.agents import itinerary as itinerary_module
from app.agents import supervisor as supervisor_module
from app.agents._llm import error_label, invoke_structured
from app.agents.supervisor import SupervisorDecision
from app.graph import synthesis as synthesis_module
from app.graph.builder import _next_step, build_travel_graph
from app.schemas.cost import CostReport
from app.schemas.itinerary import ItineraryPlan
from app.schemas.state import TravelState
from app.schemas.trip import TripRequest


class _FakeExtractor:
    """with_structured_output() result: pops queued responses (return or raise)."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)

    def invoke(self, messages: Sequence[BaseMessage]) -> object:
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeLLM:
    def __init__(self, responses: list) -> None:
        self._responses = responses

    def with_structured_output(self, schema: type[BaseModel]) -> Any:
        return _FakeExtractor(self._responses)


def test_invoke_structured_raises_after_retries() -> None:
    llm = _FakeLLM([ValueError("boom"), ValueError("boom")])
    with pytest.raises(ValueError, match="boom"):
        invoke_structured(llm, CostReport, [], retries=1)


def test_invoke_structured_succeeds_after_one_failure() -> None:
    llm = _FakeLLM([ValueError("transient"), {"summary": "ok", "items": []}])
    report = invoke_structured(llm, CostReport, [], retries=1)
    assert isinstance(report, CostReport)
    assert report.summary == "ok"


def test_error_label_is_short_and_single_line() -> None:
    label = error_label("itinerary", ValueError("a\nb" * 50))
    assert label.startswith("itinerary: ValueError:")
    assert "\n" not in label
    assert len(label) <= 200


def test_itinerary_node_records_error(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("parse failed")

    monkeypatch.setattr(itinerary_module, "invoke_structured", boom)
    state: TravelState = {
        "trip_request": TripRequest(destination="Đà Nẵng").model_dump(),
        "messages": [],
    }
    out = itinerary_module.itinerary(state)
    assert "itinerary" not in out
    assert out["errors"] and out["errors"][0].startswith("itinerary:")


def test_supervisor_node_records_error(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(supervisor_module, "invoke_structured", boom)
    state: TravelState = {"messages": [HumanMessage(content="hi")]}
    out = supervisor_module.supervisor(state)
    assert "trip_request" not in out
    assert out["plan"] == []
    assert out["errors"] and out["errors"][0].startswith("supervisor:")


def test_supervisor_node_emits_plan(monkeypatch) -> None:
    decision = SupervisorDecision(
        trip_request=TripRequest(destination="Đà Nẵng"),
        steps=["itinerary", "cost"],
    )
    monkeypatch.setattr(supervisor_module, "invoke_structured", lambda *a, **k: decision)
    state: TravelState = {"messages": [HumanMessage(content="Đà Nẵng 5 ngày")]}
    out = supervisor_module.supervisor(state)
    assert out["plan"] == ["itinerary", "cost"]
    assert out["step_index"] == 0
    assert out["trip_request"]["destination"] == "Đà Nẵng"


def test_next_step_empty_plan_goes_to_synthesize() -> None:
    assert _next_step({}).goto == "synthesize"
    assert _next_step({"plan": [], "step_index": 0}).goto == "synthesize"


def test_next_step_dispatches_and_advances_cursor() -> None:
    cmd = _next_step({"plan": ["itinerary", "cost"], "step_index": 0})
    assert cmd.goto == "itinerary"
    assert cmd.update == {"step_index": 1}


def test_next_step_at_end_goes_to_synthesize() -> None:
    assert _next_step({"plan": ["recommendation"], "step_index": 1}).goto == "synthesize"


def test_graph_supervisor_failure_short_circuits(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("bad parse")

    monkeypatch.setattr(supervisor_module, "invoke_structured", boom)
    graph = build_travel_graph()
    result = graph.invoke({"messages": [HumanMessage(content="gì đây")]})

    assert result.get("final_answer")
    assert "itinerary" not in result
    assert "recommendations" not in result
    assert "cost_report" not in result
    assert any("supervisor" in e for e in result.get("errors", []))


def test_graph_runs_ordered_plan_and_skips_unscheduled(monkeypatch) -> None:
    # Plan = [itinerary, cost]. The router must run both in order and never reach
    # recommendation (not scheduled). All LLM calls mocked -> no Ollama.
    monkeypatch.setattr(
        supervisor_module,
        "invoke_structured",
        lambda *a, **k: SupervisorDecision(
            trip_request=TripRequest(destination="Đà Nẵng", time_preference="5 ngày"),
            steps=["itinerary", "cost"],
        ),
    )
    monkeypatch.setattr(
        itinerary_module,
        "invoke_structured",
        lambda *a, **k: ItineraryPlan(destination="Đà Nẵng", summary="5 ngày"),
    )
    monkeypatch.setattr(
        cost_module,
        "invoke_structured",
        lambda *a, **k: CostReport(summary="ok"),
    )
    # cost agent now does a tool-gathering phase before invoke_structured; bypass it
    # so the test stays fast and free of real LLM/tool calls.
    monkeypatch.setattr(
        cost_module, "gather_via_tools", lambda llm, tools, messages, **kw: messages
    )
    monkeypatch.setattr(
        synthesis_module,
        "get_llm",
        lambda: SimpleNamespace(invoke=lambda msgs: SimpleNamespace(content="tóm tắt")),
    )

    graph = build_travel_graph()
    result = graph.invoke({"messages": [HumanMessage(content="Đà Nẵng 5 ngày")]})

    assert result.get("itinerary")
    assert result.get("cost_report")
    assert not result.get("recommendations")
    assert result.get("final_answer") == "tóm tắt"


def test_synthesize_asks_for_missing_required_fields() -> None:
    synthesize = synthesis_module.synthesize

    def answer(trip: TripRequest) -> str:
        return synthesize({"trip_request": trip.model_dump(), "messages": []})["final_answer"]

    # destination present, time missing -> clarify lists time + optional fields,
    # and asks whether the user wants to add more (comprehensive first-time prompt).
    text = answer(TripRequest(destination="Đà Nẵng")).lower()
    assert "thời gian" in text
    assert "tùy chọn" in text  # optional fields surfaced even when only required missing
    assert "bổ sung" in text

    # time present, destination missing -> clarify lists destination + optional.
    text = answer(TripRequest(time_preference="5 ngày")).lower()
    assert "điểm đến" in text

    # both required missing but a travel field present (companions) -> list both.
    text = answer(TripRequest(companions="2 người")).lower()
    assert "điểm đến" in text
    assert "thời gian" in text
    # companions is provided, so it must NOT be re-asked as missing.
    assert "số người" not in text
