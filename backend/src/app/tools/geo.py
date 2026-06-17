"""Geoapify tools: geocode an area to coordinates, then find real POIs nearby.

Two-phase recommendation grounding: the LLM reasons about places by NAME (Mỹ Khê,
Đà Nẵng) while the tools handle the area→coordinates→POI flow internally. Returns
real restaurants/hotels with distance + cuisine category — replacing the old
hallucinated place names. Prices are not provided by Geoapify (POIs only), so the
agent estimates from category — but the place name/area/distance are always real.

API key via GEOAPIFY_API_KEY env var. Graceful degradation: missing key or any API
failure returns an empty result with a note, so the agent can fall back to
reasoning instead of crashing.
"""

import json
import os
import urllib.parse
import urllib.request

from langchain_core.tools import tool

_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
_PLACES_URL = "https://api.geoapify.com/v2/places"
_DEFAULT_RADIUS_M = 3000  # ~3km around the area center
_DEFAULT_LIMIT = 10


def _get(url: str, params: dict) -> dict | None:
    """GET Geoapify with params; return parsed JSON or None on any failure."""
    key = os.getenv("GEOAPIFY_API_KEY")
    if not key:
        return None
    full = f"{url}?{urllib.parse.urlencode({**params, 'apiKey': key})}"
    try:
        with urllib.request.urlopen(full, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:  # noqa: BLE001 — any failure degrades to None (caller falls back)
        return None


def _geocode(area: str, city: str) -> dict | None:
    """Resolve "area, city, Việt Nam" to lat/lon. Returns None if not found."""
    text = f"{area}, {city}, Việt Nam"
    data = _get(
        _GEOCODE_URL,
        {"text": text, "filter": "countrycode:vn", "limit": 1, "lang": "vi", "format": "json"},
    )
    if not data or not data.get("results"):
        return None
    r = data["results"][0]
    if r.get("lat") is None or r.get("lon") is None:
        return None
    return {
        "lat": r["lat"],
        "lon": r["lon"],
        "formatted": r.get("formatted", text),
        "confidence": r.get("rank", {}).get("confidence"),
    }


def _places(lat: float, lon: float, categories: str, keyword: str = "") -> list[dict]:
    """Query POIs around a point by Geoapify category. Returns compact dicts."""
    params = {
        "categories": categories,
        "filter": f"circle:{lon},{lat},{_DEFAULT_RADIUS_M}",
        "bias": f"proximity:{lon},{lat}",
        "limit": str(_DEFAULT_LIMIT),
        "lang": "vi",
    }
    if keyword:
        params["name"] = keyword
    data = _get(_PLACES_URL, params)
    if not data:
        return []
    out = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        name = p.get("name")
        if not name:
            continue
        out.append(
            {
                "name": name,
                "address": p.get("formatted", ""),
                "distance_m": p.get("distance"),
                "categories": p.get("categories", []),
            }
        )
    return out


@tool
def find_restaurants(area: str, city: str, keyword: str = "") -> str:
    """Tìm quán ăn / nhà hàng / cafe THẬT quanh một khu vực.

    Args:
        area: Khu vực cụ thể (ví dụ "Mỹ Khê", "phố cổ", "Sơn Trà").
        city: Thành phố (ví dụ "Đà Nẵng", "Hội An", "Phú Quốc").
        keyword: Từ khóa món/quán tùy chọn (ví dụ "hải sản", "phở"). Để trống nếu
            không cần lọc theo món.

    Trả về JSON: list quán thật với tên, địa chỉ, khoảng cách (mét) và loại ẩm thực
    (Vietnamese, Korean, seafood...). Dùng thay vì tự bịa tên quán. KHÔNG có giá —
    bạn ước lượng từ loại ẩm thực.
    """
    geo = _geocode(area, city)
    if not geo:
        return json.dumps(
            {"area": area, "city": city, "restaurants": [], "note": "không geocode được"},
            ensure_ascii=False,
        )
    cats = "catering.restaurant,catering.cafe"
    results = _places(geo["lat"], geo["lon"], cats, keyword)
    return json.dumps(
        {"area": area, "city": city, "center": geo["formatted"], "restaurants": results},
        ensure_ascii=False,
    )


@tool
def find_hotels(area: str, city: str) -> str:
    """Tìm khách sạn / chỗ ở THẬT quanh một khu vực.

    Args:
        area: Khu vực cụ thể (ví dụ "Mỹ Khê", "phố cổ", "sân bay").
        city: Thành phố (ví dụ "Đà Nẵng", "Phú Quốc").

    Trả về JSON: list khách sạn thật với tên, địa chỉ, khoảng cách (mét). Dùng thay
    vì tự bịa tên khách sạn. KHÔNG có giá — bạn ước lượng từ hạng khách sạn.
    """
    geo = _geocode(area, city)
    if not geo:
        return json.dumps(
            {"area": area, "city": city, "hotels": [], "note": "không geocode được"},
            ensure_ascii=False,
        )
    cats = "accommodation.hotel,accommodation.guest_house,accommodation.apartment"
    results = _places(geo["lat"], geo["lon"], cats)
    return json.dumps(
        {"area": area, "city": city, "center": geo["formatted"], "hotels": results},
        ensure_ascii=False,
    )
