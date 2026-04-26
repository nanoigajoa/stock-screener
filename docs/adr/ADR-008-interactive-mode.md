# ADR-008: 대화형 입력 모드

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
CLI 인수 없이 `python main.py` 실행 시 대화형 메뉴를 제공한다.
- [1] 전체 Finviz 스캔
- [2] 티커 직접 입력
- 등급 필터, CSV 저장 여부 추가 질문
- 분석 후 재실행 여부 확인

## Rationale
`--ticker`, `--grade` 등 CLI 인수를 매번 타이핑하는 것은 비개발자에게 진입 장벽이다. 터미널에 익숙하지 않은 사용자도 `python main.py` 한 줄로 전체 기능을 사용할 수 있게 한다.

## Consequences
- CLI 인수가 하나라도 있으면 대화형 스킵 → 기존 자동화/스케줄 호환성 유지
- `--schedule`은 항상 대화형 스킵 (비대화형 환경에서 실행되므로)
