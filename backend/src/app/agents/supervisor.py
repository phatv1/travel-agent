"""Supervisor agent: route the turn from the full conversation context."""

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from app.agents._llm import error_label, invoke_structured
from app.llms.factory import get_llm
from app.schemas.state import AgentAction, AgentStep, TravelState
from app.schemas.trip import TripRequest

_SYSTEM_PROMPT = """\
Bạn là supervisor của trợ lý tư vấn du lịch. Bạn thấy TOÀN BỘ lịch sử hội thoại
(có thể nhiều lượt) và là NGƯỜI QUYẾT ĐỊNH duy nhất cho lượt này làm gì.

Phần 1 — TripRequest (gộp intent từ toàn bộ ngữ cảnh):
- destination, origin, time_preference, budget_preference, companions, preferences.
- needs_itinerary / needs_recommendations / needs_cost_estimation.
- Đa lượt (FOLLOW-UP): tin nhắn cuối có thể tham chiếu lượt trước ("thêm 1 ngày nữa",
  "đổi khách sạn rẻ hơn", "đi thêm Phú Quốc", "nhóm thêm 2 người", "vậy còn chi phí?").
  TripRequest phải phản ánh chuyến đi SAU KHI ÁP DỤNG thay đổi của lượt này lên ngữ cảnh
  trước — KHÔNG phải chỉ tin nhắn cuối. Vd: trước "Đà Nẵng 3 ngày", nay "thêm 1 ngày"
  → destination="Đà Nẵng", time_preference="4 ngày".
- Trường không rõ thì để null. KHÔNG tự bịa/giả định điểm đến hay độ dài chuyến.

Phần 2 — action (QUYẾT ĐỊNH ROUTING, quan trọng nhất). Chọn MỘT:
- "plan": đủ thông tin để lên kế hoạch hữu ích (được phép giả định hợp lý cho những
  thứ nhỏ, ví dụ "2 người" nếu không nói). Đặt `steps` là danh sách agent cần chạy.
- "clarify": user muốn đi du lịch NHƯNG đang thiếu thông tin cốt lõi đến mức không
  thể tư vấn tử tế (thường là destination HOẶC time_preference). Hệ thống sẽ hỏi lại
  TỰ NHIÊN + đưa gợi ý. Đặt steps = [].
- "direct": không phải du lịch (chào hỏi, hỏi chung, cảm ơn, trò chuyện) HOẶC câu
  hỏi mà agent không cần chạy (vd hỏi thông tin chung). Đặt steps = [].

Quy tắc chọn action (theo thứ tự ưu tiên):
- Tin nhắn xã giao / phản hồi ngoài lề (cảm ơn, ừ/ok, haha, lời chào, câu hỏi
  chung không phải thông tin chuyến đi) → "direct", KỂ CẢ khi đang giữa một trip
  chưa xong. Đừng hỏi lại thông tin khi user chỉ đang phản hồi xã giao — hãy đáp
  lời họ rồi nhẹ nhàng nhắc tiếp chuyến đi nếu hợp (vd "Không có gì! Khi nào rảnh
  thì mình lên lịch Núi Bà Đen nhé 😊").
- Tin nhắn không liên quan du lịch → "direct".
- Muốn đi du lịch nhưng chưa có điểm đến → "clarify" (đưa gợi ý loại điểm đến).
- Có điểm đến nhưng chưa có/không suy ra được thời gian → "clarify" (gợi ý options:
  cuối tuần 2N1Đ, 3N2Đ, hay chuyến dài 5N4Đ?).
- Đã đủ destination + time (hoặc suy ra được từ ngữ cảnh) → "plan".
- Follow-up thu hẹp ("chỉ đổi khách sạn") → "plan" với steps chỉ chứa agent liên quan.
- KHÔNG bao giờ hỏi lại thông tin đã có ở lượt trước.

Quy tắc steps (khi action="plan"):
- Thứ tự: "itinerary", "recommendation", "cost". cost LUÔN cuối (cần dữ liệu trước).
- Không lặp agent. steps=[itinerary, recommendation, cost] cho plan đầy đủ.
- Chỉ một việc → vd ["recommendation"].
"""


class SupervisorDecision(BaseModel):
    """Supervisor output: routing action + resolved trip request + ordered agents."""

    model_config = ConfigDict(extra="forbid")

    action: AgentAction = Field(
        description=(
            'Quyết định lượt này: "plan" (chạy agents theo steps), "clarify" '
            '(hỏi thêm thông tin còn thiếu, tự nhiên), hoặc "direct" (trả lời '
            "trực tiếp, không cần agent)."
        ),
    )
    trip_request: TripRequest
    steps: list[AgentStep] = Field(
        default_factory=list,
        description=(
            'Agent cần chạy theo thứ tự (chỉ khi action="plan"): "itinerary", '
            '"recommendation", "cost". cost phải nằm cuối. Rỗng cho clarify/direct.'
        ),
    )


def supervisor(state: TravelState) -> dict:
    """Route the turn from the full conversation context.

    Reads the whole message history so follow-ups resolve against prior turns
    (the supervisor is the single decision-maker: it decides plan/clarify/direct,
    not a downstream field check). Also resets the per-turn ephemeral fields so
    the checkpointer can't carry last turn's failures and partial domain output
    into the next answer.
    """
    messages = state["messages"]
    reset: dict = {
        "errors": [],
        "step_index": 0,
        "itinerary": {},
        "recommendations": {},
        "cost_report": {},
        "final_answer": "",
    }
    try:
        decision = invoke_structured(
            get_llm(),
            SupervisorDecision,
            [SystemMessage(_SYSTEM_PROMPT), *messages],
        )
    except Exception as exc:  # noqa: BLE001 — degrade gracefully, never crash the graph
        # No usable decision: route to a direct (apology) reply. Synthesis treats
        # a missing trip_request + supervisor error as the degraded fallback.
        return {
            **reset,
            "action": "direct",
            "plan": [],
            "errors": [error_label("supervisor", exc)],
        }
    return {
        **reset,
        "action": decision.action,
        "trip_request": decision.trip_request.model_dump(),
        "plan": list(decision.steps),
    }
