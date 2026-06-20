from enum import StrEnum
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

# Supervisor's routing decision this turn. Drives synthesis dispatch — the
# supervisor (which sees the full conversation) decides what to do, not a
# hard-coded field-presence check.
#   plan    — within the 3 capabilities (run agents)
#   clarify — wants to travel but missing core context
#   refuse  — outside the 3 capabilities, OR unsafe/adversarial
#   direct  — social / off-travel chat
type AgentAction = Literal["plan", "clarify", "direct", "refuse"]


class InputState(TypedDict):
    """External graph input. Callers only need to provide messages."""

    messages: Annotated[list[AnyMessage], add_messages]


class OutputState(TypedDict, total=False):
    """External graph output returned to API/frontend consumers.

    `errors` is surfaced here (not internal-only) so the API/frontend can show
    graceful partial-failure info instead of a flat 500. It is last-write-wins
    (no reducer): nodes manually accumulate within a turn (read state['errors'],
    append, return), and the supervisor resets it to [] at the start of each turn
    so failures don't leak across turns when a checkpointer is attached.
    """

    # messages lives in InputState only; redeclaring here (total=False)
    # would flip it to NotRequired and clash with the Required definition.
    itinerary: ItineraryState
    recommendations: RecommendationState
    cost_report: CostReportState

    final_answer: str

    errors: list[str]


class TravelState(InputState, OutputState, total=False):
    """Full internal LangGraph state.

    Reducers: messages uses add_messages; errors is last-write-wins (nodes
    accumulate manually within a turn, supervisor resets at turn start);
    trip_request + domain fields are last-write-wins.
    """

    trip_request: TripRequestState

    # Supervisor routing: the action this turn (plan/clarify/direct) + the
    # ordered agents to run + a cursor. _next_step dispatches by plan[step_index];
    # an empty plan (clarify/direct, or a supervisor failure) routes straight to
    # synthesize, which then dispatches on `action`.
    action: AgentAction
    plan: list[AgentStep]
    step_index: int
