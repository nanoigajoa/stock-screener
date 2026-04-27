"""
Google Trends 관심도 지수 조회 (pytrends).
- 최대 5개 키워드를 묶어 배치 요청 (pytrends 제한)
- TTL 24h 메모리 캐시
- rate limit 방지를 위해 배치 간 1초 딜레이
"""
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[int, datetime]] = {}
_TTL = 86400  # 24h


def _is_fresh(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    _, fetched_at = _cache[ticker]
    return (datetime.now() - fetched_at).total_seconds() < _TTL


def get_trend_scores(tickers: list[str]) -> dict[str, int]:
    """티커 리스트의 Google Trends 관심도 지수 반환. {ticker: 0~100}"""
    result = {}
    to_fetch = [t for t in tickers if not _is_fresh(t)]

    # 캐시 히트
    for t in tickers:
        if _is_fresh(t):
            result[t] = _cache[t][0]

    if not to_fetch:
        return result

    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
    except ImportError:
        logger.warning("[Trends] pytrends 미설치 — 스킵")
        return result
    except Exception as e:
        logger.warning(f"[Trends] 초기화 실패: {e}")
        return result

    # 5개씩 배치
    for i in range(0, len(to_fetch), 5):
        batch = to_fetch[i:i + 5]
        try:
            pytrends.build_payload(batch, timeframe='today 1-m', geo='US')
            df = pytrends.interest_over_time()
            if df is not None and not df.empty:
                for ticker in batch:
                    if ticker in df.columns:
                        score = int(df[ticker].iloc[-1])
                        _cache[ticker] = (score, datetime.now())
                        result[ticker] = score
                    else:
                        _cache[ticker] = (0, datetime.now())
                        result[ticker] = 0
            else:
                for ticker in batch:
                    _cache[ticker] = (0, datetime.now())
                    result[ticker] = 0
        except Exception as e:
            logger.warning(f"[Trends] 배치 조회 실패 {batch}: {e}")
            for ticker in batch:
                result[ticker] = 0

        if i + 5 < len(to_fetch):
            time.sleep(1)  # rate limit

    logger.info(f"[Trends] 완료: {len(result)}개")
    return result
