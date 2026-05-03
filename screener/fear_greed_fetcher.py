"""
공포탐욕지수 (Fear & Greed Index) 자체 계산.
VIX + SPY 125일 이동평균 모멘텀 2개 지표 가중 합산.
- yfinance만 사용, API 키 불필요
- TTL 6h 디스크 캐시 (persistent)
"""
import logging
import time
from datetime import datetime
import yfinance as yf
from screener.cache_manager import cache

logger = logging.getLogger(__name__)

_TTL = 21600  # 6h
_CACHE_KEY = "fear_greed_data"

_LABELS = [
    (25,  "극단적 공포 😱"),
    (45,  "공포 😰"),
    (56,  "중립 😐"),
    (75,  "탐욕 😀"),
    (101, "극단적 탐욕 🤑"),
]


def _is_fresh() -> bool:
    return _CACHE_KEY in cache


def get_fear_greed() -> dict:
    """공포탐욕지수 반환. 캐시 미준비 시 즉시 계산."""
    if not _is_fresh():
        _fetch()
    val = cache.get(_CACHE_KEY)
    return val if val else {}


def _fetch() -> None:
    t0 = time.perf_counter()
    try:
        # yf.Ticker().history() 사용 — download()와 달리 MultiIndex 없음
        # 1. VIX: 낮을수록 탐욕. 10→100점, 40→0점
        vix_df = yf.Ticker("^VIX").history(period="5d")
        if vix_df.empty:
            return
        vix = float(vix_df["Close"].dropna().iloc[-1])
        vix_score = max(0.0, min(100.0, (40 - vix) / 30 * 100))

        # 2. SPY 60일 모멘텀: MA 위 = 탐욕. ±10% 범위 → 0~100 정규화
        close_df = yf.Ticker("SPY").history(period="4mo")
        if close_df.empty:
            return
        close = close_df["Close"].dropna()
        ma60 = close.rolling(60).mean()
        pct = (float(close.iloc[-1]) - float(ma60.iloc[-1])) / float(ma60.iloc[-1]) * 100
        mom_score = max(0.0, min(100.0, (pct + 10) / 20 * 100))

        score = round(vix_score * 0.5 + mom_score * 0.5)
        label = next(lbl for ceiling, lbl in _LABELS if score < ceiling)

        data = {
            "score":      score,
            "label":      label,
            "vix":        round(vix, 1),
            "fetched_at": datetime.now(),
        }
        cache.set(_CACHE_KEY, data, expire=_TTL)
        logger.info(f"[FearGreed] {score} {label} | VIX {vix:.1f} | 모멘텀 {pct:+.1f}% ({time.perf_counter()-t0:.1f}s)")

    except Exception as e:
        logger.warning(f"[FearGreed] 계산 실패: {e}")
