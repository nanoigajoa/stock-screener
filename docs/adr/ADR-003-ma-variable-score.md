# ADR-003: MA 정배열 가변 점수 (0/1/2)

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
MA 정배열 항목을 이진(pass/fail) 대신 가변 점수로 채점한다.
- 완전 정배열 (price > MA5 > MA20 > MA60 > MA120): **2점**
- 단기 정배열만 (price > MA5 > MA20): **1점**
- 미충족: **0점**

## Rationale
Finviz 필터가 200MA 위를 보장하지만, 60MA/120MA 배열은 보장하지 않는다. 완전 정배열과 단기 정배열을 동일하게 처리하면 질적 차이를 등급에 반영할 수 없다. 부분 점수로 등급 차등화가 가능해진다.

## Consequences
- checklist 항목에 `score` 필드 추가 (기존 `pass` boolean과 병존)
- total_score 계산이 `weight if pass` → `sum(score)` 방식으로 변경됨
- 최대 점수: 9점 (MA 2 + RSI 2 + 거래량 1 + MACD 1 + 지지 1 + BB 1 + 추세 1)
