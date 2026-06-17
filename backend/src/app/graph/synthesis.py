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

# All clarifiable fields: (key, label, example, required). Drives both the
# deterministic required-check and the comprehensive first-time clarify message
# (user-facing text, not an LLM prompt). Same philosophy as the cost total
# recompute: don't trust the LLM with contracts the UX depends on.
_FIELD_HINTS: tuple[tuple[str, str, str, bool], ...] = (
    ("destination", "Điểm đến", "Đà Nẵng, Hội An, Phú Quốc", True),
    ("time_preference", "Khoảng thời gian", "5 ngày 4 đêm, cuối tuần", True),
    ("origin", "Điểm xuất phát", "TP.HCM, Hà Nội", False),
    ("budget_preference", "Ngân sách", "20 triệu VND", False),
    ("companions", "Số người / đoàn", "2 người, gia đình 4 người", False),
    ("preferences", "Sở thích", "biển, hải sản, lịch nhẹ", False),
)
_REQUIRED_KEYS = tuple(key for key, _, _, required in _FIELD_HINTS if required)
_TRAVEL_INTENT_FIELDS = tuple(key for key, *_ in _FIELD_HINTS)


def _clarify_message(trip_request: dict) -> str:
    # First-time clarify (user-facing): list ALL missing fields, grouped required /
    # optional. Optional fields can be skipped — defaults apply — so we never block
    # on them, only surface them so the user can refine for accuracy.
    missing_required = [
        f"- {label} (ví dụ: {ex})"
        for key, label, ex, req in _FIELD_HINTS
        if req and not trip_request.get(key)
    ]
    missing_optional = [
        f"- {label} (ví dụ: {ex})"
        for key, label, ex, req in _FIELD_HINTS
        if not req and not trip_request.get(key)
    ]

    lines = ["Để mình tư vấn chính xác nhất, bạn cho mình biết thêm:" + "\n*Bắt buộc:*"]
    lines += missing_required
    if missing_optional:
        lines += [
            "*Tùy chọn — bạn có thể bỏ qua, mình sẽ dùng mặc định (nên có để chính xác hơn):*"
        ]
        lines += missing_optional
    lines += ["Bạn muốn bổ sung thông tin nào không?"]
    return "\n".join(lines)


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

    Four cases: supervisor failure (apology), missing required info (ask to
    clarify), no travel intent / no agent outputs (direct reply), or a travel
    summary aggregated from agent outputs.
    """
    trip_request = state.get("trip_request")
    if not trip_request:
        return {"final_answer": _SUPERVISOR_FAILED_MESSAGE}

    # Deterministic backstop for the required-minimum contract: the supervisor is
    # prompted to ask when destination/time are missing, but we don't trust the LLM.
    # If a required field is still null here AND the user is actually planning a
    # trip, ask for it instead of presenting a plan built on missing info.
    missing_required = [key for key in _REQUIRED_KEYS if not trip_request.get(key)]
    if missing_required and any(trip_request.get(f) for f in _TRAVEL_INTENT_FIELDS):
        return {"final_answer": _clarify_message(trip_request)}

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
