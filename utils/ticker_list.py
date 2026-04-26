"""
티커 자동완성 검색.
Yahoo Finance 실시간 검색 API 사용 (정적 파일 불필요).
"""
import logging
import requests

logger = logging.getLogger(__name__)

_YF_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def search_tickers(q: str, limit: int = 30) -> list[dict]:
    """Yahoo Finance 검색 API로 티커 실시간 조회."""
    if not q or len(q) < 1:
        return []
    try:
        resp = requests.get(
            _YF_SEARCH_URL,
            params={"q": q.upper(), "quotesCount": limit, "newsCount": 0, "listsCount": 0},
            headers=_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        quotes = resp.json().get("quotes", [])
        return [
            {"symbol": item["symbol"], "name": item.get("longname") or item.get("shortname", "")}
            for item in quotes
            if item.get("symbol") and item.get("quoteType") in ("EQUITY", "ETF")
        ][:limit]
    except Exception as e:
        logger.warning(f"[TickerList] 검색 실패 ({q}): {e}")
        return []
