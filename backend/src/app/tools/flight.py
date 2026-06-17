"""Flight price tool: real-time scraping via fast-flights, with curated fallback.

The LLM provides IATA codes (probe showed it knows common Vietnamese airports:
SGN, DAD, HAN, PQC, HUI...); we only validate the format and search today's date
as a representative estimate when the user gave no specific date. fast-flights is
imported lazily so the module loads even without the dependency or network.
"""

import datetime as _dt
import json
import re

from langchain_core.tools import tool

_IATA_RE = re.compile(r"^[A-Z]{3}$")

# Curated round-trip economy averages (VND) for the most common domestic routes.
# Used only when scraping fails (network/Google block/rate limit). Conservative.
_FALLBACK_PRICES: dict[tuple[str, str], int] = {
    ("SGN", "DAD"): 2_500_000,
    ("HAN", "DAD"): 3_000_000,
    ("SGN", "PQC"): 2_200_000,
    ("HAN", "PQC"): 3_200_000,
    ("SGN", "CXR"): 2_000_000,
    ("HAN", "CXR"): 2_800_000,
    ("SGN", "HUI"): 2_300_000,
    ("HAN", "HUI"): 2_200_000,
}

# Representative stay for round-trip when the user gave no specific return date.
_RETURN_NIGHTS_GUESS = 7


def _is_valid_iata(code: str) -> bool:
    return bool(_IATA_RE.match(code.upper()))


def _scrape_round_trip(origin_iata: str, dest_iata: str) -> dict:
    """Live-scrape round-trip economy prices, searching today's date. Raises on failure."""
    from fast_flights import FlightQuery, Passengers, create_query, get_flights  # lazy

    today = _dt.date.today()
    ret = today + _dt.timedelta(days=_RETURN_NIGHTS_GUESS)
    q = create_query(
        flights=[
            FlightQuery(date=today.isoformat(), from_airport=origin_iata, to_airport=dest_iata),
            FlightQuery(date=ret.isoformat(), from_airport=dest_iata, to_airport=origin_iata),
        ],
        trip="round-trip",
        seat="economy",
        passengers=Passengers(adults=1),
    )
    result = get_flights(q)
    prices = sorted(p for p in (getattr(f, "price", None) for f in result) if p)
    if not prices:
        raise RuntimeError("no prices returned")
    mid = len(prices) // 2
    return {"price_vnd": prices[mid], "min_vnd": prices[0], "max_vnd": prices[-1]}


def _flight_price_impl(origin_iata: str, destination_iata: str) -> dict:
    origin_iata = origin_iata.upper()
    destination_iata = destination_iata.upper()
    if not _is_valid_iata(origin_iata) or not _is_valid_iata(destination_iata):
        return {"price_vnd": None, "source": "invalid", "note": "IATA code không hợp lệ"}
    try:
        data = _scrape_round_trip(origin_iata, destination_iata)
        return {
            "price_vnd": data["price_vnd"],
            "range_vnd": [data["min_vnd"], data["max_vnd"]],
            "source": "live",
            "route": f"{origin_iata}-{destination_iata}",
        }
    except Exception:  # noqa: BLE001 — any scrape failure degrades to fallback
        price = _FALLBACK_PRICES.get((origin_iata, destination_iata)) or _FALLBACK_PRICES.get(
            (destination_iata, origin_iata)
        )
        if price is None:
            return {"price_vnd": None, "source": "unsupported", "note": "không có dữ liệu"}
        return {
            "price_vnd": price,
            "source": "fallback",
            "route": f"{origin_iata}-{destination_iata}",
        }


@tool
def get_flight_price(origin_iata: str, destination_iata: str) -> str:
    """Giá vé máy bay khứ hồi hạng phổ thông trung bình (VND) giữa 2 sân bay.

    Args:
        origin_iata: Mã IATA 3 chữ cái của sân bay đi (ví dụ SGN, HAN).
        destination_iata: Mã IATA 3 chữ cái của sân bay đến (ví dụ DAD, PQC).

    Dữ liệu thời gian thực (Google Flights) khi có thể; có fallback cho đường bay
    phổ biến. Trả về JSON: price_vnd (số VND), source ('live'|'fallback'|'unsupported'|'invalid').
    Dùng để ước lượng chi phí Di chuyển chính xác.
    """
    data = _flight_price_impl(origin_iata, destination_iata)
    return json.dumps(data, ensure_ascii=False)
