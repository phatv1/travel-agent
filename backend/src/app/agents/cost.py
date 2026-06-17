"""Cost agent: estimate per-person costs using tool-calling + deterministic backstop.

Two-phase pattern (showcase + correctness):
  Phase 1 (gather): LLM bind_tools calls get_flight_price / check_budget_status /
    compute_trip_total to collect real data (agentic loop, _GATHER_PROMPT).
  Phase 2 (synthesize): LLM produces CostReport from context + tool results as
    text (clean structured output, _SYNTHESIZE_PROMPT — no tool mention, since
    Ollama's structured-output mode chokes when the prompt references tools it
    can't call).
Then the node recomputes total + budget status deterministically — the LLM's tool
calls showcase the loop, but correctness-critical values never depend on LLM math.
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
Bạn là chuyên gia chi phí du lịch. Thu thập dữ liệu thật bằng tool:
- get_flight_price: BẮT BUỘC gọi cho đường bay origin→destination (không tự bịa vé).
- check_budget_status: khi có tổng ước lượng VÀ budget.
- compute_trip_total: khi cần tính tổng từ chi phí mỗi ngày.
Gọi đủ tool rồi thì dừng (không cần trả lời thêm).
"""

_SYNTHESIZE_PROMPT = """\
Bạn là chuyên gia ước lượng chi phí du lịch. Từ dữ liệu chuyến đi và kết quả tool,
tổng hợp CostReport (tất cả amount_vnd là VND, mỗi đầu người):

- items[]: nhóm chi phí. Di chuyển (dùng giá vé tool thật), Lưu trú (KS/phòng/đêm
  chia người × đêm), Ăn uống (quán/người × bữa), Hoạt động (từ itinerary),
  Dự phòng (5-10% nếu thiếu).
- total_per_person_vnd: tổng items (hệ thống sẽ tính lại).
- status: để mặc định, hệ thống tính lại chính xác.
- assumptions: ghi giả định (số người, số đêm, nguồn giá vé).
- suggestions: gợi ý tiết kiệm nếu vượt budget.
"""


def _gather_messages(context: dict) -> list:
    prompt = f"Thông tin chuyến đi:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
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
            lines.append(f"  → kết quả: {m.content}")
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
    """Estimate per-person costs: tool-gathered data → CostReport → deterministic total/status."""
    trip_request = TripRequest.model_validate(state.get("trip_request") or {})
    context = {
        "trip_request": trip_request.model_dump(),
        "itinerary": state.get("itinerary") or {},
        "recommendations": state.get("recommendations") or {},
    }

    # Import domain cost tools here to avoid an import cycle (cost.py ↔ tools.cost).
    from app.tools.cost import (
        check_budget_status,
        compute_trip_total,
        convert_currency,
    )

    try:
        llm = get_llm()

        # Phase 1: gather real data via tool-calling (agentic showcase).
        tools = [get_flight_price, compute_trip_total, check_budget_status, convert_currency]
        gathered = gather_via_tools(llm, tools, _gather_messages(context))

        # Phase 2: structured CostReport with tool results as text (clean history).
        tool_text = _tool_results_as_text(gathered)
        final_prompt = (
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"DỮ LIỆU TOOL ĐÃ THU THẬP:\n{tool_text}\n\n"
            "Dựa vào dữ liệu trên (đặc biệt giá vé máy bay thật), tổng hợp CostReport ĐẦY ĐỦ."
        )
        report = invoke_structured(
            llm, CostReport, [SystemMessage(_SYNTHESIZE_PROMPT), HumanMessage(content=final_prompt)]
        )
    except Exception as exc:  # noqa: BLE001
        return {"errors": [error_label("cost", exc)]}

    report = _finalize(report, trip_request)
    return {"cost_report": report.model_dump()}
