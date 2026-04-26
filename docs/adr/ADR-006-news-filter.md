# ADR-006: 뉴스 위험 키워드 필터

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
`screener/news_filter.py`를 신규 추가한다. 48시간 이내 뉴스 제목/요약에서 고위험 키워드를 감지하면 SKIP 처리한다.

고위험 키워드: 공모/유상증자/희석, 가이던스 하향, 실적 쇼크, profit warning 등

## Rationale
기술적 지표는 펀더멘털 이벤트(주식 공모, 실적 쇼크)를 포착하지 못한다. S급 종목이 해당 이벤트로 장중 급락하는 케이스를 사전 차단하기 위해 추가됨.

## Consequences
- `yfinance` news API 의존 — API 변경 시 `check_news_risk()` 수정 필요
- 뉴스 조회 실패 시 `(False, "")` 반환으로 통과 처리 (false negative 허용)
- `NEWS_FILTER_ENABLED = False`로 비활성화 가능
- 키워드 목록은 `news_filter.py`의 `_HIGH_RISK_KEYWORDS`에서 관리
