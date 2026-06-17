import pytest
from pydantic import ValidationError

from app.schemas.cost import CostItem, CostReport


def test_cost_item_name_required() -> None:
    item = CostItem(name="Lưu trú", amount_vnd=2000000)
    assert item.name == "Lưu trú"
    assert item.amount_vnd == 2000000
    with pytest.raises(ValidationError):
        CostItem(amount_vnd=1)  # type: ignore[call-arg]


def test_cost_report_summary_required() -> None:
    report = CostReport(summary="ok")
    assert report.summary == "ok"
    assert report.items == []
    assert report.total_per_person_vnd is None
    with pytest.raises(ValidationError):
        CostReport()  # type: ignore[call-arg]


def test_status_default_and_literal() -> None:
    assert CostReport(summary="ok").status == "insufficient_info"
    with pytest.raises(ValidationError):
        CostReport(summary="ok", status="bankrupt")  # type: ignore[arg-type]


def test_total_vnd_removed() -> None:
    # Costs are per-person only; the ambiguous group-total field was removed.
    assert "total_vnd" not in CostReport.model_fields
    assert "total_per_person_vnd" in CostReport.model_fields


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        CostItem(name="x", bogus=1)  # type: ignore[call-arg]


def test_round_trip_stable() -> None:
    report = CostReport(
        summary="ok",
        items=[CostItem(name="Lưu trú", amount_vnd=2000000)],
        total_per_person_vnd=5000000,
        status="within_budget",
    )
    assert CostReport.model_validate(report.model_dump()) == report
