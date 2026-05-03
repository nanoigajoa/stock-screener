"""
스크리너(기초 체력) + 시그널(매매 타이밍) 통합 서비스.
단일 API 요청으로 종목의 전체적인 맥락을 분석하고 자연어 브리핑을 제공한다.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from config import (
    SHOW_GRADES, MAX_RESULTS,
    TODAY_CHANGE_MIN, TODAY_CHANGE_MAX, NEWS_FILTER_ENABLED,
    DATA_PERIOD, RSI_IDEAL_MIN, RSI_IDEAL_MAX,
)
from screener.finviz_filter import get_filtered_tickers
from screener.data_fetcher import fetch_ohlcv, fetch_intraday, get_today_changes
from screener.indicators import calculate_indicators
from screener.checklist import score_ticker
from screener.grader import grade
from screener.signal_scorer import score_signals
from screener.nl_generator import generate_summary
from screener.news_filter import check_news_risk
from screener.fundamental_fetcher import fetch_fundamentals
from screener.trends_fetcher import get_trend_scores
from screener.insider_fetcher import get_insider_buys

logger = logging.getLogger(__name__)

def run_explore_analysis(
    tickers_override: list[str] | None = None,
    grade_filter: str | None = None,
    period: str = DATA_PERIOD,
) -> dict:
    """
    통합 분석 파이프라인.
    """
    # 1. 대상 종목 결정
    if tickers_override:
        tickers = [t.upper() for t in tickers_override]
    else:
        # 유저가 검색하지 않았을 때: 오늘의 핫 종목 탐색
        tickers = get_filtered_tickers()
    
    if not tickers:
        return {"results": [], "summary": {"total": 0}}

    # 2. 데이터 일괄 수집
    ohlcv_map = fetch_ohlcv(tickers, period=period)
    if not ohlcv_map:
        return {"results": [], "summary": {"total": 0}}
    
    actual_tickers = list(ohlcv_map.keys())
    changes = get_today_changes(actual_tickers)
    
    # 펀더멘털 데이터 (로고 및 회사명용)
    fund_map = fetch_fundamentals(actual_tickers)

    results = []
    
    def _analyze_one(ticker: str) -> dict | None:
        try:
            df_daily = ohlcv_map.get(ticker)
            if df_daily is None or df_daily.empty:
                return None
            
            # (1) 기초 체력 분석 (Screener)
            ind = calculate_indicators(df_daily)
            if not ind:
                return None
            
            score_res = score_ticker(ind)
            found_res = grade(score_res, ticker, ind["price"])
            
            # (2) 매매 타이밍 분석 (Signal)
            # 60일치 분봉 데이터 (시그널용) - 성능을 위해 여기서 fetch
            df_hourly = fetch_intraday(ticker, "1h", "60d")
            time_res = score_signals(df_daily, df_hourly)
            
            # (3) 회사 정보 및 도메인
            fund = fund_map.get(ticker, {})
            website = fund.get("website", "")
            domain = ""
            if website:
                domain = website.replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0]
            
            # (4) 자연어 브리핑 생성
            # foundation에 rsi_val 추가 (nl_generator용)
            found_res["rsi_val"] = ind.get("rsi")
            nl_summary = generate_summary(found_res, time_res)
            
            return {
                "ticker": ticker,
                "price": ind["price"],
                "short_name": fund.get("short_name", ticker),
                "website_domain": domain,
                "foundation": {
                    "grade": found_res["grade"],
                    "score": found_res["score"],
                    "max_score": found_res["max_score"],
                    "checklist": found_res["checklist"],
                },
                "timing": {
                    "signal_grade": time_res["signal_grade"],
                    "signal_score": time_res["signal_score"],
                    "breakdown": time_res["signal_breakdown"],
                    "detected_patterns": time_res.get("detected_patterns", []),
                    "entry_low": time_res["entry_low"],
                    "entry_high": time_res["entry_high"],
                },
                "nl_summary": nl_summary,
                # 정렬용 헬퍼 점수 (체력 + 타이밍)
                "total_score": found_res["score"] + (time_res["signal_score"] * 10)
            }
        except Exception as e:
            logger.error(f"[Explore] {ticker} 분석 실패: {e}")
            return None

    # 병렬 분석 실행
    with ThreadPoolExecutor(max_workers=5) as ex:
        raw_results = list(ex.map(_analyze_one, actual_tickers))
    
    results = [r for r in raw_results if r is not None]
    
    # 정렬: 매수 매력도 순 (Timing 점수가 높은 것이 상단)
    # 1순위: 시그널 등급 (STRONG BUY -> BUY -> WATCH -> NO SIGNAL)
    # 2순위: 통합 점수
    grade_order = {"STRONG BUY": 0, "BUY": 1, "WATCH": 2, "NO SIGNAL": 3}
    results.sort(key=lambda x: (
        grade_order.get(x["timing"]["signal_grade"], 4),
        -x["total_score"]
    ))

    return {
        "results": results[:MAX_RESULTS],
        "summary": {
            "total": len(actual_tickers),
            "analyzed": len(results),
            "displayed": len(results[:MAX_RESULTS])
        }
    }
