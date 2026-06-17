"""Request/response models for the public Chat API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(description="Tin nhắn yêu cầu tư vấn du lịch từ người dùng.")


class ChatResponse(BaseModel):
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
