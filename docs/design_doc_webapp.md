# Design Document — Web App (현재 상태 기준 2026-04-28)

> **Status:** 운영 중. 주요 Phase 완료.
> **상세 아키텍처:** [docs/architecture.md](architecture.md)
> **변경 이력:** [docs/changelog.md](changelog.md)
> **미구현 계획:** [docs/phases/phase-future.md](phases/phase-future.md)

---

## 완료된 Phase 요약

| Phase | 내용 | 상태 |
|-------|------|------|
| WebApp A | 서비스 레이어 분리 (`run_analysis()`) | ✅ 완료 |
| WebApp B | FastAPI + SSE 엔드포인트 | ✅ 완료 (Celery 대신 SSE 채택) |
| WebApp C | HTMX → SSE EventSource 프론트엔드 | ✅ 완료 |
| 커스터마이징 | 기간/RSI/체크리스트 on-off | ✅ 완료 |
| 펀더멘털 배지 | 실적일/숏비율/목표가/내부자매수 | ✅ 완료 |
| 프론트엔드 개편 | CSS/JS 분리, 네비게이션, About 페이지 | ✅ 완료 |
| 외부 데이터 4종 | Google Trends/FRED/의원거래/SEC Form 4 | ✅ 완료 |

---

## 현재 아키텍처 (요약)

```
브라우저 GET /stream/screen (SSE)
    ↓
FastAPI ThreadPoolExecutor
    ↓
run_analysis()
    ├─ Finviz → yfinance → 7개 체크리스트 → S/A/B/SKIP
    └─ extras 병렬 (x4):
         fundamental_fetcher / trends_fetcher
         congress_fetcher    / insider_fetcher
    ↓
SSE "done" 이벤트 → 브라우저에 결과 카드 렌더링
```

---

## 실행 방법

```bash
# 환경변수 (.env 파일 이미 생성됨)
# FRED_API_KEY=... 설정 완료

# 서버 실행
python -m uvicorn api.main:app --reload --port 8000

# 브라우저
open http://localhost:8000
```

---

## 다음 단계 (우선순위순)

1. **목표가·손절 커스터마이징** — 고급 설정에 슬라이더 추가
2. **VIX 데이터 복구** — yfinance fallback 추가
3. **백테스팅 엔진** — 과거 신호 승률 계산
4. **Render 배포** — Procfile 생성 + 환경변수 설정

---

## ADR 목록

| ID | 결정 |
|----|------|
| [ADR-009](adr/ADR-009-fastapi.md) | FastAPI 선택 |
| [ADR-010](adr/ADR-010-celery-redis.md) | 초기 Celery 계획 |
| [ADR-011](adr/ADR-011-htmx-jinja2.md) | HTMX + Jinja2 |
| [ADR-012](adr/ADR-012-no-docker.md) | Docker 미사용 |
| [ADR-013](adr/ADR-013-sse-over-celery.md) | Celery → SSE 전환 |
| [ADR-014](adr/ADR-014-ratio-grading.md) | 비율 기반 등급 |
| [ADR-015](adr/ADR-015-external-data-sources.md) | 외부 데이터소스 4종 |
| [ADR-016](adr/ADR-016-ttl-memory-cache.md) | TTL 메모리 캐시 패턴 |
