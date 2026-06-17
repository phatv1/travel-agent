"""Build the agent step trace (mock) shown in the thinking panel.

Mirrors the 5 graph nodes with their structured outputs. Real streamed tool
calls / RAG steps will replace this later — the ToolCallData shape is the same.
"""

from app.schemas.session import ToolCallData


def build_trace(message: str, result: dict) -> list[ToolCallData]:
    answer = result.get("final_answer") or ""
    return [
        ToolCallData(
            name="supervisor",
            label="Phân tích yêu cầu",
            icon="🧭",
            status="done",
            input={"message": message},
            output={"trip_request": "(đã trích xuất)"},
        ),
        ToolCallData(
            name="itinerary",
            label="Lập lịch trình",
            icon="🗺️",
            status="done",
            input={},
            output=result.get("itinerary"),
        ),
        ToolCallData(
            name="recommendation",
            label="Gợi ý lưu trú & ăn uống",
            icon="🏨",
            status="done",
            input={},
            output=result.get("recommendations"),
        ),
        ToolCallData(
            name="cost",
            label="Ước lượng chi phí",
            icon="💰",
            status="done",
            input={},
            output=result.get("cost_report"),
        ),
        ToolCallData(
            name="synthesize",
            label="Tổng hợp câu trả lời",
            icon="✨",
            status="done",
            input={},
            output=answer[:200] if answer else None,
        ),
    ]
