"""Itinerary agent: plan days from real attractions via tool-calling + RAG.

Split into two focused LLM calls instead of one overloaded prompt:
  Phase 1 (gather + pick): tool-calling loop collects real attractions
    (list_attractions / get_place_info / search_attractions), then a focused call
    returns ONLY the destination-relevant attraction names — filtering Wiki link
    noise (e.g. Cửa Tùng=Quảng Trị) which a single overloaded prompt couldn't.
  Phase 2 (schedule): a separate call assigns day/time_slot/area/cost per
    attraction, given the cleaned list. Each call has few rules, so the model
    fills every field instead of selectively ignoring some.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from app.agents._llm import error_label, invoke_structured
from app.llms.factory import get_llm
from app.schemas.itinerary import ItineraryPlan
from app.schemas.state import TravelState
from app.schemas.trip import TripRequest
from app.tools.loop import gather_via_tools
from app.tools.search import (
    get_place_info,
    list_attractions,
    search_attractions,
)

_GATHER_PROMPT = """\
Bạn là chuyên gia du lịch. Thu thập dữ liệu địa điểm THẬT bằng tool:
- list_attractions: BẮT BUỘC gọi đầu tiên cho destination, lấy danh sách địa điểm thật.
  Danh sách CÓ NOISE — nhiều nơi KHÔNG thuộc destination (ví dụ Đà Nẵng nhưng có Cửa Tùng,
  Hải Tiến, Phương Mai từ vùng khác). Bạn phải dùng hiểu biết địa lý để lọc.
- get_place_info: gọi cho 3-5 địa điểm nghi ngờ để kiểm tra Wikipedia summary.
- search_attractions: gọi nếu cần thêm gợi ý destination-specific hoặc thông tin GIÁ VÉ.
Gọi đủ tool rồi thì dừng (không cần trả lời thêm).
"""

_PICK_PROMPT = """\
Bạn là chuyên gia địa lý du lịch. Từ danh sách địa điểm thu thập, chọn ra CHỈ những nơi
THỰC SỰ thuộc {destination} (loại bỏ noise vùng khác). Ví dụ lọc:
- Đà Nẵng: giữ Mỹ Khê, Linh Ứng, Bà Nà, Cầu Rồng; bỏ Cửa Tùng (Quảng Trị), Hải Tiến (Thanh Hóa).
- Phú Quốc: giữ Vinpearl Safari, Hòn Thơm; bỏ nơi khác tỉnh.
Đồng thời ghi giá vé ước lượng (VND/người) nếu search_attractions có đề cập, 0 cho miễn phí,
null nếu không rõ. Trả về list ĐỦ 5-8 địa điểm để lập lịch.
"""


class PickedAttraction(BaseModel):
    """A destination-relevant attraction, post-filter, with a price hint if known."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Tên địa điểm thật ở ĐÚNG destination.")
    area: str = Field(description="Khu vực (ví dụ Mỹ Khê, Sơn Trà, phố cổ).")
    typical_cost_vnd: int | None = Field(
        default=None,
        description="Giá vé ước lượng VND/người; 0 cho miễn phí; null nếu không rõ.",
    )


class PickedAttractions(BaseModel):
    """Output of phase 1: the cleaned, destination-verified attraction list."""

    model_config = ConfigDict(extra="forbid")

    attractions: list[PickedAttraction] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


_SCHEDULE_PROMPT = """\
Bạn là chuyên gia lập lịch trình. Từ TripRequest và danh sách địa điểm ĐÃ LỌC (chỉ {destination}),
phân bổ thành lịch trình theo ngày. Mỗi hoạt động BẮT BUỘC điền đủ:

- ScheduleItem.text: ngắn, rõ (ví dụ "Dạo biển {destination} khu vực đã chọn").
- ScheduleItem.time_slot: BẮT BUỘC một trong morning / afternoon / evening / full_day.
- ScheduleItem.location_hint: BẮT BUỘC tên địa điểm từ danh sách đã lọc.
- ScheduleItem.cost_vnd: dùng typical_cost_vnd từ danh sách; KHÔNG bịa.

Mỗi ngày BẮT BUỘC điền DayPlan.area (khu vực chính). Ước lượng số ngày từ time_preference
(5 ngày → 5 DayPlan). Phân bổ khu vực hợp lý để giảm di chuyển. assumptions ghi giả định.
"""


def _gather_messages(context: dict, destination: str) -> list:
    prompt = f"Thông tin chuyến đi:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    gather_sys = _GATHER_PROMPT.replace("{destination}", destination)
    return [SystemMessage(gather_sys), HumanMessage(content=prompt)]


def _tool_results_as_text(messages: list) -> str:
    # Flatten the tool-calling conversation into readable text for the next phase.
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


def itinerary(state: TravelState) -> dict:
    """Build a day-by-day itinerary: gather+filter attractions, then schedule them."""
    trip_request = TripRequest.model_validate(state.get("trip_request") or {})
    context = {"trip_request": trip_request.model_dump()}

    try:
        llm = get_llm()

        # Phase 1a: gather real attractions via tool-calling (agentic showcase).
        tools = [list_attractions, get_place_info, search_attractions]
        gathered = gather_via_tools(llm, tools, _gather_messages(context, trip_request.destination))
        tool_text = _tool_results_as_text(gathered)

        # Phase 1b: focused call to FILTER noise and tag prices (single responsibility).
        pick_prompt = (
            f"Điểm đến: {trip_request.destination}\n\n"
            f"DỮ LIỆU ĐỊA ĐIỂM ĐÃ THU THẬP:\n{tool_text}\n\n"
            "Lọc chỉ giữ địa điểm THỰC SỰ thuộc điểm đến, ghi giá nếu có."
        )
        picked = invoke_structured(
            llm,
            PickedAttractions,
            [SystemMessage(_PICK_PROMPT.format(destination=trip_request.destination)),
             HumanMessage(content=pick_prompt)],
        )

        # Phase 2: focused call to SCHEDULE with time_slot/area/cost filled.
        sched_prompt = (
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"DANH SÁCH ĐỊA ĐIỂM ĐÃ LỌC (chỉ {trip_request.destination}):\n"
            f"{picked.model_dump_json(indent=2)}\n\n"
            "Phân bổ thành lịch trình đầy đủ, mỗi hoạt động điền ĐỦ time_slot/location_hint/cost."
        )
        plan = invoke_structured(
            llm,
            ItineraryPlan,
            [SystemMessage(_SCHEDULE_PROMPT.format(destination=trip_request.destination)),
             HumanMessage(content=sched_prompt)],
        )
    except Exception as exc:  # noqa: BLE001
        return {"errors": [error_label("itinerary", exc)]}
    return {"itinerary": plan.model_dump()}
