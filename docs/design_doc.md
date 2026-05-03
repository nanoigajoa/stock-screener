# Design Document
## StockScope — 미국 주식 스크리닝 + 매매시그널 시스템

> **Status:** 운영 중 (2026-05-01) — 스크리닝 + 매매시그널 서비스 완전 분리 완료  
> **아키텍처:** [docs/architecture.md](architecture.md) | **변경이력:** [docs/changelog.md](changelog.md)

---

## Problem Statement

매일 수천 개 미국 주식 중 기술적 매수 조건을 충족하는 종목을 수동 탐색하는 데 소요되는 시간을 자동화로 제거한다. 두 단계로 분리해 해결한다:

1. **스크리닝** — 7개 기술적 체크리스트로 S/A/B/SKIP 등급 분류 (종목 건강도)
2. **매매시그널** — 관심종목에 대한 4카테고리 가중 채점으로 진입 타이밍 판단

---

## System Architecture

### 서비스 1 — 스크리닝 (`/screen`)
> "오늘 어떤 종목을 봐야 하나?" — 우주 탐색기

```
[Finviz API]
     │
     ▼
finviz_filter.py ──→ [ticker list, ETF 제거]
     │
     ▼
data_fetcher.py ──→ [OHLCV DataFrame, 당일 캐싱]
     │
     ├── get_today_changes() ──→ [당일 등락률%, 병렬 조회]
     │        │
     │    TODAY_CHANGE 범위 밖 → SKIP
     │
     ▼
news_filter.py ──→ [뉴스 위험 키워드 체크, 48h 이내]
     │ 위험 키워드 감지 → SKIP
     ▼
indicators.py ──→ [MA5/20/60/120, RSI14, MACD, BB20, Vol MA20, HH/HL]
     │
     ▼
checklist.py ──→ [7개 항목 가변점수, RSI 하드게이트]
     │
     ▼
grader.py ──→ [grade: S/A/B/SKIP, targets, stop-loss]
     │
     └──→ screen.py (SSE) ──→ 브라우저 카드 렌더링
                                  │
                           [★ 관심종목 추가] (Phase 6)
```

### 서비스 2 — 매매시그널 (`/signals`)
> "지금 X 종목에 들어가도 되나?" — 타이밍 레이더

```
[Watchlist] data/watchlist.json
     │
     ▼
data_fetcher.py ──→ [OHLCV (일봉) + fetch_intraday (시간봉)]
     │
     ▼
signal_scorer.py ──→ [4카테고리 가중 채점]
     │   ├── Trend   35%: MA 정배열(MA20>MA60) + 진입존(MA60~MA20+0.5ATR)  ← 0/1 구조 조건
     │   ├── Momentum 25%: RSI 구간점수(55 중심 종형) + StochRSI/Z-Score 보너스  ← 연속값
     │   ├── Volume  25%: CMF 자금흐름 강도(0.15=만점) + OBV MA 정배열(10/30)  ← 연속값
     │   └── Pattern 15%: LiquiditySweep(1.5단위)/기타(1.0단위) ÷ 2           ← 단위 정규화
     ▼
signal_service.py ──→ [STRONG BUY(≥0.60) / BUY(≥0.40) / WATCH(≥0.20) / NO SIGNAL]
     │                  [진입가 밴드(MA60~MA20+0.5ATR), 손절가(MA60-1ATR)]
     └──→ signals.py (SSE) ──→ 브라우저 시그널 카드 렌더링
```

### Funnel + Watchlist 연결 흐름

```
[스크리닝 /screen]           [매매시그널 /signals]
 Finviz → S/A/B 등급    →    Watchlist → 채점 → STRONG BUY 순 정렬
              │ (★ 추가)
              ▼
         Watchlist (JSON)
              ↑ (직접 입력도 가능)
```

---

## Component Breakdown

### 스크리닝 서비스

