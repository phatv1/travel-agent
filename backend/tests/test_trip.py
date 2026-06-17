import pytest
from pydantic import ValidationError

from app.schemas.trip import TripRequest


def test_defaults_are_full_plan() -> None:
    trip = TripRequest()
    assert trip.needs_itinerary is True
    assert trip.needs_recommendations is True
    assert trip.needs_cost_estimation is True
    assert trip.destination is None
    assert trip.budget_preference is None


def test_needs_flags_are_independent() -> None:
    trip = TripRequest(
        destination="Đà Nẵng",
        needs_itinerary=True,
        needs_recommendations=False,
        needs_cost_estimation=False,
    )
    assert trip.needs_itinerary is True
    assert trip.needs_recommendations is False
    assert trip.needs_cost_estimation is False


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        TripRequest(destination="Đà Nẵng", bogus="x")  # type: ignore[call-arg]


def test_round_trip_stable() -> None:
    trip = TripRequest(destination="Đà Nẵng", needs_cost_estimation=False)
    assert TripRequest.model_validate(trip.model_dump()) == trip


def test_user_intent_removed() -> None:
    # Routing is now expressed via the three needs_* booleans, not an enum.
    assert "user_intent" not in TripRequest.model_fields
