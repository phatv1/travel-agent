"""Cost tools: deterministic computation for guaranteed correctness.

These are pure functions exposed as LangChain tools so the cost agent can call
them during its tool-gathering phase. But the agent node also recomputes total
and status deterministically afterward — the LLM's tool calls showcase the
agentic loop, while the final values never depend on LLM arithmetic.
"""

import re

import requests
from langchain_core.tools import tool

# Conservative fixed rate used only to parse free-text USD amounts into VND
# (e.g. "100 USD" budget). Live currency conversion is done by convert_currency.
_VND_PER_USD = 25_000

# Recognized Vietnamese/English amount units, normalized for matching.
_UNIT_MULTIPLIERS = {
    "triệu": 1_000_000,
    "trieu": 1_000_000,
    "tr": 1_000_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "nghìn": 1_000,
    "nghin": 1_000,
    "ngàn": 1_000,
    "ngan": 1_000,
    "k": 1_000,
    "usd": _VND_PER_USD,
    "$": _VND_PER_USD,
}


def parse_budget_vnd(text: str | None) -> int | None:
    """Parse a free-text budget string into VND, or None if unparseable.

    Handles "20 triệu", "25tr", "khoảng 20 triệu VND", "1000 USD", "25,000,000".
    """
    if not text:
        return None
    t = text.lower().strip()
    m = re.search(
        r"([\d][\d.,]*)\s*(triệu|trieu|tr|m\b|million|nghìn|nghin|ngàn|ngan|k\b|usd|\$)?", t
    )
    if not m:
        return None
    num_str = m.group(1).replace(",", "").replace(".", "")
    try:
        num = int(num_str)
    except ValueError:
        return None
    unit = (m.group(2) or "").strip()
    multiplier = _UNIT_MULTIPLIERS.get(unit)
    return num * multiplier if multiplier else num


def check_budget_status_impl(total_vnd: int, budget_vnd: int) -> str:
    """Pure budget comparison: within / slight-over (<=10%) / over."""
    if total_vnd <= budget_vnd:
        return "within_budget"
    if total_vnd <= budget_vnd * 1.1:
        return "slightly_over_budget"
    return "over_budget"


@tool
def check_budget_status(total_vnd: int, budget_vnd: int) -> str:
    """So sánh tổng chi phí với ngân sách (đều là số VND).

    Args:
        total_vnd: Tổng chi phí mỗi người (VND).
        budget_vnd: Ngân sách mỗi người (VND).

    Trả về trạng thái: within_budget / slightly_over_budget / over_budget.
    Dùng để đánh giá chính xác xem chuyến đi có vượt ngân sách không.
    """
    return check_budget_status_impl(total_vnd, budget_vnd)


@tool
def add(a: int, b: int) -> str:
    """Cộng hai số (VND). Dùng để cộng các khoản chi phí."""
    return str(a + b)


@tool
def multiply(a: int, b: int) -> str:
    """Nhân hai số (VND). Dùng để tính tổng khi biết đơn giá × số lượng.

    Ví dụ: giá KS/đêm × số đêm; giá quán/người × số người; vé × số lượng.
    """
    return str(a * b)


@tool
def divide(a: int, b: int) -> str:
    """Chia hai số. Dùng để quy đổi về mỗi người hoặc mỗi đêm.

    Ví dụ: tổng nhóm KS / số người; tổng quán / số bữa.
    """
    if b == 0:
        return "lỗi: chia cho 0"
    return str(round(a / b))


@tool
def search_price(query: str) -> str:
    """Tìm giá (VND) cho một mục cụ thể qua DuckDuckGo (blog/bài báo).

    Args:
        query: Câu truy vấn tự nhiên. Ví dụ:
            - "giá phòng khách sạn Seven Sea Đà Nẵng"
            - "vé Bà Nà Hills 2026"
            - "giá nhà hàng hải sản Bé Anh Đà Nẵng"

    Trả về JSON: list snippet với tiêu đề và mô tả (thường chứa giá thật).
    Dùng để lấy giá THẬT cho từng khách sạn/quán/địa điểm đã recommend, thay vì
    ước lượng. Trích số tiền VND từ mô tả.
    """
    import json

    from ddgs import DDGS  # lazy

    try:
        with DDGS() as ddgs:
            results = [
                {"title": r.get("title", ""), "body": r.get("body", "")}
                for r in ddgs.text(query, max_results=4)
            ]
        return json.dumps({"query": query, "results": results}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {"query": query, "results": [], "error": str(exc)[:120]}, ensure_ascii=False
        )


@tool
def convert_currency(amount_vnd: int, target_currency: str) -> str:
    """Quy đổi số tiền VND sang USD, EUR, ... theo tỷ giá THẬT (mới nhất).

    Args:
        amount_vnd: Số tiền VND.
        target_currency: Mã tiền tệ đích, ví dụ "USD", "EUR", "JPY".

    Dùng khi cần trình bày chi phí bằng ngoại tệ để user dễ hình dung
    (đặc biệt user quốc tế). Lấy tỷ giá live từ open.er-api.com (miễn phí,
    không cần key).
    """
    target = target_currency.upper().strip()
    if amount_vnd < 0:
        return "lỗi: số tiền âm"
    try:
        resp = requests.get(
            f"https://open.er-api.com/v6/latest/VND", timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return f"lỗi mạng: không lấy được tỷ giá ({exc})"
    if data.get("result") != "success":
        return f"lỗi API tỷ giá: {data.get('error-type', 'không rõ')}"
    rate = data.get("rates", {}).get(target)
    if rate is None:
        return f"không hỗ trợ mã tiền tệ '{target_currency}'"
    converted = round(amount_vnd * rate)
    return (
        f"{amount_vnd:,} VND = {converted:,} {target} "
        f"(1 VND ≈ {rate:.6f} {target}, cập nhật {data.get('time_last_update_utc', 'N/A')})"
    )
