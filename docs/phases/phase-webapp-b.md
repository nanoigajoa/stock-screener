# Phase Webapp-B — FastAPI + Celery 레이어 ✅ 완료 (2026-04-25)

**Goal:** HTTP API + 백그라운드 Job 처리

## Tasks

- [x] `tasks/celery_app.py`
  - Celery 인스턴스 + Redis broker/backend
  - `task_track_started=True`, `result_expires=3600`, `worker_prefetch_multiplier=1`

- [x] `tasks/screen_task.py`
  - `@celery_app.task screen_stocks(tickers, grade_filter)`
  - `self.update_state(state="STARTED")` 중간 상태 업데이트
  - `run_analysis()` 호출 → dict 반환

- [x] `api/routes/screen.py`
  - `POST /screen` → task_id 즉시 반환
  - `GET /results/{task_id}` → 상태/결과 조회
  - `GET /health` → Redis 연결 확인
  - `POST /htmx/screen` → HTMX HTML 조각 반환 (폴링 트리거 포함)
  - `GET /htmx/results/{task_id}` → 폴링 HTML 조각

- [x] `api/main.py`
  - FastAPI 앱 + Jinja2 템플릿 연결
  - `GET /` → screen.html 반환

- [x] `worker.py`
  - `celery -A worker worker` 진입점

## Definition of Done ✅
- [x] `POST /screen` → task_id 반환
- [x] `GET /results/{task_id}` → PENDING/STARTED/SUCCESS 상태 전환
- [x] `GET /health` → `{"redis": "connected"}`
- [x] 문법 오류 없음 (ast.parse 확인)
