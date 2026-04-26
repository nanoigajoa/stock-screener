# Phase Webapp-A — 서비스 레이어 분리 ✅ 완료 (2026-04-25)

**Goal:** CLI·웹 공용 `run_analysis()` 추출 — CLI 동작 유지

## Tasks

- [x] `services/screener_service.py` 신규 생성
  - `main.py`의 파이프라인 로직 추출
  - 터미널 출력·argparse 의존성 제거
  - `run_analysis(tickers, grade_filter) -> dict` 반환

- [x] `main.py` 수정
  - `run()` → `run_analysis()` 호출로 교체
  - 터미널 출력은 `terminal.py` 통해 유지
  - CLI 인터페이스(argparse, 대화형 모드) 100% 유지

- [x] `config.py` 수정
  - `REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")` 추가

- [x] `data_fetcher.py` 수정
  - `yf.download(threads=False)` — Celery pickle 충돌 방지

- [x] `requirements.txt` 업데이트
  - fastapi, uvicorn, celery, redis, jinja2, python-multipart, flower 추가

## Definition of Done ✅
- [x] `python main.py --ticker AAPL` CLI 동작 확인
- [x] `services/screener_service.py` 문법 오류 없음
- [x] `run_analysis()` dict 반환 (terminal.py 호출 없음)
