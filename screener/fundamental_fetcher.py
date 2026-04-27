import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import date

_cache: dict[tuple[str, date], dict] = {}


def fetch_fundamentals(tickers: list[str]) -> dict[str, dict]:
    """비-SKIP 종목의 펀더멘털 데이터 병렬 조회. 당일 캐싱 적용."""
    today = date.today()
    results = {}
    to_fetch = []

    for t in tickers:
        key = (t, today)
        if key in _cache:
            results[t] = _cache[key]
        else:
            to_fetch.append(t)

    if not to_fetch:
        return results

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_fetch_one, t): t for t in to_fetch}
        for fut, ticker in futures.items():
            try:
                data = fut.result(timeout=10)
            except (FuturesTimeoutError, Exception):
                data = {}
            _cache[(ticker, today)] = data
            results[ticker] = data

    return results


def _fetch_one(ticker: str) -> dict:
    t = yf.Ticker(ticker)

    # 1. 실적 발표일
    days_to_earnings = None
    try:
        cal = t.calendar
        if cal is not None and 'Earnings Date' in cal:
            raw = cal['Earnings Date']
            next_dt = raw[0] if isinstance(raw, list) else raw
            if hasattr(next_dt, 'date'):
                next_dt = next_dt.date()
            days_to_earnings = (next_dt - date.today()).days
    except Exception:
        pass

    # 2. Short Ratio + info
    short_ratio = None
    analyst_target = None
    recommendation = ""
    try:
        info = t.info or {}
        short_ratio = info.get('shortRatio')
        analyst_target = info.get('targetMeanPrice')
        recommendation = info.get('recommendationKey', '')
    except Exception:
        pass

    return {
        'days_to_earnings': days_to_earnings,
        'short_ratio': short_ratio,
        'analyst_target': analyst_target,
        'recommendation': recommendation,
    }
