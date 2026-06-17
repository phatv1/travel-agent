"""Tests for node-level error handling and supervisor short-circuit (no Ollama).

Covers Plan #2: a bad structured-output parse must never crash the graph into a
500; failed nodes record an error and skip, and a supervisor failure routes
straight to a graceful synthesis message.
"""

from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel

from app.agents import itinerary as itinerary_module
from app.agents import supervisor as supervisor_module
from app.agents._llm import error_label, invoke_structured
from app.graph.builder import _route_after_supervisor, build_travel_graph
from app.schemas.cost import CostReport
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
        "trip_request": TripRequest(destination="Đà Nẵng", needs_itinerary=True).model_dump(),
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
    assert out["errors"] and out["errors"][0].startswith("supervisor:")


def test_route_after_supervisor_skips_when_no_trip_request() -> None:
    assert _route_after_supervisor({}) == "synthesize"
    assert _route_after_supervisor({"trip_request": {"destination": "Đà Nẵng"}}) == "itinerary"


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
