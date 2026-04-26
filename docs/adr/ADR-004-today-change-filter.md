# ADR-004: 당일 등락률 사전 필터

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
OHLCV 수집 후, 지표 계산 전에 당일 등락률을 체크한다.
- `TODAY_CHANGE_MIN = -5.0` (이상 하락 → SKIP)
- `TODAY_CHANGE_MAX = 15.0` (이상 급등 → SKIP)

## Rationale
yfinance OHLCV는 전일 종가 기반이다. 당일 -8% 하락 중인 종목이 전일 데이터 기준으로는 모든 체크리스트를 통과할 수 있다. 급등 종목은 추격매수 위험이 있다.

## Consequences
- `yf.Ticker(ticker).fast_info` 개별 조회 필요 → 병렬화 필수 (ADR-005)
- 장외/주말 실행 시 `lastPrice`가 없어 0.0 반환 → 필터 통과 처리 (보수적 기본값)
- 임계값은 `config.py`의 `TODAY_CHANGE_MIN`, `TODAY_CHANGE_MAX`로 조정
