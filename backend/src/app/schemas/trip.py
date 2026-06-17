from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TripRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str | None = Field(
        default=None,
        description=(
            "Điểm đến hoặc khu vực chính user muốn đi; dùng để lập lịch trình, "
            "gợi ý địa điểm và ước lượng chi phí. Ví dụ: Nhật Bản, Đà Nẵng, "
            "Quận 1 TP.HCM, Phú Quốc, Hội An, Bà Nà Hills."
        ),
    )

    origin: str | None = Field(
        default=None,
        description=(
            "Điểm xuất phát của user; dùng để ước lượng di chuyển và chi phí. "
            "Ví dụ: TP.HCM, Hà Nội, Quận 1 TP.HCM, sân bay Tân Sơn Nhất."
        ),
    )

    time_preference: str | None = Field(
        default=None,
        description=(
            "Thời gian hoặc độ dài chuyến đi bằng ngôn ngữ tự nhiên; dùng để chia lịch trình. "
            "Ví dụ: 5 ngày 4 đêm, trong tháng 8, cuối tuần, ngày nào cũng được."
        ),
    )

    budget_preference: str | None = Field(
        default=None,
        description=(
            "Ngân sách bằng ngôn ngữ tự nhiên; dùng để chọn mức gợi ý và đánh giá chi phí. "
            "Ví dụ: tầm 25 triệu VND, tối đa 1000 USD, 50-100 triệu, sao cũng được."
        ),
    )

    companions: str | None = Field(
        default=None,
        description=(
            "Số người và kiểu nhóm đi; dùng để điều chỉnh lịch trình, lưu trú và chi phí. "
            "Ví dụ: 2 người, solo, cặp đôi, gia đình có trẻ nhỏ, nhóm bạn 6 người."
        ),
    )

    preferences: str | None = Field(
        default=None,
        description=(
            "Sở thích, yêu cầu hoặc điều muốn tránh; dùng để cá nhân hóa lịch trình, "
            "khách sạn và quán ăn. Ví dụ: thích biển, hải sản, khách sạn gần biển, "
            "lịch nhẹ, không đi bộ nhiều."
        ),
    )

    user_intent: Literal[
        "full_plan",
        "itinerary_only",
        "recommendation_only",
        "cost_only",
    ] = Field(
        default="full_plan",
        description=(
            "Ý định chính của user; dùng để Supervisor route agent. "
            "full_plan = lập kế hoạch đầy đủ; itinerary_only = chỉ lịch trình; "
            "recommendation_only = chỉ gợi ý; cost_only = chỉ chi phí."
        ),
    )