| Component | Responsibility | Status |
|-----------|---------------|--------|
| `config.py` | 모든 설정값 중앙화 | ✅ 완료 |
| `screener/finviz_filter.py` | Finviz 필터 적용, ETF 제거, 재시도 3회 | ✅ 완료 |
| `screener/data_fetcher.py` | OHLCV 배치 수집 + 당일 캐싱, 시간봉 수집 추가 | ✅ 완료 |
| `screener/news_filter.py` | 48h 뉴스 위험 키워드 필터 | ✅ 완료 |
| `screener/indicators.py` | pandas-ta 지표 계산, 시그널 전용 보조지표 포함 | ✅ 완료 |
| `screener/checklist.py` | 7개 항목 가변점수 채점, RSI 하드게이트 | ✅ 완료 |
| `screener/grader.py` | 점수 → 등급, 목표가/손절 계산 | ✅ 완료 |
| `services/screener_service.py` | 스크리닝 파이프라인 오케스트레이터 | ✅ 완료 |
| `api/routes/screen.py` | SSE 스트리밍, 카드 HTML 렌더링 | ✅ 완료 |

### 매매시그널 서비스

| Component | Responsibility | Status |
|-----------|---------------|--------|
| `screener/watchlist_store.py` | JSON 기반 Watchlist CRUD (threading.Lock) | ✅ 완료 |
| `api/routes/watchlist.py` | Watchlist REST API (GET/POST/DELETE) | ✅ 완료 |
| `services/signal_service.py` | 시그널 분석 오케스트레이터 (ThreadPoolExecutor x4) | ✅ 완료 |
| `api/routes/signals.py` | `/signals` 페이지 + `/stream/signals` SSE | ✅ 완료 |
| `templates/signals.html` | 시그널 대시보드 UI (Watchlist 패널 + 필터) | ✅ 완료 |
| `static/js/signals.js` | Watchlist 태그 + SSE 핸들러 + 차트 모달 | ✅ 완료 |
| `static/css/signals.css` | 시그널 카드 스타일 + 모달 CSS | ✅ 완료 |

---

## Data Model

```python
# 스크리닝 결과
StockResult = {
    "ticker": str,
    "price": float,
    "grade": Literal["S", "A", "B", "SKIP"],
    "score": int,
    "action": str,          # 진입 전략 텍스트
    "checklist": {
        item_key: {
            "name": str,
            "pass": bool,   # 표시용 (True/False)
            "score": int,   # 실제 점수 (MA는 0/1/2, 나머지 0/1)
            "weight": int,
            "detail": str,
        }
    },
    "target_1": float,      # price * 1.08
    "target_2": float,      # price * 1.15
    "stop_loss": float,     # price * 0.85
    "reason": str,          # SKIP 사유 (필터 A/B 걸린 경우)
}

# 매매시그널 결과
SignalResult = {
    "ticker": str,
    "price": float,
    "signal_grade": Literal["STRONG BUY", "BUY", "WATCH", "NO SIGNAL"],
    "signal_score": float,       # 0.0~1.0 가중 합산
    "signal_breakdown": {
        "trend": float,          # MA 정배열 강도(spread%) + ATR 진입존 위치(0/0.5/1.0) 평균 (35%)
        "momentum": float,       # RSI 구간점수(45~65 종형) + StochRSI/Z-Score 보너스 (25%)
        "volume": float,         # CMF 자금흐름 강도 + OBV MA 정배열(0/1) 평균 (25%)
        "pattern": float,        # LiquiditySweep(1.5단위)/기타(1.0단위) 합산 ÷ 2, 최대 1.0 (15%)
    },
    "entry_low": float | None,   # MA60 (추세 하단 지지)
    "entry_high": float | None,  # MA20 + 0.5*ATR (상단 버퍼)
    "signal_stop": float | None, # MA60 - 1.0*ATR
}
```

---

## API / Interface Design

### Web 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | About 페이지 (기본 진입) |
| GET | `/screen` | 스크리닝 메인 페이지 |
| GET | `/signals` | 매매시그널 대시보드 (Phase 4+) |
| GET | `/about` | About 페이지 |
| GET | `/stream/screen` | SSE 스크리닝 스트림 |
| GET | `/stream/signals` | SSE 시그널 스트림 (Phase 4+) |
| GET | `/api/watchlist` | Watchlist 조회 (Phase 2+) |
| POST | `/api/watchlist/{ticker}` | Watchlist 추가 (Phase 2+) |
| DELETE | `/api/watchlist/{ticker}` | Watchlist 삭제 (Phase 2+) |
| GET | `/api/chart-data/{ticker}` | 차트 데이터 (캔들 + MA + 마커) |

