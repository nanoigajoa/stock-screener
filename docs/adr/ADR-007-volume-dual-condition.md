# ADR-007: 거래량 이중 조건 (절대량 + 상대량)

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
거래량 체크리스트를 상대량 단독에서 절대량 + 상대량 이중 조건으로 변경한다.
- 절대량: `volume ≥ MIN_VOLUME_ABSOLUTE (2,000,000)`
- 상대량: `volume ≥ vol_ma20 × MIN_RELATIVE_VOLUME (1.5)`
- 둘 다 충족해야 ✅ 1점

## Rationale
Finviz의 `sh_relvol` 필터는 상대 거래량만 보장한다. 평균 거래량 50만인 종목이 1.5배 = 75만으로 통과되지만, 이는 진입/청산이 어려운 얇은 유동성이다.

## Consequences
- `config.py`에 `MIN_VOLUME_ABSOLUTE`, `MIN_RELATIVE_VOLUME` 추가
- 상대량은 OK지만 절대량 부족한 경우 ⚠️ 표시, 점수 0
