import time
import yfinance as yf
from config import NEWS_LOOKBACK_HOURS

# 위험 키워드 — 희석/실적쇼크/법적리스크
_HIGH_RISK_KEYWORDS = [
    "public offering", "stock offering", "share offering",
    "secondary offering", "dilution", "공모", "유상증자",
    "guidance cut", "lowered guidance", "below expectations",
    "forecast cut", "warns", "warning", "profit warning",
    "가이던스 하향", "실적 쇼크", "earnings miss",
]

_MEDIUM_RISK_KEYWORDS = [
    "insider selling", "class action", "investigation",
    "sec filing", "lawsuit", "내부자 매도",
]


def check_news_risk(ticker: str) -> tuple[bool, str]:
    """
    최근 NEWS_LOOKBACK_HOURS 이내 뉴스에서 위험 키워드 감지.
    Returns: (is_risky, reason)
    """
    try:
        news = yf.Ticker(ticker).news
    except Exception:
        return False, ""  # 뉴스 조회 실패는 통과 처리

    if not news:
        return False, ""

    cutoff = time.time() - (NEWS_LOOKBACK_HOURS * 3600)  # 48시간 기준 타임스탬프

    for article in news[:10]:  # 최근 10개만 검사
        pub_time = article.get("providerPublishTime", 0)
        if pub_time < cutoff:
            continue  # 기준 시간 이전 뉴스 무시

        title = article.get("title", "").lower()
        snippet = article.get("summary", "").lower()
        text = f"{title} {snippet}"

        for keyword in _HIGH_RISK_KEYWORDS:
            if keyword.lower() in text:
                short_title = article.get("title", "")[:60]
                return True, f"뉴스위험: '{keyword}' — {short_title}"

    return False, ""
