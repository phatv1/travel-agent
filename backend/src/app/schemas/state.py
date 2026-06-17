from enum import StrEnum
from operator import add
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import AnyMessage, add_messages


class AgentName(StrEnum):
    SUPERVISOR = "supervisor_agent"
    ITINERARY = "itinerary_agent"
    RECOMMENDATION = "recommendation_agent"
    COST = "cost_agent"
    END = "end"


# Domain results are stored as JSON-serializable dicts. Node boundary:
# read via Model.model_validate(state["field"]), write via model.model_dump().
type TripRequestState = dict[str, Any]
type ItineraryState = dict[str, Any]
type RecommendationState = dict[str, Any]
type CostReportState = dict[str, Any]

# Agent node names the supervisor may schedule this turn. Drives _next_step routing.
type AgentStep = Literal["itinerary", "recommendation", "cost"]


class InputState(TypedDict):
    """External graph input. Callers only need to provide messages."""

    messages: Annotated[list[AnyMessage], add_messages]


class OutputState(TypedDict, total=False):
    """External graph output returned to API/frontend consumers.

    `errors` is surfaced here (not internal-only) so the API/frontend can show
    graceful partial-failure info instead of a flat 500.
    """

    # messages lives in InputState only; redeclaring here (total=False)
    # would flip it to NotRequired and clash with the Required definition.
    itinerary: ItineraryState
    recommendations: RecommendationState
    cost_report: CostReportState

    final_answer: str

    errors: Annotated[list[str], add]


class TravelState(InputState, OutputState, total=False):
    """Full internal LangGraph state.

    Reducers: messages uses add_messages; errors accumulates via operator.add
    (inherited from OutputState, written by multiple nodes); domain fields are
    last-write-wins.
    """

    trip_request: TripRequestState

    # Supervisor routing: ordered agents to run this turn + a cursor. _next_step
    # dispatches by plan[step_index]; an empty plan (off-topic chat, or a
    # supervisor failure) routes straight to synthesize.
    plan: list[AgentStep]
    step_index: int
