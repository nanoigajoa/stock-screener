# ADR-002: RSI 하드게이트 80

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
RSI ≥ 80인 종목은 나머지 채점 없이 즉시 SKIP 처리한다.

## Rationale
과매수 구간 진입은 단기 되돌림 위험이 크다. 체크리스트 점수가 높더라도 RSI 80 이상이면 진입 근거가 없으므로, 채점 비용을 줄이는 동시에 오신호를 차단한다.

## Consequences
- RSI 80 이상이면 MACD, BB 등 다른 지표 계산을 건너뜀 (성능 이점)
- 임계값 조정은 `config.py`의 `RSI_HARD_GATE`만 수정하면 됨
