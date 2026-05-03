import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import date
from screener.cache_manager import cache

def fetch_fundamentals(tickers: list[str]) -> dict[str, dict]:
    """비-SKIP 종목의 펀더멘털 데이터 병렬 조회. 당일 캐싱 적용."""
    today_str = date.today().isoformat()
    results = {}
    to_fetch = []

    for t in tickers:
        cache_key = f"fundamental_{t}_{today_str}"
        cached_data = cache.get(cache_key)
        if cached_data:
            results[t] = cached_data
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
            
            cache_key = f"fundamental_{ticker}_{today_str}"
            cache.set(cache_key, data, expire=86400) # 24h
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

    # 2. Short Ratio + info + Company Details
    short_ratio = None
    analyst_target = None
    recommendation = ""
    short_name = ""
    website = ""
    try:
        info = t.info or {}
        short_ratio = info.get('shortRatio')
        analyst_target = info.get('targetMeanPrice')
        recommendation = info.get('recommendationKey', '')
        short_name = info.get('shortName', '')
        website = info.get('website', '')
    except Exception:
        pass

    return {
        'days_to_earnings': days_to_earnings,
        'short_ratio': short_ratio,
        'analyst_target': analyst_target,
        'recommendation': recommendation,
        'short_name': short_name,
        'website': website,
    }
