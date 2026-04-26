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

## Project: US Stock Auto Screener (미국 주식 자동 스크리닝 시스템)

Finviz로 종목 필터링 → 7개 기술적 체크리스트 자동 채점 → S/A/B/SKIP 등급 분류 → 터미널 출력 + CSV 저장 + 텔레그램/카카오 알림.

**Status:** Greenfield — `docs/design_doc.md` 먼저 작성 후 구현 시작.

### Tech Stack
- Python 3.10+, `finviz`, `yfinance`, `pandas-ta`, `pandas`, `numpy`, `schedule`, `colorama`, `requests`

### Intended Directory Structure
```
stock_screener/
├── main.py
├── config.py
├── screener/
│   ├── finviz_filter.py   # Finviz 필터링 → 티커 리스트
│   ├── data_fetcher.py    # yfinance OHLCV 수집 (6mo, 1d)
│   ├── indicators.py      # MA5/20/60/120, RSI14, MACD, BB20
│   ├── checklist.py       # 7개 항목 채점
│   └── grader.py          # S/A/B/SKIP 등급 분류
├── notifier/
│   ├── terminal.py        # colorama 터미널 출력
│   └── telegram.py        # Telegram + KakaoTalk 알림
├── utils/
│   └── logger.py
└── output/results/        # YYYY-MM-DD.csv 저장
```

### Pipeline Flow
```
Finviz Filter → ETF 제거 → yfinance OHLCV → Indicators → Checklist(7) → Grade → Output
```

### Commands
```bash
pip install -r requirements.txt
python main.py                         # 즉시 1회 실행
python main.py --schedule              # 매일 08:00 자동 실행
python main.py --ticker AAPL MSFT      # 특정 종목만 분석
python main.py --grade S               # S급만 출력
python main.py --save                  # CSV 저장
```

### Key Config Values (config.py)
```python
FINVIZ_FILTERS = {
    "geo": "usa", "sh_avgvol": "o2000", "sh_price": "o10",
    "sh_relvol": "o1.5", "ta_rsi": "nob60",
    "ta_sma20": "pa", "ta_sma50": "pa", "ta_sma200": "pa",
    "fa_epsqoq": "pos",
}
RSI_HARD_GATE    = 80      # 이상이면 무조건 SKIP
RSI_IDEAL_MIN    = 45
RSI_IDEAL_MAX    = 65
TARGET_1_PCT     = 0.08    # +8%
TARGET_2_PCT     = 0.15    # +15%
STOP_LOSS_PCT    = 0.15    # -15%
SCHEDULE_TIME    = "08:00"
OUTPUT_DIR       = "output/results"
MAX_RESULTS      = 20
```

### Grading
| Grade | Min Score | Action |
|-------|-----------|--------|
| S     | 6         | 즉시 진입 |
| A     | 4         | 분할 진입 검토 |
| B     | 2         | 대기 |
| SKIP  | 0 or RSI≥80 | 진입 금지 |

### Checklist Weights
| # | Item | Weight |
|---|------|--------|
| 1 | MA 정배열 (price > 5>20>60>120MA) | 2 |
| 2 | RSI 45~65 (hard gate: ≥80 → SKIP) | 2 |
| 3 | 거래량 > 평균 1.5배 | 1 |
| 4 | MACD 골든크로스 | 1 |
| 5 | 지지선 위 반등 | 1 |
| 6 | 볼린저밴드 중간선 위 | 1 |
| 7 | Higher High + Higher Low | 1 |

### Secrets
`TELEGRAM_BOT_TOKEN`, `KAKAO_ACCESS_TOKEN` → 환경변수 또는 `.env` 파일로 관리. 코드에 하드코딩 금지.

### Notes
- yfinance는 15~20분 지연 (실시간 필요 시 Alpha Vantage 고려)
- Finviz 무료 버전은 스크래핑 제한 있음 (Elite 구독 시 안정적)
- Phase 2 선택 기능: 백테스팅(`backtest.py`), 웹 대시보드(Flask + plotly, `localhost:5000`)

---

## Docs File Map
```
docs/
├── design_doc.md         ← 항상 로드 (구현 전 반드시 존재해야 함)
├── skills/               ← 해당 phase 필요 skill만 로드
├── templates/            ← 프로젝트 시작 시 로드
├── adr/                  ← 의사결정 필요 시 로드
└── phases/               ← 현재 phase만 로드
```
