# ADR-012: Docker 미사용

**Status:** Accepted  
**Date:** 2026-04-25

## Decision
Docker/docker-compose를 사용하지 않는다. Redis는 Homebrew로 로컬 설치한다.

## Rationale
- 개발 환경 오버헤드 최소화 요구 ("앱이 너무 무거워")
- macOS에서 `brew install redis && brew services start redis`로 충분
- FastAPI, Celery는 이미 venv에서 직접 실행 가능
- 현재 단계에서 컨테이너 격리의 이점보다 운영 단순성이 더 중요

## Consequences
- Redis는 Homebrew 서비스로 시스템 상시 실행 (`brew services list`로 확인)
- 배포 시 Docker 도입 재검토 가능 (이 ADR은 개발 환경 한정)
- 팀 협업 시 README에 Homebrew Redis 설치 가이드 필수
