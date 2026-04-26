# Design Document — Web App 확장
## FastAPI + Celery + Redis + HTMX

> **Status:** Phase A 구현 시작 (2026-04-25)
> **전제:** CLI(`python main.py`)는 그대로 유지. 웹 레이어를 위에 얹는 방식.

---

## 문제 정의

CLI 스크리너를 웹앱으로 전환 시 핵심 병목:
- yfinance 동기 I/O → 티커 1개당 5~10초 소요
- 동기 HTTP 요청으로 서빙 시 UX 불가

**해결책:** 202 Accepted + 백그라운드 Job + 폴링 패턴

```
사용자 요청 → FastAPI가 즉시 task_id 반환 (202)
               ↓
          Celery 워커가 백그라운드에서 스크리닝 실행
               ↓
          Redis에 결과 저장
               ↓
          클라이언트 2초마다 폴링 → 완료 시 결과 표시
```

---

## 최종 아키텍처

```
[브라우저 HTMX]
      │ POST /screen (tickers, grade_filter)
      ▼
[FastAPI :8000]
      │ task = screen_stocks.delay(...)
      ▼
[Redis :6379] ← Celery broker + result backend
      │
      ▼
[Celery Worker]
      │ run_analysis() 호출
      ▼
[services/screener_service.py]  ← CLI·웹 공용 코어
      │
      ├─ screener/finviz_filter.py
      ├─ screener/data_fetcher.py
      ├─ screener/indicators.py
      ├─ screener/checklist.py
      ├─ screener/grader.py
      └─ screener/news_filter.py
```

---

## 디렉토리 구조 (추가분)

```
fin_auto/
├── services/
│   └── screener_service.py      # run_analysis() — CLI·웹 공용
├── tasks/
│   ├── celery_app.py            # Celery 인스턴스 + 설정
│   └── screen_task.py           # @task screen_stocks()
├── api/
│   ├── main.py                  # FastAPI 앱
│   └── routes/
│       └── screen.py            # POST /screen, GET /results/{id}
├── templates/
│   ├── base.html                # Jinja2 레이아웃
│   └── screen.html              # HTMX 메인 대시보드
└── worker.py                    # celery -A worker worker
```

---

## 로컬 환경 설정 (Docker 없음)

```bash
# Redis (최초 1회)
brew install redis
brew services start redis

# 추가 패키지
pip install fastapi uvicorn celery redis python-dotenv jinja2 python-multipart flower
```

---

## HTTP API 명세

### POST /screen
스크리닝 작업 제출. 즉시 task_id 반환.

**Request:**
```json
{ "tickers": ["AAPL", "MSFT"], "grade_filter": null }
```

**Response (202):**
```json
{ "task_id": "abc-123", "status": "submitted", "poll_url": "/results/abc-123" }
```

### GET /results/{task_id}
태스크 상태 및 결과 조회.

**Response (PENDING/STARTED):**
```json
{ "state": "STARTED", "stage": "스크리닝 중..." }
```

**Response (SUCCESS):**
```json
{
  "state": "SUCCESS",
  "result": {
    "results": [...],
    "summary": { "total": 5, "skipped": 2, "displayed": 3 }
  }
}
```

### GET /health
```json
{ "status": "ok", "redis": "connected" }
```

---

## 기존 파일 변경 내용

| 파일 | 변경 내용 | 이유 |
|------|----------|------|
| `config.py` | `REDIS_URL` 환경변수 추가 | Celery broker/backend |
| `data_fetcher.py` | `yf.download(threads=False)` | Celery 워커 내 pickle 충돌 방지 |
| `requirements.txt` | FastAPI, Celery, Redis 등 추가 | 웹 의존성 |
| `main.py` | `run_analysis()` 호출로 교체 | CLI → 공용 서비스 사용 |

CLI 인터페이스(argparse, 대화형 모드)는 100% 유지.

---

## 태스크 상태 흐름

```
PENDING (큐 대기)
  ↓
STARTED (워커가 실행 시작)
  ↓
SUCCESS → Redis에 result dict 저장 (TTL 1시간)
FAILURE → Redis에 에러 정보 저장
```

`task_track_started=True` 필수 (STARTED 상태 활성화).

---

## HTMX 폴링 패턴

```
POST /screen
  → FastAPI: task_id 포함 HTML 조각 반환
  → HTMX: 해당 조각을 DOM에 삽입

GET /results/{task_id} (2초마다 자동 폴링)
  → PENDING/STARTED: 로딩 표시 (hx-trigger 유지 → 폴링 계속)
  → SUCCESS: 결과 카드 HTML 반환 (hx-trigger 없음 → 폴링 중단)
  → FAILURE: 에러 메시지 반환 (폴링 중단)
```

---

## 실행 방법

### 권장 — start.sh (한 번에 실행)
```bash
cd /Users/parkjuan/Desktop/fin_auto
./start.sh
# → Redis + Celery + FastAPI 자동 시작
# → Ctrl+C 로 전체 종료
```

### Redis 최초 실행 (Homebrew 없는 환경)
```bash
# redis-server pip 패키지 사용
.venv/lib/python3.12/site-packages/redis_server/bin/redis-server --daemonize yes
```

### 수동 실행 (개발/디버깅용)
```bash
# 터미널 1 — FastAPI
uvicorn api.main:app --reload --port 8000

# 터미널 2 — Celery 워커
celery -A worker worker --loglevel=info

# (선택) 터미널 3 — Flower 모니터링
celery -A worker flower   # localhost:5555
```

### CLI는 그대로
```bash
python main.py --ticker AAPL MSFT
```

---

## 구현 Phase

### Phase A — 서비스 레이어 (현재)
- [x] 이 문서 작성
- [ ] `services/screener_service.py` — run_analysis() 추출
- [ ] `config.py` REDIS_URL 추가
- [ ] `data_fetcher.py` threads=False
- [ ] `main.py` run_analysis() 호출 교체
- [ ] `requirements.txt` 업데이트

### Phase B — FastAPI + Celery
- [ ] `tasks/celery_app.py`
- [ ] `tasks/screen_task.py`
- [ ] `api/main.py`
- [ ] `api/routes/screen.py`
- [ ] `worker.py`

### Phase C — HTMX 프론트엔드
- [ ] `templates/base.html`
- [ ] `templates/screen.html`
- [ ] 결과 카드 렌더링 (등급별 색상, 체크리스트)

---

## ADR

| ID | 결정 | 파일 |
|----|------|------|
| ADR-009 | FastAPI 선택 | [ADR-009-fastapi.md](adr/ADR-009-fastapi.md) |
| ADR-010 | Celery + Redis | [ADR-010-celery-redis.md](adr/ADR-010-celery-redis.md) |
| ADR-011 | HTMX + Jinja2 | [ADR-011-htmx-jinja2.md](adr/ADR-011-htmx-jinja2.md) |
| ADR-012 | Docker 미사용 | [ADR-012-no-docker.md](adr/ADR-012-no-docker.md) |

## Skills

| Skill | 파일 |
|-------|------|
| FastAPI + Celery Job Queue | [skill-fastapi-celery-jobqueue.md](skills/skill-fastapi-celery-jobqueue.md) |
| HTMX 폴링 패턴 | [skill-htmx-polling.md](skills/skill-htmx-polling.md) |

## Template

[fastapi-celery-webapp.md](templates/fastapi-celery-webapp.md)
