"""Recommendation agent: suggest hotels + restaurants from real Geoapify POIs.

Two-phase pattern (same as cost agent):
  Phase 1 (gather): LLM bind_tools calls find_hotels / find_restaurants for the
    destination (and areas pulled from itinerary when available) to collect real
    POIs with name, address, distance, cuisine.
  Phase 2 (synthesize): LLM produces RecommendationPlan from the gathered POIs as
    text (clean structured output).

Geoapify returns no prices, so the agent estimates cost_vnd from cuisine/category
(honest reasoning, not fabrication) — but the place names, areas, and distances
are always real, fixing the 'hallucinated hotel/restaurant' bug.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._llm import error_label, invoke_structured
from app.llms.factory import get_llm
from app.schemas.recommendation import RecommendationPlan
from app.schemas.state import TravelState
from app.schemas.trip import TripRequest
from app.tools.geo import find_hotels, find_restaurants
from app.tools.loop import gather_via_tools

_GATHER_PROMPT = """\
Bạn là chuyên gia lưu trú và ẩm thực. Thu thập địa điểm THẬT qua tool:
- find_hotels(area, city): gọi cho destination (và các khu vực chính từ itinerary
  nếu có) để lấy danh sách khách sạn thật. BẮT BUỘC gọi ít nhất 1 lần.
- find_restaurants(area, city, keyword): gọi cho destination và các khu vực chính.
  Dùng keyword để lọc theo preferences của user (ví dụ "hải sản" nếu user thích
  hải sản). BẮT BUỘC gọi ít nhất 1 lần.
- area nên là khu vực cụ thể (Mỹ Khê, phố cổ, Sơn Trà) nếu biết; nếu không rõ,
  dùng destination làm area.
Gọi đủ tool rồi thì dừng (không cần trả lời thêm).
"""

_SYNTHESIZE_PROMPT = """\
Bạn là chuyên gia gợi ý lưu trú và ẩm thực. Từ TripRequest và danh sách địa điểm
THẬT đã thu thập (qua Geoapify), tổng hợp thành RecommendationPlan:

- hotels[]: 3-5 khách sạn từ tool (dùng TÊN THẬT, KHÔNG bịa tên).
  + area: từ dữ liệu tool.
  + description: ghi sức chứa phòng + tiện ích (ví dụ "phòng đôi 2 người, có hồ bơi").
  + KHÔNG điền cost_vnd (đã bỏ trường này — Cost Agent sẽ tự tìm giá).
- restaurants[]: 3-5 quán từ tool (dùng TÊN THẬT, KHÔNG bịa tên).
  + area: từ dữ liệu tool.
  + description: loại ẩm thực (Vietnamese, hải sản, Korean...).
- reason: dựa trên distance (gần khu vực), loại ẩm thực phù hợp preferences.
- assumptions: ghi giả định nếu cần.

LƯU Ý: Chỉ dùng địa điểm THẬT đã thu thập. KHÔNG bịa tên khách sạn/quán ăn.
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
            lines.append(f"  → kết quả: {str(m.content)[:600]}")
    return "\n".join(lines)


def recommendation(state: TravelState) -> dict:
    """Suggest hotels + restaurants from real Geoapify POIs gathered via tool-calling."""
    trip_request = TripRequest.model_validate(state.get("trip_request") or {})
    context = {
        "trip_request": trip_request.model_dump(),
        "itinerary_areas": [
            d.get("area") for d in (state.get("itinerary") or {}).get("days", []) if d.get("area")
        ],
    }

    try:
        llm = get_llm()

        # Phase 1: gather real POIs via tool-calling (agentic showcase).
        tools = [find_hotels, find_restaurants]
        gathered = gather_via_tools(llm, tools, _gather_messages(context))

        # Phase 2: structured RecommendationPlan with POIs as text.
        tool_text = _tool_results_as_text(gathered)
        final_prompt = (
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"ĐỊA ĐIỂM THẬT ĐÃ THU THẬP:\n{tool_text}\n\n"
            "Dựa vào danh sách thật trên, tổng hợp RecommendationPlan ĐẦY ĐỦ."
        )
        plan = invoke_structured(
            llm,
            RecommendationPlan,
            [SystemMessage(_SYNTHESIZE_PROMPT), HumanMessage(content=final_prompt)],
        )
    except Exception as exc:  # noqa: BLE001
        return {"errors": [error_label("recommendation", exc)]}
    return {"recommendations": plan.model_dump()}
