"""Build and compile the travel agent graph."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.cost import cost
from app.agents.itinerary import itinerary
from app.agents.recommendation import recommendation
from app.agents.supervisor import supervisor
from app.graph.synthesis import synthesize
from app.schemas.state import InputState, OutputState, TravelState


def _route_after_supervisor(state: dict[str, Any]) -> str:
    # Accepts any state dict (not full TravelState) because it only inspects
    # trip_request presence — keeps unit tests honest with partial states.
    # If the supervisor failed to produce a trip_request, skip the agents and go
    # straight to synthesis so the user gets a graceful message, not a 500.
    return "synthesize" if not state.get("trip_request") else "itinerary"


def build_travel_graph():
    """Compile the travel graph: supervisor → agents → synthesize.

    Agents self-skip (return {}) when their needs_* flag is False. The single
    conditional edge short-circuits to synthesis when the supervisor fails to
    parse the request, so a bad parse never crashes the graph.
    """
    graph = StateGraph(TravelState, input_schema=InputState, output_schema=OutputState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("itinerary", itinerary)
    graph.add_node("recommendation", recommendation)
    graph.add_node("cost", cost)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"itinerary": "itinerary", "synthesize": "synthesize"},
    )
    graph.add_edge("itinerary", "recommendation")
    graph.add_edge("recommendation", "cost")
    graph.add_edge("cost", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()
