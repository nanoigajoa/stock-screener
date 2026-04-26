import time
from finviz.screener import Screener
from config import FINVIZ_FILTERS

# ETF 패턴 — 이름에 포함되면 제거
_ETF_KEYWORDS = ("ETF", "FUND", "TRUST", "SHARES", "INDEX", "NOTES", "PROSHARES")


def _is_etf(ticker: str, company_name: str) -> bool:
    name_upper = company_name.upper()
    return any(kw in name_upper for kw in _ETF_KEYWORDS)


def get_filtered_tickers(retries: int = 3) -> list[str]:
    """Finviz 필터 적용 후 ETF 제거한 티커 리스트 반환."""
    filters = [f"{k}_{v}" for k, v in FINVIZ_FILTERS.items()]

    for attempt in range(retries):
        try:
            screener = Screener(filters=filters, table="Overview", order="ticker")
            rows = screener.data if screener.data else []
            break
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"[Finviz] 연결 실패: {e}")
                return []

    if not rows:
        print("[Finviz] 필터 조건에 맞는 종목 없음.")
        return []

    all_tickers = [(r.get("Ticker", ""), r.get("Company", "")) for r in rows]
    tickers = [t for t, name in all_tickers if t and not _is_etf(t, name)]

    removed = len(all_tickers) - len(tickers)
    print(f"[Finviz] {len(all_tickers)}개 발견 → ETF {removed}개 제거 → 개별주 {len(tickers)}개")
    return tickers
