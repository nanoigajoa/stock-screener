# ADR-011: HTMX + Jinja2 (프론트엔드)

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
프론트엔드를 React 대신 HTMX + Jinja2 서버 렌더링으로 구현한다.

## Rationale
- HTMX 14KB vs React 47KB+ — 번들 크기 1/3
- 빌드 과정(npm, webpack) 없음 → 즉시 반영, 배포 단순
- `hx-trigger="every 2s"` 선언만으로 폴링 구현 — JavaScript 불필요
- 서버 렌더링으로 결과 카드를 Jinja2가 처리 → 데이터 모델 변경이 HTML에 즉시 반영
- 이 프로젝트 규모(개인/소팀 스크리너)에서 React의 복잡도는 과도함

## Consequences
- 복잡한 클라이언트 상태 관리 불가 (차트 라이브러리 등 필요 시 vanilla JS 또는 Alpine.js 추가)
- HTMX 폴링 중단: SUCCESS/FAILURE 응답에 `hx-trigger` 미포함 → 자동 중단
- 실시간 차트 필요 시 Phase 3에서 Chart.js 추가 고려
