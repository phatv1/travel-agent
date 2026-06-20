"""Synthesis node: compose the final answer, dispatched on the supervisor's action.

The supervisor (which sees the full conversation) decides the action; this node
only turns that decision into prose. No field-presence routing lives here.
"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.supervisor import CAPABILITIES
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

# Degraded-mode fallback: only reached when the supervisor's own LLM call failed
# (we have no decision and can't reliably ask the LLM to write a message). This is
# not a clarification rule — it's a "the supervisor is down" apology.
_SUPERVISOR_FAILED_MESSAGE = (
    "Xin lỗi, mình đang gặp chút vấn đề xử lý yêu cầu. Bạn vui lòng nhắc lại "
    "điểm đến, số ngày và số người để mình tư vấn chi tiết hơn nhé."
)

# Field labels for the clarify prompt only (humanizing what's known / missing in
# the question). NOT a routing contract — the supervisor decides when to clarify.
_FIELD_LABELS: tuple[tuple[str, str, str], ...] = (
    ("destination", "điểm đến", "Đà Nẵng, Hội An, Phú Quốc"),
    ("time_preference", "thời gian", "2N1Đ cuối tuần, 3N2Đ, 5N4Đ"),
    ("origin", "điểm xuất phát", "TP.HCM, Hà Nội"),
    ("budget_preference", "ngân sách", "5-10 triệu, 20 triệu VND"),
    ("companions", "số người", "2 người, gia đình 4 người"),
    ("preferences", "sở thích", "biển, hải sản, lịch nhẹ"),
)


def _format_known(trip_request: dict) -> str:
    lines = [
        f"- {label}: {trip_request[key]}"
        for key, label, _ in _FIELD_LABELS
        if trip_request.get(key)
    ]
    return "\n".join(lines) or "(chưa có gì)"


def _missing(trip_request: dict) -> list[str]:
    return [key for key, _, _ in _FIELD_LABELS if not trip_request.get(key)]


_CLARIFY_PROMPT = """\
Bạn là trợ lý tư vấn du lịch, nói chuyện tự nhiên, thân thiện như một tư vấn
viên thực — KHÔNG như một form.

Nhiệm vụ: viết một câu phản hồi NGẮN để hỏi thêm thông tin cần thiết
cho việc lên kế hoạch. Phải ĐƯA GỢI Ý cụ thể để user dễ trả lời.

Thông tin user đã cho:
{known}

Thông tin còn thiếu (ưu tiên hỏi những thứ quan trọng nhất trước):
{missing}

Quy tắc:
- Tự nhiên như chat, ngắn gọn (1-3 câu). Không bullet list dài.
  Không "Bắt buộc:"/"Tùy chọn:".
- Nếu đã biết điểm đến, xác nhận nhẹ nhàng rồi hỏi đúng thứ còn thiếu
  (vd: "Núi Bà Đen à, tuyệt! ...").
- QUAN TRỌNG — ĐƯA GỢI Ý CỤ THỂ (bắt buộc): với MỖI thứ cần hỏi, đưa 2-3 lựa chọn
  cụ thể để user chỉ việc chọn, KHÔNG hỏi suông. Đây là yêu cầu bắt buộc.
  Vd thời gian: "Bạn muốn đi 2N1Đ cuối tuần, 3N2Đ, hay chuyến dài 5N4Đ?"
  Vd điểm đến: "Bạn thích biển (Đà Nẵng, Phú Quốc), núi (Đà Lạt, Sapa),
  hay phố cổ (Hội An)?"
