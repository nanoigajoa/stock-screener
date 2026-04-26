# ADR-009: FastAPI 선택

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
웹 프레임워크로 FastAPI를 사용한다.

## Rationale
- async 기본 지원 → Celery 태스크 제출이 이벤트 루프를 블로킹하지 않음
- OpenAPI 문서 자동 생성 (`/docs`)
- Pydantic 통합 — 요청/응답 타입 검증
- Jinja2 템플릿 지원 (HTMX 서버 렌더링 compatible)

## Consequences
- `uvicorn api.main:app --reload`로 실행
- 기존 CLI(`main.py`)와 완전 독립 — 같은 `services/screener_service.py`를 공유
