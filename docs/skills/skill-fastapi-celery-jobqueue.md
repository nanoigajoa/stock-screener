## Skill: FastAPI + Celery Job Queue (202 Accepted 패턴)

- **Purpose:** 5~10초 이상 소요되는 작업을 HTTP 요청 내에서 블로킹하지 않고 백그라운드로 처리한다.
- **Inputs:** HTTP POST 요청 파라미터
- **Outputs:** task_id (즉시 반환) → 클라이언트가 폴링으로 결과 수령
- **Files:** `tasks/celery_app.py`, `tasks/screen_task.py`, `api/routes/screen.py`

### 패턴 흐름
```
POST /screen → task_id 즉시 반환 (202 Accepted)
GET  /results/{task_id} → PENDING | STARTED | SUCCESS | FAILURE
```

### Celery 핵심 설정
```python
celery_app.conf.update(
    task_track_started=True,       # STARTED 상태 활성화 (기본값: PENDING만)
    result_expires=3600,           # Redis 결과 TTL 1시간
    worker_prefetch_multiplier=1,  # 워커 1개당 태스크 1개 (yfinance 안정성)
    task_serializer="json",        # DataFrame 직렬화 금지 → 결과는 dict로만
)
```

### Best Practices
- 태스크 반환값은 반드시 JSON-serializable dict (`float`, `int`, `str`, `bool`, `None`)
- DataFrame은 태스크 반환값으로 사용 금지 → pickle 버전 의존성 발생
- `bind=True` + `self.update_state()` 로 진행 상태 중간 업데이트 가능
- `worker_prefetch_multiplier=1`: yfinance 동시 호출 충돌 방지

### Anti-patterns
- 태스크 결과로 `pd.DataFrame` 직접 반환 → pandas 버전 mismatch 시 pickle 오류
- `threads=True`로 yfinance download → Celery 워커 내 RLock 충돌
- 태스크 내에서 `print()` → Celery 로그와 혼합, 구조화 안 됨

### Example
```python
# 제출
task = screen_stocks.delay(tickers, grade_filter)
return {"task_id": task.id}

# 결과 조회
result = AsyncResult(task_id, app=celery_app)
if result.state == "SUCCESS":
    data = result.result  # dict
```

### 실행
```bash
celery -A worker worker --loglevel=info
celery -A worker flower   # 모니터링 localhost:5555
```
