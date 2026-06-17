"""Cost agent: per-item real pricing via tool-calling + deterministic backstop.

Single source of truth for ALL trip costs (SRP after refactor): reads
recommendations + itinerary from state, then searches a REAL price for each item
(per-item design — consistent with what the UI shows) via search_price, gets the
live flight via get_flight_price, and uses arithmetic tools (add/multiply/divide)
to compute per-person totals. Then _finalize recomputes total + budget status
deterministically — the LLM's tool calls showcase the agentic loop, but the final
correctness-critical values never depend on LLM math.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._llm import error_label, invoke_structured
from app.llms.factory import get_llm
from app.schemas.cost import CostReport
from app.schemas.state import TravelState
from app.schemas.trip import TripRequest
from app.tools.cost import check_budget_status_impl, parse_budget_vnd
from app.tools.flight import get_flight_price
from app.tools.loop import gather_via_tools

_GATHER_PROMPT = """\
Bạn là chuyên gia chi phí du lịch. Tính chi phí THẬT cho chuyến đi qua tool:

BƯỚC 1 — Vé máy bay (BẮT BUỘC nếu có origin):
- get_flight_price: gọi với IATA của origin → destination để lấy giá khứ hồi thật.

BƯỚC 2 — Giá từng khách sạn/quán đã recommend (BẮT BUỘC, per-item):
- search_price: gọi cho MỖI khách sạn trong recommendations.hotels (query:
  "giá phòng {name} {destination}"). Lấy giá/phòng/đêm.
- search_price: gọi cho MỖI quán ăn trong recommendations.restaurants (query:
  "giá {name} {destination}"). Lấy giá/người.

BƯỚC 3 — Tính toán số học (DÙNG tool, không tự tính):
- multiply: giá KS/đêm × số đêm (số đêm = số ngày - 1).
- divide: tổng KS / số người (lấy companions từ trip_request).
- add: cộng các khoản lại.

BƯỚC 4 — check_budget_status: khi có tổng VÀ budget, gọi tool đánh giá.
Gọi đủ tool rồi thì dừng (không cần trả lời thêm).
"""

_SYNTHESIZE_PROMPT = """\
Bạn là chuyên gia chi phí du lịch. Từ dữ liệu chuyến đi và giá THẬT đã thu thập qua tool,
tổng hợp CostReport (tất cả amount_vnd là VND, mỗi đầu người):

- items[]: nhóm chi phí:
  + Di chuyển: vé máy bay từ get_flight_price (chia số người nếu cần) + nội vùng.
  + Lưu trú: giá KS (từ search_price) × số đêm, chia số người/phòng.
  + Ăn uống: giá quán (từ search_price) × số bữa/người.
  + Hoạt động: ước lượng vé tham quan (nếu có).
  + Dự phòng: 5-10% nếu thiếu.
- total_per_person_vnd: tổng items (hệ thống sẽ tính lại).
- status: để mặc định, hệ thống tính lại chính xác.
- assumptions: ghi giả định (số người, số đêm, nguồn giá vé/KS/quán từ tool).
- suggestions: gợi ý tiết kiệm nếu vượt budget.

LƯU Ý: Chỉ dùng GIÁ THẬT từ tool. Nếu tool không trả giá cho một mục, ước lượng hợp lý
và ghi vào assumptions.
"""


def _gather_messages(context: dict) -> list:
    prompt = (
        "Dữ liệu chuyến đi (recommendations + lịch trình + yêu cầu):\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [SystemMessage(_GATHER_PROMPT), HumanMessage(content=prompt)]


def _tool_results_as_text(messages: list) -> str:
    # Flatten the tool-calling conversation into readable text for phase 2.
    # Phase 2 gets a clean message history — Ollama's structured-output mode
    # mishandles raw tool_call/ToolMessage history.
    lines = []
    for m in messages:
        calls = getattr(m, "tool_calls", None) or []
        for tc in calls:
            lines.append(f"- Đã gọi {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})")
        if type(m).__name__ == "ToolMessage":
            lines.append(f"  → kết quả: {str(m.content)[:500]}")
    return "\n".join(lines)


def _finalize(report: CostReport, trip_request: TripRequest) -> CostReport:
    """Deterministic override of correctness-critical fields (don't trust LLM math)."""
    amounts = [item.amount_vnd for item in report.items if item.amount_vnd is not None]
    if amounts:
        report = report.model_copy(update={"total_per_person_vnd": sum(amounts)})

    total = report.total_per_person_vnd
    budget_vnd = parse_budget_vnd(trip_request.budget_preference)
    if total and budget_vnd:
        status = check_budget_status_impl(total, budget_vnd)
        comparison = f"Chi phí ~{total:,} VND/người vs ngân sách ~{budget_vnd:,} VND → {status}."
        report = report.model_copy(update={"status": status, "budget_comparison": comparison})
    elif total and not budget_vnd:
        report = report.model_copy(update={"status": "unknown_budget"})
    return report


def cost(state: TravelState) -> dict:
    """Estimate per-person costs: per-item real pricing → CostReport → finalize."""
    trip_request = TripRequest.model_validate(state.get("trip_request") or {})
    recommendations = state.get("recommendations") or {}
    context = {
        "trip_request": trip_request.model_dump(),
        "recommendations": recommendations,
        "itinerary_days": len((state.get("itinerary") or {}).get("days", [])),
    }

    # Import domain cost tools here to avoid an import cycle (cost.py ↔ tools.cost).
    from app.tools.cost import (
        add,
        check_budget_status,
        divide,
        multiply,
        search_price,
    )

    try:
        llm = get_llm()

        # Phase 1: gather real prices via tool-calling (agentic showcase).
        tools = [
            get_flight_price,
            search_price,
            add,
            multiply,
            divide,
            check_budget_status,
        ]
        gathered = gather_via_tools(llm, tools, _gather_messages(context))

        # Phase 2: structured CostReport with tool results as text.
        tool_text = _tool_results_as_text(gathered)
        final_prompt = (
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"GIÁ THẬT ĐÃ THU THẬP:\n{tool_text}\n\n"
            "Dựa vào giá thật trên, tổng hợp CostReport ĐẦY ĐỦ với items[]."
        )
        report = invoke_structured(
            llm, CostReport, [SystemMessage(_SYNTHESIZE_PROMPT), HumanMessage(content=final_prompt)]
        )
    except Exception as exc:  # noqa: BLE001
        return {"errors": [error_label("cost", exc)]}

    report = _finalize(report, trip_request)
    return {"cost_report": report.model_dump()}
