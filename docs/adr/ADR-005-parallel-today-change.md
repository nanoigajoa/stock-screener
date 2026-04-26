# ADR-005: get_today_changes 병렬화 + timeout

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
당일 등락률 조회를 `concurrent.futures.ThreadPoolExecutor(max_workers=6)`로 병렬 처리하고, 개별 조회에 6초 timeout을 적용한다.

## Rationale
`yf.Ticker(ticker).fast_info` 순차 호출 시 특정 티커에서 네트워크 응답이 없으면 프로세스 전체가 hang된다. 실제로 `python main.py` 실행 시 아무것도 출력되지 않는 버그로 확인됨.

## Consequences
- 티커 수에 관계없이 최대 6개 동시 요청 → 전체 조회 시간 단축
- 6초 내 응답 없는 티커는 0.0 반환 (필터 통과) — 정확도보다 가용성 우선
- 루프 내 개별 호출 대신 루프 전 일괄 처리로 구조 변경
