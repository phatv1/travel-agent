"""Supervisor agent: parse the request into a TripRequest and an agent plan."""

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from app.agents._llm import error_label, invoke_structured
from app.llms.factory import get_llm
from app.schemas.state import AgentStep, TravelState
from app.schemas.trip import TripRequest

_SYSTEM_PROMPT = """\
Bạn là supervisor của trợ lý tư vấn du lịch.
Nhiệm vụ: từ tin nhắn người dùng, trích xuất TripRequest VÀ quyết định steps
(thứ tự agents cần chạy trong lượt này).

Phần 1 - TripRequest: trích xuất
- destination, origin, time_preference, budget_preference, companions, preferences.
- needs_itinerary / needs_recommendations / needs_cost_estimation: True nếu user muốn dịch vụ đó.
- Trường không rõ thì để null. KHÔNG được tự bịa/giả định (đặc biệt không mặc định
  điểm đến hay độ dài chuyến): user không nói thì để null.

Phần 2 - steps (QUYẾT ĐỊNH ROUTING, quan trọng nhất):
Danh sách agent cần chạy theo THỨ TỰ. Mỗi phần tử là một trong:
- "itinerary": lập lịch trình theo ngày.
- "recommendation": gợi ý khách sạn/quán ăn.
- "cost": ước lượng chi phí.

Quy tắc chọn steps:
- THÔNG TIN BẮT BUỘC: destination VÀ time_preference. Nếu user muốn đi du lịch nhưng
  chưa nêu điểm đến hoặc khoảng thời gian → steps = [] và để các trường đó null
  (hệ thống sẽ yêu cầu user bổ sung, KHÔNG tự giả định để chạy agent).
- Yêu cầu đầy đủ (đủ thông tin bắt buộc) → ["itinerary", "recommendation", "cost"].
- Chỉ một việc (ví dụ "chỉ gợi ý khách sạn") → ["recommendation"].
- cost luôn CUỐI danh sách khi có mặt, vì cần dữ liệu từ itinerary/recommendation.
- Không lặp lại agent trong steps.
- Nếu tin nhắn KHÔNG liên quan du lịch (chào hỏi, hỏi chung, cảm ơn...) → steps = []
  để trả lời trực tiếp.
"""


class SupervisorDecision(BaseModel):
    """Supervisor output: the parsed request + the ordered agents to run."""

    model_config = ConfigDict(extra="forbid")

    trip_request: TripRequest
    steps: list[AgentStep] = Field(
        default_factory=list,
        description=(
            'Agent cần chạy theo thứ tự: "itinerary", "recommendation", "cost". '
            "cost phải nằm cuối. Rỗng nếu tin nhắn không liên quan du lịch."
        ),
    )


def supervisor(state: TravelState) -> dict:
    """Parse the latest user message into a TripRequest and an agent plan."""
    user_message = state["messages"][-1]
    try:
        decision = invoke_structured(
            get_llm(),
            SupervisorDecision,
            [SystemMessage(_SYSTEM_PROMPT), user_message],
        )
    except Exception as exc:  # noqa: BLE001 — degrade gracefully, never crash the graph
        return {"plan": [], "errors": [error_label("supervisor", exc)]}
    return {
        "trip_request": decision.trip_request.model_dump(),
        "plan": list(decision.steps),
        "step_index": 0,
    }
