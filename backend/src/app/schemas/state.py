from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import AnyMessage, add_messages


class AgentName(StrEnum):
    SUPERVISOR = "supervisor_agent"
    ITINERARY = "itinerary_agent"
    RECOMMENDATION = "recommendation_agent"
    COST = "cost_agent"
    END = "end"


class TravelState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]

    trip_request: dict[str, Any]

    itinerary: dict[str, Any]
    recommendations: dict[str, Any]
    cost_report: dict[str, Any]

    next_agent: AgentName

    final_answer: str
    errors: list[str]