- Ưu tiên hỏi 1-2 thứ quan trọng nhất trước, đừng hỏi dồn dập tất cả cùng lúc.
- Tiếng Việt, có thể thêm 1 emoji nhẹ.
"""


def _clarify_message(state: TravelState) -> str:
    # The supervisor decided "clarify"; this only writes the prose. Suggestions
    # are the key quality bar (per UX feedback): give concrete options, not bare
    # questions. A deterministic fallback covers LLM failure.
    trip_request = state.get("trip_request") or {}
    missing = _missing(trip_request)
    labels = {k: lbl for k, lbl, _ in _FIELD_LABELS}
    prompt = _CLARIFY_PROMPT.format(
        known=_format_known(trip_request),
        missing="\n".join(f"- {labels[k]}" for k in missing) or "(không)",
    )
    try:
        content = get_llm().invoke([HumanMessage(content=prompt)]).content
        text = content if isinstance(content, str) else str(content)
        if text.strip():
            return text
    except Exception:  # noqa: BLE001 — fall back so the user always gets a question
        pass
    first = labels[missing[0]] if missing else "thông tin"
    return f"Để mình tư vấn chính xác hơn, bạn cho mình biết thêm {first} nhé? 😊"


_DIRECT_PROMPT = """\
Bạn là trợ lý tư vấn du lịch.
Trả lời trực tiếp, thân thiện bằng tiếng Việt cho tin nhắn không cần lập kế hoạch
(chào hỏi, hỏi chung, cảm ơn, trò chuyện). Ngắn gọn, tự nhiên. Nếu user có vẻ muốn
lên kế hoạch thì gợi ý họ nêu rõ điểm đến, số ngày và số người.
"""


def _direct_answer(state: TravelState) -> str:
    messages = state.get("messages") or []
    user_message = messages[-1] if messages else HumanMessage(content="")
    content = get_llm().invoke([SystemMessage(_DIRECT_PROMPT), user_message]).content
    return content if isinstance(content, str) else str(content)


def _summarize(state: TravelState) -> str:
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
    return text


def _refuse_message(state: TravelState) -> str:
    """Honest refusal: name what the bot cannot do and steer to what it can.

    Two shapes:
      - Crisis / self-harm signal → a short, caring redirect to help (never a
        cheerful plan). Handled first because duty-of-care outroutes capability.
      - Otherwise (out-of-scope request, prompt injection, harmful content) → an
        LLM reply grounded in the capability list: states the limit plainly and
        suggests the nearest in-scope thing, so the user is never just blocked.
    Falls back to a deterministic template if the LLM call fails.
    """
    messages = state.get("messages") or []
    raw = messages[-1].content if messages else ""
    # content may be a list of blocks (multimodal providers); coerce to text.
    user_text = str(raw).lower() if not isinstance(raw, str) else raw.lower()
    crisis_words = (
        "không quay về", "không muốn sống", "tự xử", "tự vẫn", "kết thúc cuộc đời",
        "kill myself", "suicide", "end it all", "không còn lý do",
    )
    if any(w in user_text for w in crisis_words):
        return (
            "Mình thấy dường như bạn đang ở một lúc rất khó khăn. Bạn không đơn độc — "
            "hãy gọi 111 (Tổng đài Quốc gia Bảo vệ Trẻ em, miễn phí 24/7) hoặc nói "
            "chia sẻ với người bạn tin. Mình luôn sẵn sàng tư vấn một chuyến đi nghỉ "
            "ngơi khi bạn sẵn sàng. 💙"
        )

    caps = "; ".join(c["label"].lower() for c in CAPABILITIES)
    prompt = (
        f"Yêu cầu của user nằm NGOÀI 3 năng lực của mình ({caps}). "
        "Hãy viết 1-3 câu tiếng Việt, thân thiện, nói THẬT mình không làm được "
        "chuyện đó (KHÔNG bịa thông tin, KHÔNG hứa đặt chỗ/giá vé/thời tiết/visa), "
        "rồi gợi ý ngắn 1 việc trong tầm mình có thể giúp. "
        f"Tin nhắn user: {(messages[-1].content if messages else '')[:200]}"
    )
    try:
        content = get_llm().invoke([HumanMessage(content=prompt)]).content
        text = content if isinstance(content, str) else str(content)
        if text.strip():
            return text
    except Exception:  # noqa: BLE001 — user always gets a refusal, LLM or not
        pass
    return (
        "Xin lỗi, phần này nằm ngoài 3 việc mình làm được (lập lịch trình, gợi ý "
        "lưu trú & ăn uống, ước chi phí). Bạn cho mình biết điểm đến và thời gian, "
        "mình sẽ tư vấn kế hoạch chi tiết nhé!"
    )


def synthesize(state: TravelState) -> dict:
    """Compose the final answer, dispatched on the supervisor's action.

    - plan      → summarize agent outputs (fall back to direct if none ran)
    - clarify   → ask for the missing info naturally, with concrete suggestions
    - refuse    → honest refusal naming the limit (duty-of-care for crisis signals)
    - direct    → answer conversationally

    The answer is returned both as ``final_answer`` (API/trace) and appended to
    ``messages`` as an AIMessage so the checkpointer persists it for the next turn.

    A supervisor-LLM failure (no decision at all) degrades to an apology rather
    than crashing — the only hard-coded string here.
    """
    action = state.get("action")
    trip_request = state.get("trip_request")

    if not trip_request and (state.get("errors") or not action):
        # Supervisor's own LLM call failed before producing a decision.
        text = _SUPERVISOR_FAILED_MESSAGE
    elif action == "clarify":
        text = _clarify_message(state)
    elif action == "refuse":
        text = _refuse_message(state)
    elif action == "direct":
        text = _direct_answer(state)
    else:
        # action == "plan" (default). If agents produced nothing (e.g. the
        # supervisor mis-judged), fall back to a direct reply rather than empty.
        if any(state.get(k) for k in ("itinerary", "recommendations", "cost_report")):
            text = _summarize(state)
        else:
            text = _direct_answer(state)

    return {"final_answer": text, "messages": [AIMessage(content=text)]}
