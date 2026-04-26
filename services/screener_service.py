"""
CLI·웹 공용 스크리닝 서비스.
터미널 출력·argparse 의존성 없이 순수하게 데이터를 반환한다.
"""
import logging

from config import (
    SHOW_GRADES, MAX_RESULTS,
    TODAY_CHANGE_MIN, TODAY_CHANGE_MAX, NEWS_FILTER_ENABLED,
)
from screener.finviz_filter import get_filtered_tickers
from screener.data_fetcher import fetch_ohlcv, get_today_changes
from screener.indicators import calculate_indicators
from screener.checklist import score_ticker
from screener.grader import grade
from screener.news_filter import check_news_risk

logger = logging.getLogger(__name__)


def _make_skip(ticker: str, reason: str) -> dict:
    return {
        "ticker": ticker, "price": 0, "grade": "SKIP",
        "score": 0, "action": "진입 금지", "checklist": {},
        "target_1": None, "target_2": None, "stop_loss": None,
        "reason": reason,
    }


def run_analysis(
    tickers_override: list[str] | None = None,
    grade_filter: str | None = None,
) -> dict:
    """
    스크리닝 파이프라인 실행 후 결과 dict 반환.

    Returns:
        {
            "results":    list[dict],  # 전체 결과 (S→A→B→SKIP 정렬)
            "displayable": list[dict], # 등급 필터 + MAX_RESULTS 적용
            "summary": {
                "total": int,
                "skipped": int,
                "displayed": int,
            }
        }
    """
    # 1. 종목 수집
    if tickers_override:
        tickers = [t.upper() for t in tickers_override]
        logger.info(f"지정 종목 분석: {tickers}")
    else:
        logger.info("Finviz 필터링 시작")
        tickers = get_filtered_tickers()

    if not tickers:
        return _empty_result()

    # 2. OHLCV 수집
    ohlcv_map = fetch_ohlcv(tickers)
    if not ohlcv_map:
        return _empty_result()

    # 3. 당일 변동률 일괄 조회
    changes = get_today_changes(list(ohlcv_map.keys()))

    # 4~6. 지표 → 채점 → 등급
    results = []
    for ticker, df in ohlcv_map.items():
        today_change = changes.get(ticker, 0.0)
        if not (TODAY_CHANGE_MIN <= today_change <= TODAY_CHANGE_MAX):
            direction = "급등" if today_change > 0 else "급락"
            reason = f"당일변동 {today_change:+.1f}% ({direction} 제외)"
            logger.info(f"[SKIP] {ticker}: {reason}")
            results.append(_make_skip(ticker, reason))
            continue

        if NEWS_FILTER_ENABLED:
            is_risky, news_reason = check_news_risk(ticker)
            if is_risky:
                logger.info(f"[SKIP] {ticker}: {news_reason}")
                results.append(_make_skip(ticker, news_reason))
                continue

        ind = calculate_indicators(df)
        if ind is None:
            continue

        score_result = score_ticker(ind)
        result = grade(score_result, ticker, ind["price"])
        results.append(result)

    # 7. 정렬
    grade_order = {"S": 0, "A": 1, "B": 2, "SKIP": 3}
    results.sort(key=lambda r: (grade_order.get(r["grade"], 4), -r["score"]))

    # 8. 필터링
    show_grades = [grade_filter.upper()] if grade_filter else SHOW_GRADES
    displayable = [r for r in results if r["grade"] in show_grades][:MAX_RESULTS]

    skipped = sum(1 for r in results if r["grade"] == "SKIP")
    logger.info(f"완료: 총 {len(results)}개 | SKIP {skipped}개 | 표시 {len(displayable)}개")

    return {
        "results": results,
        "displayable": displayable,
        "summary": {
            "total": len(results),
            "skipped": skipped,
            "displayed": len(displayable),
        },
    }


def _empty_result() -> dict:
    return {
        "results": [],
        "displayable": [],
        "summary": {"total": 0, "skipped": 0, "displayed": 0},
    }
