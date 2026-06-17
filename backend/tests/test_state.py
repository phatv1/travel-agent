import typing
from operator import add

from langgraph.graph.message import add_messages

from app.schemas.state import InputState, OutputState, TravelState


def test_travel_state_has_all_keys() -> None:
    hints = typing.get_type_hints(TravelState, include_extras=True)
    assert set(hints) == {
        "messages",
        "itinerary",
        "recommendations",
        "cost_report",
        "final_answer",
        "trip_request",
        "plan",
        "step_index",
        "errors",
    }


def test_messages_reducer_inherited_into_travel_state() -> None:
    # messages is declared once in InputState but must carry its reducer
    # into TravelState via inheritance.
    hints = typing.get_type_hints(TravelState, include_extras=True)
    assert typing.get_args(hints["messages"])[1:] == (add_messages,)


def test_errors_uses_accumulating_reducer() -> None:
    # Multiple nodes write errors, so it must accumulate (not last-writer-wins).
    hints = typing.get_type_hints(TravelState, include_extras=True)
    assert typing.get_args(hints["errors"])[1:] == (add,)


def test_output_state_exposes_errors_but_keeps_internals_private() -> None:
    hints = typing.get_type_hints(OutputState, include_extras=True)
    # errors is surfaced to consumers for graceful partial-failure display.
    assert "errors" in hints
    assert typing.get_args(hints["errors"])[1:] == (add,)
    # trip_request is internal-only; messages lives in InputState to avoid a
    # Required/NotRequired clash.
    assert "trip_request" not in hints
    assert "messages" not in hints


def test_input_state_is_minimal() -> None:
    assert set(typing.get_type_hints(InputState, include_extras=True)) == {"messages"}
