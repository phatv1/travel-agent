"""Synthesis node: compose the final natural-language answer from agent outputs."""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.llms.factory import get_llm
from app.schemas.state import TravelState

_SYSTEM_PROMPT = """\
Bạn là trợ lý tư vấn du lịch.
Nhiệm vụ: từ kết quả structured (JSON), viết câu trả lời cuối thân thiện bằng tiếng Việt.

Quy tắc:
- Tổng hợp lịch trình, gợi ý (khách sạn/quán ăn) và chi phí thành một câu trả lời mạch lạc.
- Chỉ nhắc đến phần có dữ liệu; bỏ qua phần null hoặc rỗng.
- Giọng văn thân thiện như chuyên gia tư vấn du lịch.
- Dùng markdown nhẹ (tiêu đề, bullet) để dễ đọc khi hợp lý.
"""


def synthesize(state: TravelState) -> dict:
    """Compose the final natural-language answer from the structured agent outputs."""
    context = {
        "trip_request": state.get("trip_request") or {},
        "itinerary": state.get("itinerary") or {},
        "recommendations": state.get("recommendations") or {},
        "cost_report": state.get("cost_report") or {},
    }
    content = get_llm().invoke(
        [
            SystemMessage(_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, ensure_ascii=False, indent=2)),
        ]
    ).content
    text = content if isinstance(content, str) else str(content)
    return {"final_answer": text}
