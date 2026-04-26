import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import date
from config import DATA_PERIOD, DATA_INTERVAL

_cache: dict[str, tuple[date, pd.DataFrame]] = {}


def fetch_ohlcv(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """티커 리스트의 OHLCV 데이터 수집. 당일 캐싱 적용."""
    today = date.today()
    result: dict[str, pd.DataFrame] = {}
    to_fetch = []

    for t in tickers:
        if t in _cache and _cache[t][0] == today:
            result[t] = _cache[t][1]
        else:
            to_fetch.append(t)

    if not to_fetch:
        return result

    print(f"[Fetcher] {len(to_fetch)}개 종목 데이터 수집 중...")
    try:
        raw = yf.download(
            to_fetch,
            period=DATA_PERIOD,
            interval=DATA_INTERVAL,
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=False,   # Celery 워커 내 pickle 충돌 방지
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

            _cache[ticker] = (today, df)
            result[ticker] = df
        except Exception:
            print(f"[Fetcher] {ticker}: 파싱 실패 → skip")

    print(f"[Fetcher] 수집 완료: {len(result)}/{len(to_fetch)}개")
    return result


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
