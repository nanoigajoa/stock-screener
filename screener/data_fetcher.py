import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import date, datetime, time as _time
from zoneinfo import ZoneInfo
from config import DATA_PERIOD, DATA_INTERVAL
from screener.cache_manager import cache

_ET = ZoneInfo("America/New_York")


def is_market_open() -> bool:
    """NYSE 기준 장 중 여부 (9:30–16:00 ET, 월–금)."""
    now = datetime.now(_ET)
    return now.weekday() < 5 and _time(9, 30) <= now.time() < _time(16, 0)

def fetch_ohlcv(tickers: list[str], period: str = DATA_PERIOD) -> dict[str, pd.DataFrame]:
    """티커 리스트의 OHLCV 데이터 수집. 당일 캐싱 적용 (기간별 별도 캐시)."""
    today_str = date.today().isoformat()
    result: dict[str, pd.DataFrame] = {}
    to_fetch = []

    for t in tickers:
        cache_key = f"ohlcv_{t}_{period}"
        cached_data = cache.get(cache_key)
        
        # 캐시 구조: (date_str, dataframe)
        if cached_data and cached_data[0] == today_str:
            result[t] = cached_data[1]
        else:
            to_fetch.append(t)

    if not to_fetch:
        return result

    print(f"[Fetcher] {len(to_fetch)}개 종목 데이터 수집 중... (기간: {period})")
    try:
        raw = yf.download(
            to_fetch,
            period=period,
            interval=DATA_INTERVAL,
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as e:
        print(f"[Fetcher] 수집 실패: {e}")
        return result

    for ticker in to_fetch:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                df = raw[ticker].copy()
            else:
                df = raw.copy()

            df.dropna(how="all", inplace=True)
            if len(df) < 30:
                print(f"[Fetcher] {ticker}: 데이터 부족 ({len(df)}일) → skip")
                continue

            cache_key = f"ohlcv_{ticker}_{period}"
            cache.set(cache_key, (today_str, df), expire=86400 * 2) # 안전하게 2일 유지
            result[ticker] = df
        except Exception:
            print(f"[Fetcher] {ticker}: 파싱 실패 → skip")

    print(f"[Fetcher] 수집 완료: {len(result)}/{len(to_fetch)}개")
    return result


def fetch_intraday(ticker: str, interval: str, period: str) -> pd.DataFrame | None:
    """단일 티커 분봉 데이터 수집. 당일 캐싱."""
    today_str = date.today().isoformat()
    cache_key = f"intraday_{ticker}_{interval}_{today_str}"
    
    cached_df = cache.get(cache_key)
    if cached_df is not None:
        return cached_df
        
    try:
        df = yf.Ticker(ticker).history(
            interval=interval, period=period, auto_adjust=True
        )
        if df.index.tzinfo is not None:
            df.index = df.index.tz_localize(None)
        if len(df) < 10:
            return None
            
        cache.set(cache_key, df, expire=86400) # 24h
        return df
    except Exception:
        return None


def _fetch_change(ticker: str) -> float:
    """단일 티커 당일 등락률 조회 (스레드 내부용)."""
    info = yf.Ticker(ticker).fast_info
    prev = info["previousClose"]
    curr = info["lastPrice"]
    if not prev:
        return 0.0
    return ((curr - prev) / prev) * 100


def get_today_change(ticker: str, timeout: int = 6) -> float:
    """당일 등락률(%) 반환. timeout 초 내 응답 없으면 0.0 반환."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_fetch_change, ticker)
        try:
            return fut.result(timeout=timeout)
        except (FuturesTimeoutError, Exception):
            return 0.0


def get_today_changes(tickers: list[str], timeout: int = 6) -> dict[str, float]:
    """여러 티커 당일 등락률 병렬 조회. {ticker: change%} 반환."""
    print(f"[Fetcher] 당일 변동률 조회 중... ({len(tickers)}개)", flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_fetch_change, t): t for t in tickers}
        result = {}
        for fut, ticker in futures.items():
            try:
                result[ticker] = fut.result(timeout=timeout)
            except (FuturesTimeoutError, Exception):
                result[ticker] = 0.0
    return result
