"""Run the travel graph for a single chat request."""

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph


async def run_travel(graph: CompiledStateGraph, message: str, thread_id: str) -> dict:
    """Invoke the graph and return the OutputState-shaped result.

    ``thread_id`` (= session_id) keys the checkpointer so the full TravelState —
    including message history — persists across turns, giving the supervisor the
    prior conversation when resolving follow-ups.
    """
    return await graph.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": thread_id}},
    )
