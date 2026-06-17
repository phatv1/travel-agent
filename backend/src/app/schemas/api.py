"""Request/response models for the public Chat API."""

from pydantic import BaseModel, Field

from app.schemas.session import ToolCallData


class ChatRequest(BaseModel):
    message: str = Field(description="Tin nhắn yêu cầu tư vấn du lịch từ người dùng.")
    session_id: str | None = Field(
        default=None,
        description="ID phiên chat để lưu trữ tin nhắn; nếu null sẽ tạo phiên mới.",
    )


class ChatResponse(BaseModel):
    session_id: str = Field(description="ID phiên chat (tạo mới nếu request không có).")
    message_id: str = Field(description="ID tin nhắn assistant đã lưu.")
    final_answer: str = Field(description="Câu trả lời cuối bằng ngôn ngữ tự nhiên.")
    itinerary: dict | None = Field(
        default=None, description="Lịch trình theo ngày (nếu có)."
    )
    recommendations: dict | None = Field(
        default=None, description="Gợi ý khách sạn/quán ăn (nếu có)."
    )
    cost_report: dict | None = Field(
        default=None, description="Báo cáo chi phí ước lượng (nếu có)."
    )
    tool_calls: list[ToolCallData] | None = Field(
        default=None, description="Trace các bước agent cho thinking panel."
    )
    errors: list[str] | None = Field(
        default=None,
        description="Các lỗi agent nếu có; graph luôn hoàn thành thay vì crash 500.",
    )
