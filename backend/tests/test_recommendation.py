import pytest
from pydantic import ValidationError

from app.schemas.recommendation import RecommendationItem, RecommendationPlan


def test_required_fields() -> None:
    item = RecommendationItem(name="KS Mỹ Khê", reason="gần biển")
    assert item.name == "KS Mỹ Khê"
    assert item.reason == "gần biển"


def test_name_and_reason_required() -> None:
    with pytest.raises(ValidationError):
        RecommendationItem(name="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        RecommendationItem(reason="x")  # type: ignore[call-arg]


def test_plan_defaults() -> None:
    plan = RecommendationPlan()
    assert plan.hotels == []
    assert plan.restaurants == []
    assert plan.assumptions == []


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        RecommendationItem(name="x", reason="y", bogus=1)  # type: ignore[call-arg]


def test_round_trip_stable() -> None:
    item = RecommendationItem(name="KS", reason="gần biển")
    assert RecommendationItem.model_validate(item.model_dump()) == item


def test_cost_vnd_removed() -> None:
    # After SRP refactor, RecommendationItem no longer carries cost_vnd — the Cost
    # agent owns all pricing via per-item tool search.
    assert "cost_vnd" not in RecommendationItem.model_fields


def test_tier_and_price_removed() -> None:
    # Pricing fields were intentionally removed from RecommendationItem.
    assert "tier" not in RecommendationItem.model_fields
    assert "price" not in RecommendationItem.model_fields
