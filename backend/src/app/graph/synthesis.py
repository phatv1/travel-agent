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


_SUPERVISOR_FAILED_MESSAGE = (
    "Xin lỗi, mình chưa nắm rõ yêu cầu của bạn. Bạn vui lòng nói lại điểm đến, "
    "số ngày và số người để mình lên kế hoạch chi tiết hơn nhé."
)

_DIRECT_PROMPT = """\
Bạn là trợ lý tư vấn du lịch.
Trả lời trực tiếp, thân thiện bằng tiếng Việt cho tin nhắn không cần lập kế hoạch
(chào hỏi, hỏi chung, cảm ơn, trò chuyện). Ngắn gọn, tự nhiên. Nếu user có vẻ muốn
lên kế hoạch thì gợi ý họ nêu rõ điểm đến, số ngày và số người.
"""


def _direct_answer(state: TravelState) -> str:
    # Supervisor scheduled no agents (off-topic / general chat): answer directly.
    messages = state.get("messages") or []
    user_message = messages[-1] if messages else HumanMessage(content="")
    content = get_llm().invoke([SystemMessage(_DIRECT_PROMPT), user_message]).content
    return content if isinstance(content, str) else str(content)


def synthesize(state: TravelState) -> dict:
    """Compose the final answer.

    Three cases: supervisor failure (apology), no agents scheduled (direct reply),
    or a travel summary aggregated from agent outputs.
    """
    if not state.get("trip_request"):
        return {"final_answer": _SUPERVISOR_FAILED_MESSAGE}

    if not any(state.get(k) for k in ("itinerary", "recommendations", "cost_report")):
        return {"final_answer": _direct_answer(state)}

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

    errors = state.get("errors") or []
    if errors:
        # error_label format is "node: Type: msg"; take the node name.
        failed = ", ".join(e.split(":", 1)[0] for e in errors)
        text = f"{text.rstrip()}\n\n*Lưu ý: một số phần chưa tạo được ({failed}).*"
    return {"final_answer": text}
