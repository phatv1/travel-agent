"""Supervisor agent: parse the request into a TripRequest and an agent plan."""

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from app.agents._llm import error_label, invoke_structured
from app.llms.factory import get_llm
from app.schemas.state import AgentStep, TravelState
from app.schemas.trip import TripRequest

_SYSTEM_PROMPT = """\
Bạn là supervisor của trợ lý tư vấn du lịch.
Nhiệm vụ: từ CUỘC TRÒ CHUYỆN (có thể nhiều lượt), trích xuất TripRequest VÀ
quyết định steps (thứ tự agents cần chạy trong lượt này).

Phần 1 - TripRequest: trích xuất
- destination, origin, time_preference, budget_preference, companions, preferences.
- needs_itinerary / needs_recommendations / needs_cost_estimation.
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

ĐA LƯỢT (FOLLOW-UP) — QUAN TRỌNG:
- Bạn thấy TOÀN BỘ lịch sử hội thoại, không chỉ tin nhắn cuối. Phân tích theo ngữ cảnh.
- Tin nhắn cuối có thể là follow-up tham chiếu lượt trước, ví dụ:
  "thêm 1 ngày nữa", "đổi khách sạn rẻ hơn", "đi thêm Phú Quốc", "vậy còn chi phí?",
  "giảm xuống 3 ngày", "nhóm thêm 2 người".
- Khi đó: TripRequest phải phản ánh chuyến đi SAU KHI ÁP DỤNG thay đổi của lượt này
  (gộp intent mới vào TripRequest ngụ ý từ hội thoại trước), KHÔNG phải chỉ tin nhắn cuối.
  Ví dụ: lượt trước "Đà Nẵng 3 ngày", lượt này "thêm 1 ngày" → time_preference="4 ngày",
  destination="Đà Nẵng".
- steps chỉ chứa những agent user MUỐN CHẠY LƯỢT NÀY. Follow-up thu hẹp
  ("chỉ đổi khách sạn") → ["recommendation"] (không chạy lại itinerary/cost).
- Follow-up yêu cầu cả lịch trình lẫn gợi ý → đặt lại các agent liên quan vào steps.
- Nếu follow-up thiếu thông tin đã có ở lượt trước (destination/time), KHÔNG hỏi lại;
  dùng ngữ cảnh hội thoại để resolve.
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
    """Parse the conversation into a TripRequest and an agent plan.

    Reads the full message history so follow-ups resolve against prior turns.
    Also resets the per-turn ephemeral fields (errors, plan, step_index, and any
    domain results not recomputed this turn). Without these resets the
    checkpointer would carry last turn's failures and partial domain output into
    the next answer, polluting it with stale data.
    """
    # Full conversation history — the supervisor must see prior turns to resolve
    # follow-ups ("thêm 1 ngày nữa", "đổi KS rẻ hơn") against the established
    # trip context, not just the latest message in isolation.
    messages = state["messages"]
    # Per-turn reset: these are ephemeral to the current turn. The checkpointer
    # persists the whole TravelState between turns, so leaving them set would
    # leak the previous turn's plan, errors, and partial domain results.
    reset: dict = {
        "errors": [],
        "step_index": 0,
        # Domain fields: blank any result this turn won't recompute, so a
        # narrowed follow-up (e.g. "only suggest hotels") never shows a stale
        # itinerary/cost from the previous turn.
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
        return {**reset, "plan": [], "errors": [error_label("supervisor", exc)]}
    return {
        **reset,
        "trip_request": decision.trip_request.model_dump(),
        "plan": list(decision.steps),
    }
