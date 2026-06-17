"""Itinerary search tools: live web RAG via Wikipedia + DuckDuckGo.

Three complementary tools the itinerary agent orchestrates:
  - list_attractions: extract tourism-related links from a destination's Wikipedia
    page (authoritative list, vs DDG blog noise).
  - get_place_info: a place's Wikipedia summary (structured description, no ads).
  - search_attractions: DuckDuckGo text search (blog/article bodies, often with
    fresh prices) for context Wikipedia lacks.

Wikipedia-API is preferred over the `wikipedia` package: richer (sections, links,
categories), better error handling with retries, and async-ready. All imports are
lazy so the module loads without the deps or network.
"""

import json

from langchain_core.tools import tool

# Keywords that mark a Wikipedia link as a tourist attraction. Used to filter the
# destination page's link list down to actual places worth visiting.
_ATTRACTION_KEYWORDS = (
    "bãi biển", "bai bien", "chùa", "chua", "đền", "den", "cầu", "cau",
    "bán đảo", "ban dao", "sơn trà", "son tra", "bà nà", "ba na", "linh ứng",
    "linh ung", "ngũ hành", "ngu hanh", "bảo tàng", "bao tang", "cáp treo",
    "cap treo", "đèo", "deo", "hang", "thác", "thac", "vườn", "vuon",
    "khu du lịch", "khu du lich", "vinpearl", "sun world",
)


def _filter_attraction_links(links: list[str], destination: str) -> list[str]:
    """Pick links that look like tourist attractions, dropping generic words.

    `destination` is accepted for symmetry with how callers reason about the
    list; the filter is keyword-only (the LLM does destination-relevance filtering).
    """
    _ = destination  # documented above; kept in signature for caller clarity
    out = []
    for link in links:
        low = link.lower()
        # Skip pure generic terms like "Chùa" or "Bãi biển" (category words).
        if low in {"chùa", "đền", "bãi biển", "bán đảo", "cầu", "thác"}:
            continue
        if any(k in low for k in _ATTRACTION_KEYWORDS):
            out.append(link)
    # Dedupe, keep order.
    seen: set[str] = set()
    return [name for name in out if not (name in seen or seen.add(name))]


def _wiki_client():
    import wikipediaapi  # lazy

    return wikipediaapi.Wikipedia(
        user_agent="TravelAgent/1.0 (academic project)", language="vi"
    )


@tool
def list_attractions(destination: str) -> str:
    """Liệt kê các điểm tham quan thật tại một điểm đến, từ trang Wikipedia của nó.

    Args:
        destination: Tên điểm đến (ví dụ "Đà Nẵng", "Phú Quốc", "Hội An").

    Trả về JSON: list tên địa điểm thật (từ links Wikipedia, đã lọc theo từ khóa
    du lịch). Dùng để có danh sách attractions chính xác, không tự bịa. Sau đó có
    thể gọi get_place_info cho từng địa điểm để lấy mô tả chi tiết.
    """
    wiki = _wiki_client()
    page = wiki.page(destination)
    if not page.exists():
        return json.dumps(
            {"destination": destination, "attractions": [], "note": "không tìm thấy trang"},
            ensure_ascii=False,
        )
    attractions = _filter_attraction_links(list(page.links.keys()), destination)
    return json.dumps(
        {"destination": page.title, "attractions": attractions[:20]}, ensure_ascii=False
    )


@tool
def get_place_info(place_name: str) -> str:
    """Lấy mô tả ngắn (tóm tắt Wikipedia tiếng Việt) cho một địa điểm cụ thể.

    Args:
        place_name: Tên địa điểm (ví dụ "Bãi biển Mỹ Khê", "Chùa Linh Ứng").

    Trả về JSON: title + summary (~600 ký tự) từ Wikipedia, hoặc rỗng nếu không
    tìm thấy. Dùng để mô tả chính xác một địa điểm đã chọn.
    """
    wiki = _wiki_client()
    page = wiki.page(place_name)
    if not page.exists():
        return json.dumps(
            {"note": "không tìm thấy trên Wikipedia"}, ensure_ascii=False
        )
    summary = (page.summary or "")[:600]
    return json.dumps(
        {"title": page.title, "summary": summary}, ensure_ascii=False
    )


@tool
def search_events(destination: str, time_preference: str) -> str:
    """Tìm sự kiện, lễ hội, thời tiết theo mùa cho một điểm đến trong khoảng thời gian đi.

    Args:
        destination: Tên điểm đến (ví dụ "Đà Nẵng", "Phú Quốc").
        time_preference: Khoảng thời gian đi (ví dụ "tháng 8", "5 ngày 4 đêm",
            "cuối tuần"). Dùng để nhắm sự kiện đúng mùa.

    Trả về JSON: list snippet với tiêu đề và mô tả về lễ hội, sự kiện, thời tiết mùa.
    Dùng để gợi ý lý do đi + hoạt động đặc biệt theo mùa (ví dụ Lễ hội pháo hoa quốc tế
    Đà Nẵng, mùa hoa anh đào, mùa mưa) thay vì chỉ lập lịch generic.
    """
    from ddgs import DDGS  # lazy

    q = f"sự kiện lễ hội {destination} {time_preference}"
    try:
        with DDGS() as ddgs:
            results = [
                {"title": r.get("title", ""), "body": r.get("body", "")}
                for r in ddgs.text(q, max_results=4)
            ]
        return json.dumps({"query": q, "results": results}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"query": q, "results": [], "error": str(exc)[:120]}, ensure_ascii=False)


@tool
def search_attractions(destination: str, interest: str = "") -> str:
    """Tìm điểm tham quan + thông tin giá qua DuckDuckGo (blog/bài báo, cập nhật).

    Args:
        destination: Tên điểm đến (ví dụ "Đà Nẵng", "Phú Quốc").
        interest: Sở thích tùy chọn để lọc (ví dụ "biển", "đền chùa", "ẩm thực").

    Trả về JSON: list snippet với tiêu đề và mô tả. Nguồn blog/bài báo nên thường
    có thông tin giá vé cập nhật (Wikipedia ít có giá). Dùng song song với
    list_attractions (Wikipedia) để bổ sung thông tin giá và địa điểm mới.
    """
    from ddgs import DDGS  # lazy

    q = f"điểm tham quan {destination} đáng đi"
    if interest:
        q += f" {interest}"
    try:
        with DDGS() as ddgs:
            results = [
                {"title": r.get("title", ""), "body": r.get("body", "")}
                for r in ddgs.text(q, max_results=4)
            ]
        return json.dumps({"query": q, "results": results}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 — degrade to empty, never crash the agent
        return json.dumps(
            {"query": q, "results": [], "error": str(exc)[:120]}, ensure_ascii=False
        )
