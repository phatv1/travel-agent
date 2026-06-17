"""Itinerary agent: build a day-by-day ItineraryPlan from the trip request."""

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._llm import error_label, invoke_structured
from app.llms.factory import get_llm
from app.schemas.itinerary import ItineraryPlan
from app.schemas.state import TravelState
from app.schemas.trip import TripRequest

_SYSTEM_PROMPT = """\
Bạn là chuyên gia lập lịch trình du lịch.
Nhiệm vụ: từ TripRequest (JSON), lập lịch trình theo ngày thành ItineraryPlan.

OUTPUT CHÍNH là days[]: bắt buộc điền ĐỦ số ngày theo time_preference (5 ngày → 5 DayPlan).
Mỗi ngày (DayPlan) chia 3-4 hoạt động theo buổi:
- ScheduleItem.time_slot: morning / afternoon / evening.
- ScheduleItem.text: ngắn gọn, rõ ràng (ví dụ "Dạo biển Mỹ Khê").
- ScheduleItem.cost_vnd: chi phí MỖI ĐẦU NGƯỜI bằng VND; 0 cho miễn phí; null nếu không rõ.

Quy tắc khác:
- time_preference luôn được cung cấp (supervisor đã yêu cầu). Ước lượng số ngày từ đó
  (ví dụ "5 ngày 4 đêm" → 5 ngày, "cuối tuần" → 2 ngày).
- KHÔNG mặc định độ dài chuyến (không tự dùng "3 ngày 2 đêm"). Nếu time_preference mơ hồ
  (ví dụ "tháng 8"), suy luận số ngày hợp lý nhất VÀ ghi rõ giả định vào assumptions.
- Phân bổ khu vực (area) hợp lý theo ngày để giảm di chuyển.
- Phù hợp với companions và preferences nếu có.
- assumptions: ghi các giả định khi thiếu thông tin.
"""


def itinerary(state: TravelState) -> dict:
    """Build a day-by-day itinerary from the parsed trip request."""
    trip_request = TripRequest.model_validate(state.get("trip_request") or {})
    try:
        plan = invoke_structured(
            get_llm(),
            ItineraryPlan,
            [
                SystemMessage(_SYSTEM_PROMPT),
                HumanMessage(content=trip_request.model_dump_json(indent=2)),
            ],
        )
    except Exception as exc:  # noqa: BLE001
        return {"errors": [error_label("itinerary", exc)]}
    return {"itinerary": plan.model_dump()}
