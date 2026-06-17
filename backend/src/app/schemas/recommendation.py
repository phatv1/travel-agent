from pydantic import BaseModel, ConfigDict, Field


class RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Tên khách sạn, quán ăn hoặc lựa chọn được đề xuất; dùng để frontend hiển thị. "
            "Ví dụ: khách sạn khu Mỹ Khê, quán hải sản Sơn Trà."
        ),
    )

    area: str | None = Field(
        default=None,
        description=(
            "Khu vực của lựa chọn; dùng để kiểm tra có gần lịch trình hay không. "
            "Ví dụ: Mỹ Khê, Quận 1 TP.HCM, Sơn Trà, phố cổ Hội An."
        ),
    )

    description: str | None = Field(
        default=None,
        description=(
            "Mô tả ngắn lựa chọn này là gì; dùng để user hiểu nhanh option. "
            "Ví dụ: khách sạn gần biển có hồ bơi, quán hải sản hợp bữa tối."
        ),
    )

    reason: str = Field(
        description=(
            "Lý do lựa chọn này phù hợp; dùng để giải thích recommendation. "
            "Ví dụ: gần lịch trình, hợp ngân sách, phù hợp gia đình, đúng sở thích hải sản."
        ),
    )


class RecommendationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hotels: list[RecommendationItem] = Field(
        default_factory=list,
        description="Danh sách gợi ý lưu trú; dùng cho frontend và Cost Agent.",
    )

    restaurants: list[RecommendationItem] = Field(
        default_factory=list,
        description="Danh sách gợi ý ăn uống; dùng cho frontend và Cost Agent.",
    )

    assumptions: list[str] = Field(
        default_factory=list,
        description=(
            "Các giả định khi đề xuất; dùng khi thiếu budget, ngày đi hoặc preference. "
            "Ví dụ: giả định khách sạn gần trung tâm, giả định 2 bữa chính mỗi ngày."
        ),
    )