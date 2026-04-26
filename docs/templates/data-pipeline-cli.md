# Template: Data Pipeline CLI

## Directory Structure
```
project/
├── main.py              # CLI entry point, pipeline orchestration
├── config.py            # All config values centralized
├── pipeline/            # Core processing stages (one file per stage)
├── notifier/            # Output channels (terminal, messaging)
├── utils/               # logger, helpers
└── output/              # Generated artifacts
```

## Layer Responsibilities
- `config.py` — 모든 상수/설정값, 코드에 하드코딩 금지
- `pipeline/` — 각 stage는 단일 책임, 이전 stage 출력을 입력으로 받음
- `notifier/` — side-effect only (출력/발송), 비즈니스 로직 없음
- `utils/` — 재사용 유틸 (로깅, 파일 IO 등)

## Coding Conventions
- 각 pipeline stage는 순수 함수로 작성 (입력 → 출력, 상태 변경 없음)
- 예외처리는 stage 경계에서만 (네트워크, 파일 IO)
- config.py 값은 import해서 사용, 함수 파라미터로 전달하지 않음
- 시크릿은 환경변수 또는 `.env` 파일

## Branch Strategy
`feature/*` → `dev` → `main`

## Required Skills
- skill-finviz-scraper
- skill-yfinance-fetch
- skill-technical-indicators
- skill-checklist-scorer
- skill-grader

## Agent Map
| Layer | Agent |
|-------|-------|
| config.py, docs/ | Architect |
| pipeline/ | Engineer |
| notifier/, utils/ | Engineer |
| tests/ | QA |
