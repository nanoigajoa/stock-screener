"""
FRED(연준) 매크로 경제 지표 조회.
- fredapi 대신 requests 직접 사용 (macOS SSL 인증서 이슈 우회)
- TTL 7일 메모리 캐시
- FRED_API_KEY 환경변수 필요 (fred.stlouisfed.org 무료 발급)
"""
import logging
import time
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[dict, datetime]] = {}
_TTL = 604800  # 7일
_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _is_fresh() -> bool:
    if "macro" not in _cache:
        return False
    _, fetched_at = _cache["macro"]
    return (datetime.now() - fetched_at).total_seconds() < _TTL


def refresh_macro() -> None:
    _fetch()


def get_macro_context() -> dict:
    if not _is_fresh():
        _fetch()
    if "macro" in _cache:
        return _cache["macro"][0]
    return {}


def _get_series(series_id: str, api_key: str, limit: int = 20) -> list[float]:
    """FRED 시리즈에서 최근 N개 유효값 반환. 5xx 오류 시 1회 재시도."""
    import time as _time
    params = {
        "series_id":  series_id,
        "api_key":    api_key,
        "file_type":  "json",
        "sort_order": "desc",
        "limit":      max(limit, 30),  # 결측값(.) 여유분 포함
    }
    for attempt in range(2):
        try:
            resp = requests.get(_BASE, params=params, timeout=10)
            if resp.status_code >= 500 and attempt == 0:
                _time.sleep(1)
                continue
            resp.raise_for_status()
            observations = resp.json().get("observations", [])
            return [float(o["value"]) for o in observations if o.get("value") not in (".", None, "")]
        except requests.HTTPError:
            if attempt == 0:
                _time.sleep(1)
                continue
            raise
    return []


def _fetch() -> None:
    from config import FRED_API_KEY
    if not FRED_API_KEY:
        logger.warning("[Macro] FRED_API_KEY 미설정 — 스킵")
        return

    _SERIES = ["FEDFUNDS", "CPIAUCSL", "UNRATE", "T10Y2Y", "VIXCLS"]
    logger.info(f"[Macro] FRED 지표 {len(_SERIES)}개 조회 시작")

    def _safe(series_id: str, default=None):
        t0 = time.perf_counter()
        try:
            vals = _get_series(series_id, FRED_API_KEY)
            val = round(vals[0], 2) if vals else default
            logger.info(f"[Macro]   {series_id}: {val} ({time.perf_counter()-t0:.1f}s)")
            return val
        except Exception as e:
            logger.warning(f"[Macro]   {series_id}: 조회 실패 ({time.perf_counter()-t0:.1f}s) — {e}")
            return default

    fed_funds = _safe("FEDFUNDS")

    # CPI YoY: (현재값 - 13번째 전 값) / 13번째 전 값 * 100
    cpi_yoy = None
    t0 = time.perf_counter()
    try:
        vals = _get_series("CPIAUCSL", FRED_API_KEY, limit=14)
        if len(vals) >= 13:
            cpi_yoy = round((vals[0] - vals[12]) / vals[12] * 100, 1)
        logger.info(f"[Macro]   CPIAUCSL(YoY): {cpi_yoy}% ({time.perf_counter()-t0:.1f}s)")
    except Exception as e:
        logger.warning(f"[Macro]   CPIAUCSL: 조회 실패 ({time.perf_counter()-t0:.1f}s) — {e}")

    unrate = _safe("UNRATE")
    t10y2y = _safe("T10Y2Y")

    # VIX: FRED VIXCLS 실패 시 yfinance fallback (Ticker().history() 사용 — MultiIndex 없음)
    vix = _safe("VIXCLS")
    if vix is None:
        t0 = time.perf_counter()
        try:
            import yfinance as yf
            hist = yf.Ticker("^VIX").history(period="5d")
            if not hist.empty:
                vix = round(float(hist["Close"].dropna().iloc[-1]), 2)
            logger.info(f"[Macro]   VIX(yfinance fallback): {vix} ({time.perf_counter()-t0:.1f}s)")
        except Exception:
            pass

    regime = _judge_regime(fed_funds, t10y2y, vix)

    now = datetime.now()
    data = {
        "fed_funds":  fed_funds,
        "cpi_yoy":    cpi_yoy,
        "unrate":     unrate,
        "t10y2y":     t10y2y,
        "vix":        vix,
        "regime":     regime,
        "fetched_at": now,
        "note":       "기준금리·CPI·실업률 월간 / 장단기금리차·VIX 일간",
    }
    _cache["macro"] = (data, now)
    logger.info(f"[Macro] 로드 완료 → {regime}")


def _judge_regime(fed_funds, t10y2y, vix) -> str:
    if vix and vix > 30:
        return "고변동성 — 방어적 접근 권장"
    if t10y2y is not None and t10y2y < 0:
        return "장단기 역전 — 경기침체 우려"
    if fed_funds and fed_funds > 4.5:
        return "고금리 — 성장주 주의"
    return "안정"
