"""Run the travel graph for a single chat request."""

from langchain_core.messages import HumanMessage

from app.graph.builder import build_travel_graph

# Compiled once at import; reuse across requests.
_travel_graph = build_travel_graph()


async def run_travel(message: str) -> dict:
    """Invoke the travel graph and return the OutputState-shaped result."""
    return await _travel_graph.ainvoke({"messages": [HumanMessage(content=message)]})
