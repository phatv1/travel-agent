"""Recommendation agent: suggest hotels and restaurants from the trip request."""

from langchain_core.messages import HumanMessage, SystemMessage

from app.llms.factory import get_llm
from app.schemas.recommendation import RecommendationPlan
from app.schemas.state import TravelState
from app.schemas.trip import TripRequest

_SYSTEM_PROMPT = """\
Bạn là chuyên gia gợi ý lưu trú và ẩm thực du lịch.
Nhiệm vụ: từ TripRequest (JSON), gợi ý khách sạn và quán ăn thành RecommendationPlan.

OUTPUT CHÍNH là hotels[] và restaurants[]: mỗi loại 3-5 gợi ý cụ thể.
- name: tên cụ thể (ví dụ "Khách sạn Mỹ Khê Boutique", "Quán hải sản Bé Mặn").
- area: khu vực (ví dụ "Mỹ Khê", "phố cổ Hội An").
- cost_vnd (đơn vị VND, KHÔNG phải nghìn đồng):
  + Quán ăn: 150000-500000 VND/người (một đến năm trăm nghìn).
  + Khách sạn: 500000-3000000 VND/phòng/đêm (500k-3 triệu).
  + Ví dụ ĐÚNG: bữa ăn 250000, phòng khách sạn 900000. Không thêm số 0 thừa.
  + null nếu không rõ.
- Khách sạn: ghi sức chứa phòng trong description (ví dụ "phòng đôi 2 người, có hồ bơi").
- reason: lý do phù hợp (gần biển, hợp budget, đúng sở thích...).

Quy tắc khác:
- Phù hợp với destination, companions, preferences, budget_preference nếu có.
- assumptions: ghi giả định khi thiếu thông tin.
"""


def recommendation(state: TravelState) -> dict:
    """Suggest hotels and restaurants from the parsed trip request."""
    trip_request = TripRequest.model_validate(state.get("trip_request") or {})
    if not trip_request.needs_recommendations:
        return {}

    planner = get_llm().with_structured_output(RecommendationPlan)
    plan = RecommendationPlan.model_validate(
        planner.invoke(
            [
                SystemMessage(_SYSTEM_PROMPT),
                HumanMessage(content=trip_request.model_dump_json(indent=2)),
            ]
        )
    )
    return {"recommendations": plan.model_dump()}
