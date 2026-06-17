import pytest
from pydantic import ValidationError

from app.schemas.itinerary import DayPlan, ItineraryPlan, ScheduleItem


def test_schedule_item_text_required() -> None:
    with pytest.raises(ValidationError):
        ScheduleItem()  # type: ignore[call-arg]


def test_schedule_item_time_slot_literal() -> None:
    item = ScheduleItem(text="Biển Mỹ Khê", time_slot="morning")
    assert item.time_slot == "morning"
    with pytest.raises(ValidationError):
        ScheduleItem(text="x", time_slot="midnight")  # type: ignore[arg-type]


def test_day_plan_required_fields_and_defaults() -> None:
    day = DayPlan(day=1, title="Biển Mỹ Khê")
    assert day.day == 1
    assert day.schedule == []
    assert day.notes == []


def test_day_plan_day_and_title_required() -> None:
    with pytest.raises(ValidationError):
        DayPlan(day=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        DayPlan(title="x")  # type: ignore[call-arg]


def test_itinerary_plan_defaults() -> None:
    plan = ItineraryPlan(destination="Đà Nẵng", summary="5 ngày")
    assert plan.days == []
    assert plan.assumptions == []


def test_itinerary_plan_required_fields_missing() -> None:
    with pytest.raises(ValidationError):
        ItineraryPlan(destination="Đà Nẵng")  # type: ignore[call-arg]


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        ScheduleItem(text="x", bogus=1)  # type: ignore[call-arg]


def test_round_trip_stable() -> None:
    plan = ItineraryPlan(
        destination="Đà Nẵng",
        summary="5 ngày",
        days=[DayPlan(day=1, title="t", schedule=[ScheduleItem(text="a")])],
    )
    assert ItineraryPlan.model_validate(plan.model_dump()) == plan
