from fastapi import APIRouter
from utils.ticker_list import search_tickers

router = APIRouter()


@router.get("/api/tickers")
def get_tickers(q: str = ""):
    """티커 자동완성 검색. Yahoo Finance 실시간."""
    if not q:
        return []
    return search_tickers(q, limit=30)
