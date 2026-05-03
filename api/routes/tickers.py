import logging
import httpx
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

_YF_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


async def _search_tickers(q: str, limit: int = 30) -> list[dict]:
    if not q:
        return []
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=5.0) as client:
            resp = await client.get(
                _YF_SEARCH_URL,
                params={"q": q.upper(), "quotesCount": limit, "newsCount": 0, "listsCount": 0},
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


@router.get("/api/tickers")
async def get_tickers(q: str = ""):
    """티커 자동완성 검색. Yahoo Finance 실시간."""
    return await _search_tickers(q, limit=30)
