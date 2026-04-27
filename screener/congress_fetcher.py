"""
미국 의회 의원 주식 거래 공시 데이터.
- 로컬 파일 기반: data/congress_trades.json (한 번 다운받아 저장)
- 파일 없으면 여러 소스 자동 시도 → 성공 시 파일 저장
- TTL 24h 메모리 캐시 (파일은 영구 보존)
- 데이터 갱신: python scripts/download_congress_data.py
"""
import json
import logging
import time
from datetime import datetime, date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_all_trades: list[dict] = []
_fetched_at: datetime | None = None
_TTL = 86400  # 24h

_DATA_FILE = Path(__file__).parent.parent / "data" / "congress_trades.json"

# 시도할 소스 순서 (앞에서부터 성공하면 멈춤)
_SOURCES = [
    ("House Stock Watcher S3",  "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"),
    ("Senate Stock Watcher S3", "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"),
]


def _is_fresh() -> bool:
    if _fetched_at is None:
        return False
    return (datetime.now() - _fetched_at).total_seconds() < _TTL


def refresh_congress() -> None:
    _load()


def get_congress_trades(ticker: str, days: int = 90) -> list[dict]:
    """특정 티커의 최근 N일 의원 매수 내역 반환."""
    if not _is_fresh():
        _load()

    if not _all_trades:
        return []

    cutoff = date.today() - timedelta(days=days)
    result = []
    for trade in _all_trades:
        if trade.get("ticker", "").upper() != ticker.upper():
            continue
        tx_type = trade.get("type", "").lower()
        if "purchase" not in tx_type and "buy" not in tx_type:
            continue
        try:
            raw_date = trade.get("transaction_date") or trade.get("disclosure_date", "")
            trade_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
            if trade_date >= cutoff:
                result.append(trade)
        except (ValueError, KeyError):
            continue
    return result


def _load() -> None:
    """파일 → 네트워크 순서로 데이터 로드."""
    global _all_trades, _fetched_at

    # 1. 로컬 파일 우선
    if _DATA_FILE.exists():
        try:
            data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                _all_trades = data
                _fetched_at = datetime.now()
                age_days = (datetime.now().timestamp() - _DATA_FILE.stat().st_mtime) / 86400
                logger.info(f"[Congress] 파일 로드: {len(_all_trades)}건 (파일 나이 {age_days:.0f}일)")
                return
        except Exception as e:
            logger.warning(f"[Congress] 파일 로드 실패: {e}")

    # 2. 파일 없으면 네트워크 시도
    _fetch_from_network()


def _fetch_from_network() -> None:
    global _all_trades, _fetched_at
    import requests

    trades = []
    for name, url in _SOURCES:
        t0 = time.perf_counter()
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "StockScope/1.0"})
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                trades.extend(data)
                logger.info(f"[Congress]   {name}: {len(data)}건 ({time.perf_counter()-t0:.1f}s)")
        except Exception as e:
            logger.warning(f"[Congress]   {name}: 실패 ({time.perf_counter()-t0:.1f}s) — {e}")

    if trades:
        _all_trades = trades
        _fetched_at = datetime.now()
        # 파일로 저장
        try:
            _DATA_FILE.parent.mkdir(exist_ok=True)
            _DATA_FILE.write_text(json.dumps(trades, ensure_ascii=False), encoding="utf-8")
            logger.info(f"[Congress] 총 {len(_all_trades)}건 저장 완료 → {_DATA_FILE}")
        except Exception as e:
            logger.warning(f"[Congress] 파일 저장 실패: {e}")
    else:
        logger.warning("[Congress] 모든 소스 실패. 의원거래 배지 비활성화됨.")
        logger.warning("[Congress] 수동 갱신: python scripts/download_congress_data.py")
