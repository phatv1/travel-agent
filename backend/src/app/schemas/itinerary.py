from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScheduleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        description=(
            "Một hoạt động trong lịch trình; dùng để frontend hiển thị và Cost Agent đọc. "
            "Ví dụ: Sáng dạo biển Mỹ Khê, Chiều tham quan chùa Linh Ứng."
        ),
    )

    time_slot: Literal["morning", "afternoon", "evening", "full_day", "flexible"] | None = Field(
        default=None,
        description=(
            "Khung thời gian của hoạt động; giúp Recommendation Agent gợi ý quán ăn "
            "đúng bữa."
        ),
    )

    location_hint: str | None = Field(
        default=None,
        description=(
            "Tên địa điểm hoặc khu vực chính của hoạt động; dùng để map lịch trình "
            "với hotel, restaurant. Ví dụ: Mỹ Khê, Sơn Trà, Hội An."
        ),
    )


class DayPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(
        description="Thứ tự ngày trong chuyến đi; dùng để sắp xếp lịch trình. Ví dụ: 1, 2, 3.",
    )

    title: str = Field(
        description=(
            "Tiêu đề ngắn của ngày; dùng để user hiểu nhanh chủ đề ngày đó. "
            "Ví dụ: Biển Mỹ Khê và Sơn Trà, Khám phá Hội An."
        ),
    )

    area: str | None = Field(
        default=None,
        description=(
            "Khu vực chính trong ngày; dùng để gợi ý khách sạn/quán ăn gần lịch trình. "
            "Ví dụ: Sơn Trà, Quận 1 TP.HCM, phố cổ Hội An."
        ),
    )

    schedule: list[ScheduleItem] = Field(
        default_factory=list,
        description="Danh sách hoạt động trong ngày; mỗi hoạt động có thể có chi phí ước lượng.",
    )

    notes: list[str] = Field(
        default_factory=list,
        description=(
            "Ghi chú ngắn cho ngày đó; dùng để giải thích lưu ý hoặc giả định. "
            "Ví dụ: nên đi sớm, lịch nhẹ phù hợp người lớn tuổi."
        ),
    )


class ItineraryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(
        description=(
            "Điểm đến của lịch trình; dùng để xác nhận itinerary đang áp dụng cho khu vực nào."
        ),
    )

    summary: str = Field(
        description=(
            "Tóm tắt ngắn về lịch trình; dùng để Supervisor tổng hợp câu trả lời cuối. "
            "Ví dụ: Lịch trình 5 ngày ở Đà Nẵng, tập trung biển, hải sản và di chuyển nhẹ."
        ),
    )

    days: list[DayPlan] = Field(
        default_factory=list,
        description="Danh sách lịch trình theo ngày; đây là output chính của Itinerary Agent.",
    )

    assumptions: list[str] = Field(
        default_factory=list,
        description=(
            "Các giả định khi lập lịch trình; dùng khi user thiếu thông tin "
            "hoặc nói sao cũng được. "
            "Ví dụ: giả định đi 4 ngày 3 đêm, giả định lịch nhẹ."
        ),
    )