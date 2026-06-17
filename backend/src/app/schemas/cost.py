from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CostItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Tên nhóm chi phí; dùng để frontend render bảng hoặc chart. "
            "Ví dụ: Di chuyển, Lưu trú, Ăn uống, Hoạt động, Dự phòng."
        ),
    )

    amount_vnd: int | None = Field(
        default=None,
        description=(
            "Số tiền ước lượng bằng VND cho nhóm chi phí này; dùng để tính tổng. "
            "Ví dụ: 5000000, 3600000, 1200000; nếu không đủ thông tin thì để null."
        ),
    )

    note: str | None = Field(
        default=None,
        description=(
            "Ghi chú ngắn về cách ước lượng; dùng để giải thích chi phí cho user. "
            "Ví dụ: ước lượng từ khách sạn được đề xuất, chưa gồm vé máy bay."
        ),
    )


class CostReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        description=(
            "Tóm tắt ngắn về chi phí dự kiến; dùng để user hiểu nhanh tổng quan. "
            "Ví dụ: Chi phí dự kiến nằm trong budget 25 triệu nếu chọn khách sạn tầm trung."
        ),
    )

    items: list[CostItem] = Field(
        default_factory=list,
        description="Danh sách nhóm chi phí; dùng để frontend render breakdown và tính tổng.",
    )

    total_vnd: int | None = Field(
        default=None,
        description=(
            "Tổng chi phí ước lượng bằng VND; dùng để so sánh với budget. "
            "Nếu chưa đủ thông tin để tính tổng thì để null."
        ),
    )

    budget_comparison: str | None = Field(
        default=None,
        description=(
            "So sánh với ngân sách user đưa ra; dùng để giải thích vượt hoặc còn dư. "
            "Ví dụ: nằm trong budget 25 triệu, có thể vượt nhẹ, chưa đủ thông tin để so sánh."
        ),
    )

    status: Literal[
        "within_budget",
        "slightly_over_budget",
        "over_budget",
        "unknown_budget",
        "insufficient_info",
    ] = Field(
        default="insufficient_info",
        description=(
            "Trạng thái ngân sách; dùng để frontend hiển thị badge. "
            "within_budget = trong ngân sách; unknown_budget = user chưa nói ngân sách."
        ),
    )

    assumptions: list[str] = Field(
        default_factory=list,
        description=(
            "Các giả định khi tính chi phí; dùng để minh bạch với user. "
            "Ví dụ: giả định đi 2 người, giả định khách sạn tầm trung."
        ),
    )

    suggestions: list[str] = Field(
        default_factory=list,
        description=(
            "Gợi ý điều chỉnh chi phí; dùng khi plan vượt budget hoặc có thể tối ưu. "
            "Ví dụ: chọn khách sạn xa biển hơn, giảm activity trả phí."
        ),
    )