"""
Google Trends 관심도 지수 조회 (pytrends).
- 최대 5개 키워드를 묶어 배치 요청 (pytrends 제한)
- TTL 24h 디스크 캐시 (persistent)
- rate limit 방지를 위해 배치 간 1초 딜레이
- Google 차단 시 hang 방지: 배치당 30초 타임아웃
"""
import time
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from screener.cache_manager import cache

logger = logging.getLogger(__name__)

_TTL = 86400  # 24h
_BATCH_TIMEOUT = 30  # Google 차단 시 무한 hang 방지


def _is_fresh(ticker: str) -> bool:
    cache_key = f"trends_{ticker}"
    return cache_key in cache


def _fetch_batch(pytrends, batch: list[str]) -> dict[str, int]:
    """단일 배치 조회. hang 방지용 타임아웃 래퍼에서 호출."""
    pytrends.build_payload(batch, timeframe='today 1-m', geo='US')
    df = pytrends.interest_over_time()
    result = {}
    if df is not None and not df.empty:
        for ticker in batch:
            result[ticker] = int(df[ticker].iloc[-1]) if ticker in df.columns else 0
    else:
        for ticker in batch:
            result[ticker] = 0
    return result


def get_trend_scores(tickers: list[str]) -> dict[str, int]:
    """티커 리스트의 Google Trends 관심도 지수 반환. {ticker: 0~100}"""
    result = {}
    to_fetch = []

    for t in tickers:
        cache_key = f"trends_{t}"
        if _is_fresh(t):
            result[t] = cache.get(cache_key)
        else:
            to_fetch.append(t)

    if not to_fetch:
        return result

    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(8, 15),
                            requests_args={'headers': {'User-Agent': 'Mozilla/5.0'}})
    except ImportError:
        logger.warning("[Trends] pytrends 미설치 — 스킵")
        return {t: 0 for t in tickers}
    except Exception as e:
        logger.warning(f"[Trends] 초기화 실패: {e}")
        return {t: 0 for t in tickers}

    for i in range(0, len(to_fetch), 5):
        batch = to_fetch[i:i + 5]
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_fetch_batch, pytrends, batch)
                scores = fut.result(timeout=_BATCH_TIMEOUT)
            for ticker, score in scores.items():
                cache_key = f"trends_{ticker}"
                cache.set(cache_key, score, expire=_TTL)
                result[ticker] = score
        except FuturesTimeoutError:
            logger.debug(f"[Trends] 타임아웃 {batch} — Google 차단 추정")
            for ticker in batch:
                cache_key = f"trends_{ticker}"
                cache.set(cache_key, 0, expire=3600) # 차단 시 1시간 후 재시도
                result[ticker] = 0
        except Exception as e:
            logger.debug(f"[Trends] {batch}: {e}")
            for ticker in batch:
                cache_key = f"trends_{ticker}"
                cache.set(cache_key, 0, expire=3600)
                result[ticker] = 0

        if i + 5 < len(to_fetch):
            time.sleep(1)

    non_zero = sum(1 for v in result.values() if v > 0)
    if non_zero:
        logger.info(f"[Trends] 완료: {len(result)}개 (유효 {non_zero}개)")
    else:
        logger.info("[Trends] Google 차단으로 데이터 없음 — 배지 비표시")
    return result
