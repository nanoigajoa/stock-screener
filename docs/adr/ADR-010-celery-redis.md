# ADR-010: Celery + Redis (Job Queue 패턴)

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
장기 실행 스크리닝(5~10초)을 Celery 백그라운드 태스크로 처리하고, Redis를 broker 겸 result backend로 사용한다. HTTP 응답은 task_id를 즉시 반환(202 Accepted), 클라이언트가 폴링으로 결과를 수령한다.

## Rationale
- yfinance 동기 I/O(5~10초)를 HTTP 요청 안에서 블로킹하면 UX 불가 및 nginx timeout 위험
- WebSocket은 5~10초 작업에 과도한 복잡도
- Redis: broker + result backend 이중 역할 → 별도 DB 불필요
- `result_expires=3600`: 결과 1시간 자동 삭제로 Redis 메모리 관리

## Consequences
- `brew install redis && brew services start redis` (Docker 없음)
- 터미널 2개 필요: uvicorn + celery worker
- `task_track_started=True` 필수 (STARTED 상태 활성화)
- `worker_prefetch_multiplier=1`: yfinance 동시 호출 충돌 방지
- 태스크 반환값은 JSON dict만 (DataFrame 금지 — pickle 버전 의존성)
