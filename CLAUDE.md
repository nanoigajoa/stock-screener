# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## AI Engineering Workflow

**Never generate code before a Design Document exists.**

### Session Start Checklist
```
[ ] CASE identified (Existing / New)
[ ] Template selected or extracted
[ ] Design Document (docs/design_doc.md) exists and loaded
[ ] Current phase identified
[ ] Required skills for this phase loaded
[ ] Agent assignments confirmed
```

If any item is unchecked → complete it before writing code.

### Workflow (New Project)
1. Define Problem → 2. Define Templates → 3. Define Skills → 4. Define Agents → 5. Create Design Document → 6. Phase Planning → 7. Implementation

### Workflow (Existing Project)
1. Analyze codebase → extract Architecture Template → 2. Extract reusable Skills → 3. Identify Agents per layer → 4. Generate Design Document → 5. Phase Planning

### Phase Execution Rules
- Run phases in planning mode first
- Complete DoD before starting next phase
- One phase per session when possible
- File PR summary at phase end: What changed / Why / Risk / Next phase dependency

### File Loading Strategy (Token Efficiency)
```
Session startup:
1. Load: docs/design_doc.md (current state)
2. Load: current phase task list only
3. Load: required skills for this phase only
4. Do not reload completed phases
```

### Anti-patterns
- Writing research inline in chat
- Redefining architecture per session
- Generating code to "explore" — use planning mode
- Skipping DoD to move faster
- Repeating skill/template content inline — reference by name

---

## Project: StockScope — 미국 주식 스크리닝 + 매매시그널 시스템

두 개의 독립 서비스로 구성된 FastAPI 웹 애플리케이션.

**Status:** 운영 중 (2026-05-01) — Phase 0~6 완료

### 두 서비스 요약

| 서비스 | URL | 핵심 질문 |
|--------|-----|---------|
| 스크리닝 | `/screen` | 이 종목이 기술적으로 건강한가? |
| 매매시그널 | `/signals` | 지금 진입 타이밍인가? |

### Tech Stack
- **Backend:** FastAPI + Jinja2 + SSE, Python 3.12
- **Data:** yfinance, finviz, pytrends, FRED REST API, quiverquant
- **Frontend:** Vanilla JS, TomSelect, Lightweight Charts 4.2
- **Concurrency:** `concurrent.futures.ThreadPoolExecutor`

### Commands
```bash
pip install -r requirements.txt

# 서버 실행 (권장)
./run.sh

# 직접 실행
~/fin_auto_venv/bin/python -m uvicorn api.main:app --reload --port 8000 \
  --reload-dir api --reload-dir screener --reload-dir services
```

### Directory Structure
```
fin_auto/
├── api/
│   ├── main.py                 # FastAPI 앱 + 라우터 등록 + 배치 스케줄러
│   └── routes/
│       ├── screen.py           # /stream/screen SSE + 카드 HTML 렌더링
│       ├── signals.py          # /signals 페이지 + /stream/signals SSE
│       ├── watchlist.py        # /api/watchlist CRUD
│       ├── chart.py            # /api/chart-data/{ticker}
│       └── tickers.py          # /api/tickers 자동완성
├── services/
│   ├── screener_service.py     # run_analysis() — 스크리닝 오케스트레이터
│   └── signal_service.py       # run_signal_analysis() — 시그널 오케스트레이터
├── screener/
│   ├── finviz_filter.py        # Finviz 필터 → 티커 리스트
│   ├── data_fetcher.py         # OHLCV 배치 수집 + 분봉 수집, TTL 캐시
│   ├── indicators.py           # MA/RSI/MACD/BB + ATR/StochRSI/OBV/거래대금
│   ├── checklist.py            # 7개 항목 채점, RSI 하드게이트
│   ├── grader.py               # 비율 기반 S/A/B/SKIP 등급
│   ├── signal_scorer.py        # 4카테고리 가중 시그널 채점
│   ├── watchlist_store.py      # Watchlist JSON CRUD (threading.Lock)
│   ├── fundamental_fetcher.py  # 실적일/숏비율/목표가
│   ├── trends_fetcher.py       # Google Trends (TTL 24h)
│   ├── macro_fetcher.py        # FRED REST API (TTL 7일)
│   ├── congress_fetcher.py     # 의원거래 (TTL 24h)
│   ├── insider_fetcher.py      # 내부자 거래 (TTL 24h)
│   ├── news_filter.py          # 뉴스 위험 키워드 필터
│   └── batch_scheduler.py      # 데몬 스레드 배치 + 진행 게이지
├── static/css/                 # base.css / screen.css / signals.css / about.css
├── static/js/                  # screen.js / signals.js
├── templates/                  # base.html / screen.html / signals.html / about.html
└── data/watchlist.json         # Watchlist 영구 저장 (git 제외)
```

