# ADR-013: Celery + Redis → FastAPI SSE로 전환

**날짜:** 2026-04-25
**상태:** 결정됨

---

## 배경

초기 웹앱 설계(ADR-010)에서 Celery + Redis 패턴을 선택했으나,
로컬 개발 환경에서 Redis 프로세스 별도 관리 필요성이 부담이 됨.

## 결정

Celery + Redis를 제거하고 **FastAPI SSE(Server-Sent Events)** 방식으로 전환.

```
AS-IS: POST /screen → task_id → 클라이언트 2초 폴링 → GET /results/{id}
TO-BE: GET /stream/screen → EventSource 연결 → progress/done 이벤트 수신
```

## 이유

1. **Redis 불필요** — 별도 프로세스 없이 단일 uvicorn 서버만으로 동작
2. **실시간 진행 표시** — progress 이벤트로 "분석 중..." 메시지 즉시 전달
3. **Render 무료 티어 호환** — Redis 없이 배포 가능
4. **코드 단순화** — tasks/, worker.py 삭제. celery_app.py 불필요

## 트레이드오프

| 항목 | Celery | SSE |
|------|--------|-----|
| 연결 끊김 시 작업 | 워커가 계속 실행 | 취소됨 |
| 동시 요청 처리 | 워커 수만큼 | 스레드풀 기준 |
| 모니터링 | Flower 대시보드 | 로그만 |
| 인프라 복잡도 | Redis + Worker 필요 | uvicorn 1개 |

스크리너 특성상 연결 끊김 시 재시도가 자연스러워 트레이드오프 수용.
