"""Supervisor agent: parse the user's message into a structured TripRequest."""

from langchain_core.messages import SystemMessage

from app.llms.factory import get_llm
from app.schemas.state import TravelState
from app.schemas.trip import TripRequest

_SYSTEM_PROMPT = """\
Bạn là bộ phân tích yêu cầu của trợ lý tư vấn du lịch.
Nhiệm vụ duy nhất: từ tin nhắn người dùng, trích xuất thông tin chuyến đi vào TripRequest.

Trích xuất trường:
- time_preference: thời gian/số ngày-đêm (ví dụ "5 ngày 4 đêm", "tháng 8", "cuối tuần").
- budget_preference: số tiền/ngân sách (ví dụ "25 triệu", "tối đa 1000 USD").
- companions: số người và kiểu nhóm (ví dụ "2 người", "solo", "gia đình 4 người").
- preferences: sở thích/yêu cầu (ví dụ "thích biển, hải sản").
- Trường không rõ thì để null.

Routing (quan trọng nhất):
- needs_itinerary: True nếu user muốn LÊN LỊCH TRÌNH theo ngày.
- needs_recommendations: True nếu user muốn GỢI Ý khách sạn/quán ăn.
- needs_cost_estimation: True nếu user muốn ƯỚC LƯỢNG CHI PHÍ.
- Khi user nói "chỉ ... thôi" hoặc "không cần ..." → các dịch vụ khác đặt False.
- Khi không rõ → mặc định cả 3 True (làm đầy đủ).
"""


def supervisor(state: TravelState) -> dict:
    """Extract a TripRequest from the latest user message via structured output."""
    user_message = state["messages"][-1]
    extractor = get_llm().with_structured_output(TripRequest)
    trip_request = TripRequest.model_validate(
        extractor.invoke([SystemMessage(_SYSTEM_PROMPT), user_message])
    )
    return {"trip_request": trip_request.model_dump()}