### Internal Module Interfaces
```python
# finviz_filter.py
def get_filtered_tickers(retries: int = 3) -> list[str]

# data_fetcher.py
def fetch_ohlcv(tickers: list[str]) -> dict[str, pd.DataFrame]
def fetch_intraday(ticker: str, interval: str = "1h", period: str = "5d") -> pd.DataFrame
def get_today_changes(tickers: list[str], timeout: int = 6) -> dict[str, float]

# news_filter.py
def check_news_risk(ticker: str) -> tuple[bool, str]

# indicators.py
def calculate_indicators(df: pd.DataFrame) -> dict | None
def calc_atr_zones(df: pd.DataFrame) -> dict        # 진입존 = MA60~MA20+0.5ATR
def calc_stoch_rsi(df: pd.DataFrame) -> dict
def calc_bb_advanced(df: pd.DataFrame) -> dict
def calc_obv_divergence(df: pd.DataFrame) -> dict   # OBV MA10 vs MA30 정배열
def calc_ma_alignment(df_d: pd.DataFrame, df_h: pd.DataFrame) -> dict  # 현재 정배열 상태
def calc_value_spike(df: pd.DataFrame) -> dict
def calc_cmf(df: pd.DataFrame, length: int = 21) -> dict   # Chaikin Money Flow

# buy_signal.py (2026-05-02+)
def compute_buy_signals(df: pd.DataFrame) -> list[dict]    # [{time, type, price, reason}]

# sell_signal.py (2026-05-02+)
def compute_sell_signals(df: pd.DataFrame) -> list[dict]

# checklist.py
def score_ticker(ind: dict, rsi_min, rsi_max, enabled_checks) -> dict

# grader.py
def grade(score_result: dict, ticker: str, price: float) -> dict

# signal_scorer.py (Phase 3+)
def score_signals(df_daily: pd.DataFrame, df_hourly: pd.DataFrame) -> dict

# watchlist_store.py (Phase 1+)
def load() -> list[str]
def add(ticker: str) -> list[str]
def remove(ticker: str) -> list[str]
def clear() -> list[str]

# signal_service.py (Phase 3+)
def run_signal_analysis(tickers: list[str]) -> dict
```

---

## Tech Stack

| Layer | Library | 비고 |
|-------|---------|------|
| Screening | finviz | ETF 제거 로직 포함 |
| Data | yfinance | OHLCV + fast_info (당일 등락률) |
| Indicators | pandas-ta | 컬럼명 동적 탐색으로 버전 호환 |
| Data Processing | pandas, numpy | — |
| Scheduling | schedule | 매일 08:00 |
| Output | colorama | 등급별 색상 |
| Concurrency | concurrent.futures | get_today_changes 병렬화 |
| Runtime | Python | 3.12 (3.10+ 호환) |

---

## Risk Analysis

| Risk | Impact | Mitigation |
|------|--------|------------|
| Finviz 스크래핑 차단 | High | 재시도 3회 + 지수 백오프, Elite 구독 고려 |
| yfinance fast_info hang | High | ThreadPoolExecutor 6초 timeout → 0.0 반환 |
| pandas-ta 컬럼명 변경 | Medium | startswith() 동적 탐색으로 버전 무관 |
| yfinance 데이터 지연 (15~20분) | Medium | 문서화, 실시간 필요 시 Alpha Vantage 전환 |
| 뉴스 API 누락/지연 | Low | 조회 실패 시 통과 처리 (보수적 기본값) |

---

## ADR Log

