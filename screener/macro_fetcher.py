"""
FRED(연준) 매크로 경제 지표 조회.
- fredapi 대신 requests 직접 사용 (macOS SSL 인증서 이슈 우회)
- TTL 7일 디스크 캐시 (persistent)
- FRED_API_KEY 환경변수 필요 (fred.stlouisfed.org 무료 발급)
"""
import logging
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from screener.cache_manager import cache

logger = logging.getLogger(__name__)

_TTL = 604800  # 7일
_BASE = "https://api.stlouisfed.org/fred/series/observations"
_fetch_lock = threading.Lock()
_CACHE_KEY = "macro_data"

_SIDEBAR_KEY = "sidebar_live"
_SIDEBAR_TTL = 900  # 15분
_sidebar_lock = threading.Lock()

def _is_fresh() -> bool:
    return _CACHE_KEY in cache


def refresh_macro() -> None:
    _fetch()


def get_macro_context() -> dict:
    """캐시가 신선하면 즉시 반환, 아니면 백그라운드에서 갱신 후 기존값 반환."""
    if _is_fresh():
        return cache.get(_CACHE_KEY)
        
    threading.Thread(target=_fetch, daemon=True).start()
    
    # 캐시가 만료되었더라도 데이터가 남아있으면 일단 반환 (diskcache는 만료 시 삭제하므로 별도 저장 필요할 수도 있으나, 
    # 여기서는 간단히 fresh 체크만 함. 만료된 경우 None 반환됨)
    val = cache.get(_CACHE_KEY)
    return val if val else {}


def _get_series(series_id: str, api_key: str, limit: int = 20) -> list[float]:
    """FRED 시리즈에서 최근 N개 유효값 반환. 5xx 오류 시 1회 재시도."""
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
                time.sleep(1)
                continue
            resp.raise_for_status()
            observations = resp.json().get("observations", [])
            return [float(o["value"]) for o in observations if o.get("value") not in (".", None, "")]
        except requests.HTTPError:
            if attempt == 0:
                time.sleep(1)
                continue
            raise
    return []


def _fetch() -> None:
    if not _fetch_lock.acquire(blocking=False):
        return  # 다른 스레드가 이미 가져오는 중
    try:
        from config import FRED_API_KEY
        if not FRED_API_KEY:
            logger.warning("[Macro] FRED_API_KEY 미설정 — 스킵")
            return

        logger.info("[Macro] FRED 지표 병렬 조회 시작")
        t_total = time.perf_counter()

        def _safe(series_id: str, limit: int = 20):
            t0 = time.perf_counter()
            try:
                vals = _get_series(series_id, FRED_API_KEY, limit)
                val = round(vals[0], 2) if vals else None
                logger.info(f"[Macro]   {series_id}: {val} ({time.perf_counter()-t0:.1f}s)")
                return series_id, vals, val
            except Exception as e:
                logger.warning(f"[Macro]   {series_id}: 조회 실패 ({time.perf_counter()-t0:.1f}s) — {e}")
                return series_id, [], None

        results = {}
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {
                ex.submit(_safe, "FEDFUNDS"):    "FEDFUNDS",
                ex.submit(_safe, "CPIAUCSL", 14): "CPIAUCSL",
                ex.submit(_safe, "UNRATE"):       "UNRATE",
                ex.submit(_safe, "T10Y2Y"):       "T10Y2Y",
                ex.submit(_safe, "VIXCLS"):       "VIXCLS",
            }
            for f in as_completed(futures):
                series_id, vals, val = f.result()
                results[series_id] = (vals, val)

        fed_funds = results["FEDFUNDS"][1]
        unrate    = results["UNRATE"][1]
        t10y2y    = results["T10Y2Y"][1]
        vix       = results["VIXCLS"][1]

        # CPI YoY: (현재값 - 13번째 전 값) / 13번째 전 값 * 100
        cpi_vals = results["CPIAUCSL"][0]
        cpi_yoy = None
        if len(cpi_vals) >= 13:
            cpi_yoy = round((cpi_vals[0] - cpi_vals[12]) / cpi_vals[12] * 100, 1)

        # VIX fallback to yfinance if FRED returned None
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
        logger.info(f"[Macro] 로드 완료 → {regime} (총 {time.perf_counter()-t_total:.1f}s)")

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
        cache.set(_CACHE_KEY, data, expire=_TTL)
    finally:
        _fetch_lock.release()


def _judge_regime(fed_funds, t10y2y, vix) -> str:
    if vix and vix > 30:
        return "고변동성 — 방어적 접근 권장"
    if t10y2y is not None and t10y2y < 0:
        return "장단기 역전 — 경기침체 우려"
    if fed_funds and fed_funds > 4.5:
        return "고금리 — 성장주 주의"
    return "안정"


# ── 사이드바 Markets · Live ────────────────────────────────────

def get_sidebar_macro() -> dict:
    """사이드바용 실시간 데이터 반환 (SPY/VIX delta + FearGreed). TTL 15분."""
    if _SIDEBAR_KEY in cache:
        val = cache.get(_SIDEBAR_KEY)
        if val:
            return val
    return _fetch_sidebar()


def refresh_sidebar() -> None:
    _fetch_sidebar()


def _fetch_sidebar() -> dict:
    if not _sidebar_lock.acquire(blocking=False):
        return cache.get(_SIDEBAR_KEY) or {}
    try:
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor as _TPE
        from screener.fear_greed_fetcher import get_fear_greed

        def _fetch_spy():
            hist = yf.Ticker("SPY").history(period="2d")
            closes = hist["Close"].dropna()
            price = round(float(closes.iloc[-1]), 2) if len(closes) >= 1 else None
            delta = None
            if len(closes) >= 2 and price is not None:
                delta = round((price - float(closes.iloc[-2])) / float(closes.iloc[-2]) * 100, 2)
            return price, delta

        def _fetch_vix():
            hist = yf.Ticker("^VIX").history(period="2d")
            closes = hist["Close"].dropna()
            val = round(float(closes.iloc[-1]), 2) if len(closes) >= 1 else None
            delta = None
            if len(closes) >= 2 and val is not None:
                delta = round(val - float(closes.iloc[-2]), 2)
            return val, delta

        with _TPE(max_workers=2) as ex:
            f_spy = ex.submit(_fetch_spy)
            f_vix = ex.submit(_fetch_vix)
            spy_price, spy_delta = f_spy.result()
            vix, vix_delta = f_vix.result()

        fg = get_fear_greed()

        data = {
            "spy":              spy_price,
            "spy_delta":        spy_delta,
            "vix":              vix,
            "vix_delta":        vix_delta,
            "fear_greed":       fg.get("score"),
            "fear_greed_label": fg.get("label"),
        }
        cache.set(_SIDEBAR_KEY, data, expire=_SIDEBAR_TTL)
        logger.info(
            f"[Sidebar] SPY={spy_price} ({spy_delta}%) "
            f"VIX={vix} ({vix_delta}) FG={fg.get('score')}"
        )
        return data
    except Exception as e:
        logger.warning(f"[Sidebar] 조회 실패: {e}")
        return {}
    finally:
        _sidebar_lock.release()
