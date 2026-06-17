"""Build and compile the travel agent graph."""

from langgraph.graph import END, START, StateGraph

from app.agents.cost import cost
from app.agents.itinerary import itinerary
from app.agents.recommendation import recommendation
from app.agents.supervisor import supervisor
from app.graph.synthesis import synthesize
from app.schemas.state import InputState, OutputState, TravelState


def build_travel_graph():
    """Compile the linear travel graph: supervisor → agents → synthesize.

    Agents self-skip (return {}) when their needs_* flag is False, so a linear
    graph is correct without conditional routing.
    """
    graph = StateGraph(TravelState, input_schema=InputState, output_schema=OutputState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("itinerary", itinerary)
    graph.add_node("recommendation", recommendation)
    graph.add_node("cost", cost)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "itinerary")
    graph.add_edge("itinerary", "recommendation")
    graph.add_edge("recommendation", "cost")
    graph.add_edge("cost", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()
