import pytest
from pydantic import ValidationError

from app.schemas.recommendation import RecommendationItem, RecommendationPlan


def test_required_fields() -> None:
    item = RecommendationItem(name="KS Mỹ Khê", reason="gần biển")
    assert item.name == "KS Mỹ Khê"
    assert item.reason == "gần biển"
    assert item.cost_vnd is None


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
    item = RecommendationItem(name="KS", reason="gần biển", cost_vnd=900000)
    assert RecommendationItem.model_validate(item.model_dump()) == item


def test_tier_and_price_removed() -> None:
    # Pricing is expressed only as a concrete VND amount (cost_vnd); the vague
    # tier/price fields were intentionally removed.
    assert "tier" not in RecommendationItem.model_fields
    assert "price" not in RecommendationItem.model_fields
