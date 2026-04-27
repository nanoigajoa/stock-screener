"""
SEC EDGAR Form 4 내부자 거래 조회 (sec-edgar-downloader).
- yfinance insider_purchases 대체 (더 신뢰도 높음)
- Lazy per-ticker, TTL 24h 메모리 캐시
- API 키 불필요 (SEC 공개 데이터)
"""
import logging
import os
import re
import tempfile
from datetime import datetime, date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[bool, datetime]] = {}
_TTL = 86400  # 24h


def _is_fresh(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    _, fetched_at = _cache[ticker]
    return (datetime.now() - fetched_at).total_seconds() < _TTL


def get_insider_buys(ticker: str, days: int = 90) -> bool:
    """최근 N일 내 내부자 매수 여부 반환."""
    if _is_fresh(ticker):
        return _cache[ticker][0]

    result = _fetch_form4(ticker, days)
    _cache[ticker] = (result, datetime.now())
    return result


def _fetch_form4(ticker: str, days: int) -> bool:
    try:
        from sec_edgar_downloader import Downloader
    except ImportError:
        logger.warning("[Insider] sec-edgar-downloader 미설치 — 스킵")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            dl = Downloader("StockScope", "noreply@stockscope.app", tmpdir)
            dl.get("4", ticker, limit=10, download_details=True)

            cutoff = date.today() - timedelta(days=days)
            form4_dir = Path(tmpdir) / "sec-edgar-filings" / ticker / "4"

            if not form4_dir.exists():
                _cache[ticker] = (False, datetime.now())
                return False

            for filing_dir in sorted(form4_dir.iterdir(), reverse=True):
                for xml_file in filing_dir.glob("*.xml"):
                    try:
                        content = xml_file.read_text(encoding="utf-8", errors="ignore")
                        # 거래 유형 확인 (P = Purchase)
                        if "<transactionCode>P</transactionCode>" not in content:
                            continue
                        # 날짜 파싱
                        date_match = re.search(
                            r"<transactionDate>.*?<value>([\d-]+)</value>",
                            content, re.DOTALL
                        )
                        if date_match:
                            trade_date = datetime.strptime(
                                date_match.group(1), "%Y-%m-%d"
                            ).date()
                            if trade_date >= cutoff:
                                logger.info(f"[Insider] {ticker}: 매수 발견 ({trade_date})")
                                return True
                    except Exception:
                        continue
            return False

        except Exception as e:
            logger.warning(f"[Insider] {ticker} Form 4 조회 실패: {e}")
            return False