### Key Architectural Patterns

**SSE 스트리밍:** `EventSource → FastAPI generate() → ThreadPoolExecutor → done 이벤트(HTML)`

**스크리닝 파이프라인:**
```
finviz_filter → fetch_ohlcv → today_changes → news_filter
→ indicators → checklist → grade → extras 병렬 (4종)
```

**시그널 파이프라인:**
```
watchlist_store.load() → fetch_ohlcv + fetch_intraday (병렬)
→ score_signals() → STRONG BUY / BUY / WATCH / NO SIGNAL
```

**Watchlist 브리지:** 스크리닝 카드 ★ 클릭 → `POST /api/watchlist/{ticker}` → `/signals` 자동 분석

### Key Config Values (config.py)
```python
RSI_HARD_GATE = 80     # 이상이면 무조건 SKIP
RSI_IDEAL_MIN = 45
RSI_IDEAL_MAX = 65
DATA_PERIOD   = "6mo"  # yfinance 기본 기간
TARGET_1_PCT  = 0.08   # +8% (고급 설정에서 변경 가능)
STOP_LOSS_PCT = 0.07   # -7%
```

### Grading (비율 기반)
```
_GRADE_RATIOS = [("S", 0.67), ("A", 0.44), ("B", 0.22)]
# 체크리스트 항목 비활성화 시 분모 자동 조정
```

### Signal Scoring (4카테고리)
| 카테고리 | 가중치 | 지표 | 점수 방식 |
|---------|:---:|-----|---------|
| Trend | 35% | MA 정배열(MA20>MA60) + 가격이 진입존(MA60~MA20+0.5ATR) 안 | 0/1 구조 조건 |
| Momentum | 25% | StochRSI k<0.3 강도 + BB %B<0.20 강도 | 연속값 강도 |
| Volume | 25% | OBV_MA10>OBV_MA30 정배열 + 거래대금 급증 강도(1x→0, 2x→1.0) | 연속값 강도 |
| Pattern | 15% | 최근 3봉 강세 캔들 패턴 수/2 (최대 1.0) | 수 기반 정규화 |

등급 임계값: STRONG BUY ≥ 0.60 / BUY ≥ 0.40 / WATCH ≥ 0.20

### Environment Variables
```
FRED_API_KEY         # FRED 매크로 (없으면 배너 숨김)
QUIVERQUANT_API_KEY  # 의원거래 (없으면 스킵)
REFRESH_TOKEN        # GitHub Actions → Render 배치 인증
```

### Notes
- venv 위치: `~/fin_auto_venv` (iCloud Desktop 동기화 문제 회피)
- `run.sh`가 8000 포트 기존 프로세스 종료 후 서버 재시작
- yfinance는 15~20분 지연 (스크리닝/시그널 목적에 충분)
- Finviz 무료 버전 스크래핑 제한 → 재시도 3회 + 지수 백오프

---

## Docs File Map
```
docs/
├── design_doc.md              ← 항상 로드 (전체 시스템 설계)
├── architecture.md            ← 아키텍처 상세 + API 목록
├── changelog.md               ← 변경 이력
├── adr/                       ← 의사결정 기록 (ADR-001~016)
├── skills/                    ← 핵심 구현 스킬 레퍼런스 (5종)
└── phases/
    ├── phase-service-split.md ← Phase 0~6 구현 이력
    └── phase-future.md        ← 미구현 기능 계획 (프론트 리디자인 1순위)
```
