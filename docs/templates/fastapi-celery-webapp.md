# Template: FastAPI + Celery Web App

## Directory Structure
```
project/
├── api/
│   ├── main.py          # FastAPI 앱 팩토리, Jinja2 연결
│   └── routes/
│       └── screen.py    # REST + HTMX 엔드포인트
├── tasks/
│   ├── celery_app.py    # Celery 인스턴스 + Redis 설정
│   └── screen_task.py   # @task 함수
├── services/
│   └── screener_service.py  # CLI·웹 공용 비즈니스 로직
├── templates/
│   ├── base.html        # Jinja2 레이아웃 (HTMX CDN 포함)
│   └── screen.html      # 메인 페이지
└── worker.py            # celery -A worker worker 진입점
```

## Layer Responsibilities
- `api/` — HTTP 요청 수신, task 제출, HTMX HTML 조각 반환
- `tasks/` — Celery 태스크 정의, 비동기 실행
- `services/` — 핵심 비즈니스 로직 (CLI·웹 공유, 순수 함수)
- `templates/` — Jinja2 서버 렌더링 + HTMX 폴링

## 202 Accepted + 폴링 패턴
```
POST /screen             → task_id 즉시 반환
GET  /results/{task_id}  → PENDING | STARTED | SUCCESS | FAILURE
HTMX: hx-trigger="every 2s" → SUCCESS 시 hx-trigger 제거 → 폴링 중단
```

## Celery 필수 설정
```python
task_track_started=True       # STARTED 상태 활성화
result_expires=3600            # Redis 결과 TTL
worker_prefetch_multiplier=1   # 태스크 1개씩 처리
task_serializer="json"         # DataFrame 반환 금지
```

## Coding Conventions
- 태스크 반환값: JSON-serializable dict only (DataFrame 금지)
- `services/`는 import하는 쪽(CLI/웹)을 모름 — print 없음, argparse 없음
- HTMX 엔드포인트는 HTML 조각 반환 (전체 페이지 아님)
- REST 엔드포인트는 JSON 반환

## Branch Strategy
`feature/*` → `dev` → `main`

## Required Skills
- skill-fastapi-celery-jobqueue
- skill-htmx-polling

## Agent Map
| Layer | Agent |
|-------|-------|
| tasks/, services/ | Engineer |
| api/routes/ | Engineer |
| templates/ | Engineer |
| config.py, docs/ | Architect |

## 로컬 실행
```bash
brew services start redis
uvicorn api.main:app --reload --port 8000
celery -A worker worker --loglevel=info
```