| ID | Decision | Rationale |
|----|----------|-----------|
| ADR-001 | pandas-ta 사용 | 7개 지표를 단일 라이브러리로 처리 |
| ADR-002 | RSI 하드게이트 80 | 과매수 진입 위험 즉시 제거 |
| ADR-003 | MA 정배열 가변 점수 (0/1/2) | 단기 정배열(부분점수 1)과 완전 정배열(2) 구분 |
| ADR-004 | 당일 등락률 사전 필터 | 전일 종가 기반 지표가 급등락 종목에 오신호 발생 |
| ADR-005 | get_today_changes 병렬화 | 개별 순차 조회 시 hang 발생 → ThreadPoolExecutor + timeout |
| ADR-006 | 뉴스 위험 키워드 필터 | 기술적 지표로 포착 불가한 희석/실적쇼크 이벤트 선제 차단 |
| ADR-007 | 거래량 이중 조건 (절대+상대) | Finviz 상대 거래량 필터가 절대량 얇은 종목을 통과시킴 |
| ADR-008 | 대화형 입력 모드 | CLI 인수 없이 실행 시 사용자 친화적 메뉴 제공 |
| ADR-017 | 매수/매도 신호 파일 분리 | 상태 머신 결합 → 독립 엔진 분리로 마커 신뢰성 확보 |
| ADR-018 | CMF로 거래대금 spike 교체 | spike는 이벤트성(발화 낮음) → CMF 연속값으로 score 분산 |
| ADR-019 | RSI 종형 곡선 모멘텀 재설계 | StochRSI 과매도 기반이 trend(상승 추세)와 상호 배타적 |

---

## Implementation Phases

### 완료된 Phase

| Phase | 내용 | 완료일 |
|-------|------|--------|
| Phase WebApp A·B·C | FastAPI + SSE 웹앱 전환 | 2026-04-25 |
| Phase Customization | RSI/체크리스트 커스터마이징 | 2026-04-26 |
| Phase Fundamentals | yfinance 펀더멘털 배지 | 2026-04-27 |
| Phase External Data | 매크로/의회/내부자/구글트렌드 | 2026-04-28 |
| Phase Signal Scoring | 4카테고리 매매타이밍 채점 | 2026-04-29 |
| Phase LW Charts | Lightweight Charts 모달 + 마스터 시그널 마커 | 2026-04-30 |
| Phase Signal QA | 시그널 채점 로직 6종 고도화 | 2026-05-01 |
| Phase Signal Quality 2 | 마커 아키텍처 분리 + CMF/RSI 재설계 + LiquiditySweep/Z-Score | 2026-05-02 |

---

### 서비스 분리 — Phase 0~6 ✅ 완료 (2026-05-01)

> 상세 이력: `docs/phases/phase-service-split.md`

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 0 | 기존 screener_service에서 signal 코드 제거 | ✅ 완료 |
| Phase 1 | `screener/watchlist_store.py` — JSON CRUD | ✅ 완료 |
| Phase 2 | `api/routes/watchlist.py` — REST API | ✅ 완료 |
| Phase 3 | `services/signal_service.py` — 독립 오케스트레이터 | ✅ 완료 |
| Phase 4 | `api/routes/signals.py` — SSE 스트리밍 | ✅ 완료 |
| Phase 5 | 시그널 프론트엔드 (signals.html/js/css) | ✅ 완료 |
| Phase 6 | 스크리닝 카드 ★ 버튼 → Watchlist 브리지 | ✅ 완료 |

---

### 다음 Phase — 프론트엔드 리디자인 (외부 공개 준비)

> 목표: 외부 서비스화를 위한 전문성 있는 금융 대시보드 디자인으로 전면 교체
> 우선 개선 영역: 전체 색상 체계 + 시그널 대시보드 (현재 빈약해 보임)

| 항목 | 방향 |
|------|------|
| 스택 | Tailwind CSS 도입 (기존 Vanilla CSS → 유지 or 교체 결정 필요) |
| 색상 | 트레이딩 터미널 계열 다크 테마 (현재 단순 다크 → 전문적 금융 UI) |
| 시그널 대시보드 | 카테고리별 게이지/바 + 진입존 시각화 + STRONG BUY 강조 레이아웃 |
| 스크리닝 카드 | 밀도 높은 컴팩트 카드 → 정보 계층 명확화 |
| 공통 | 타이포그래피 정비, 배지 디자인 통일, 반응형 |
