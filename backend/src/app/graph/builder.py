"""Build and compile the travel agent graph (supervisor plan-then-execute)."""

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents.cost import cost
from app.agents.itinerary import itinerary
from app.agents.recommendation import recommendation
from app.agents.supervisor import supervisor
from app.graph.synthesis import synthesize
from app.schemas.state import InputState, OutputState, TravelState


def _next_step(
    state: dict[str, Any],
) -> Command[Literal["itinerary", "recommendation", "cost", "synthesize"]]:
    # Single shared router node. Reads the supervisor's plan and a cursor, then
    # dispatches to the next planned agent (advancing the cursor atomically), or
    # synthesize when the plan is exhausted. An empty plan (off-topic chat, or a
    # supervisor failure) skips the agents and goes straight to synthesize.
    # Routing + cursor advance live here so agent nodes never need to know about
    # the cursor (and can't forget to advance it on their error path).
    plan = state.get("plan") or []
    idx = state.get("step_index", 0)
    if idx >= len(plan):
        return Command(goto="synthesize")
    return Command(goto=plan[idx], update={"step_index": idx + 1})


def build_travel_graph():
    """Compile the travel graph.

    supervisor -> router -> itinerary/recommendation/cost (looped via router)
                     -> synthesize -> END

    The router follows every node, so all multi-agent orchestration is driven by
    the supervisor's ordered plan from one place.
    """
    graph = StateGraph(TravelState, input_schema=InputState, output_schema=OutputState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("router", _next_step)
    graph.add_node("itinerary", itinerary)
    graph.add_node("recommendation", recommendation)
    graph.add_node("cost", cost)
    graph.add_node("synthesize", synthesize)

    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "router")
    for src in ("itinerary", "recommendation", "cost"):
        graph.add_edge(src, "router")
    graph.add_edge("synthesize", END)
    return graph.compile()
