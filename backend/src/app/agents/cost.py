"""Cost agent: estimate per-person costs from trip request, itinerary, recommendations."""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.llms.factory import get_llm
from app.schemas.cost import CostReport
from app.schemas.state import TravelState
from app.schemas.trip import TripRequest

_SYSTEM_PROMPT = """\
Bạn là chuyên gia ước lượng chi phí du lịch.
Nhiệm vụ: từ trip_request, itinerary và recommendations (JSON), tổng hợp chi phí thành CostReport.

Tất cả amount_vnd tính MỖI ĐẦU NGƯỜI bằng VND (không phải nghìn đồng).

Cách tính:
- Hoạt động: lấy từ itinerary.days[].schedule[].cost_vnd (đã là mỗi người).
- Ăn uống: lấy từ recommendations.restaurants[].cost_vnd (mỗi người) × số bữa.
- Lưu trú: lấy từ recommendations.hotels[].cost_vnd (MỖI PHÒNG/ĐÊM), chia số người mỗi phòng
  (dùng trip_request.companions), × số đêm.
- Di chuyển, dự phòng: ước lượng hợp lý nếu thiếu.

Quy tắc:
- items[]: nhóm chi phí (ví dụ Di chuyển, Lưu trú, Ăn uống, Hoạt động, Dự phòng).
- total_per_person_vnd: để null, hệ thống sẽ tự tính tổng từ items.
- budget_comparison: so với trip_request.budget_preference nếu có.
- status: within_budget / slightly_over_budget / over_budget / unknown_budget
  (chưa có budget) / insufficient_info.
- assumptions: ghi giả định (số người, số đêm, cách quy đổi phòng).
- suggestions: gợi ý tiết kiệm nếu vượt budget.
"""


def cost(state: TravelState) -> dict:
    """Estimate per-person costs by aggregating itinerary and recommendation costs."""
    trip_request = TripRequest.model_validate(state.get("trip_request") or {})
    if not trip_request.needs_cost_estimation:
        return {}

    context = {
        "trip_request": trip_request.model_dump(),
        "itinerary": state.get("itinerary") or {},
        "recommendations": state.get("recommendations") or {},
    }
    planner = get_llm().with_structured_output(CostReport)
    report = CostReport.model_validate(
        planner.invoke(
            [
                SystemMessage(_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(context, ensure_ascii=False, indent=2)),
            ]
        )
    )

    # LLMs miscalculate large-number sums; recompute the total from items deterministically.
    amounts = [item.amount_vnd for item in report.items if item.amount_vnd is not None]
    if amounts:
        report = report.model_copy(update={"total_per_person_vnd": sum(amounts)})

    return {"cost_report": report.model_dump()}
