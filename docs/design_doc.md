# Design Document
## US Stock Auto Screener

> **Status:** Phase 1 완료 (2026-04-25) — Phase 2 대기 중

---

## Problem Statement

매일 수천 개 미국 주식 중 기술적 매수 조건을 충족하는 종목을 수동 탐색하는 데 소요되는 시간을 자동화로 제거한다. 7개 기술적 체크리스트 기반 채점으로 S/A/B/SKIP 등급을 분류해 즉각적인 투자 판단 근거를 제공한다.

---

## System Architecture

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
     ├──→ terminal.py ──→ [colorama 터미널 출력]
     └──→ logger.py   ──→ [output/results/YYYY-MM-DD.csv]
```

**Template Used:** Data Pipeline CLI

---

## Component Breakdown

| Component | Responsibility | Status |
|-----------|---------------|--------|
| `config.py` | 모든 설정값 중앙화 | ✅ 완료 |
| `screener/finviz_filter.py` | Finviz 필터 적용, ETF 제거, 재시도 3회 | ✅ 완료 |
| `screener/data_fetcher.py` | OHLCV 배치 수집 + 당일 캐싱, 당일 등락률 병렬 조회 | ✅ 완료 |
| `screener/news_filter.py` | 48h 뉴스 위험 키워드 필터 (신규) | ✅ 완료 |
| `screener/indicators.py` | pandas-ta 지표 계산, 컬럼명 동적 탐색 | ✅ 완료 |
| `screener/checklist.py` | 7개 항목 가변점수 채점, RSI 하드게이트 | ✅ 완료 |
| `screener/grader.py` | 점수 → 등급, 목표가/손절 계산 | ✅ 완료 |
| `notifier/terminal.py` | colorama 색상 출력, 등급별 포맷 | ✅ 완료 |
| `utils/logger.py` | CSV 저장 (output/results/YYYY-MM-DD.csv) | ✅ 완료 |
| `main.py` | 파이프라인 통합, CLI + 대화형 입력 모드 | ✅ 완료 |

---

## Data Model

```python
# 종목별 분석 결과
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
```

---

## API / Interface Design

### CLI
```bash
python main.py                         # 대화형 모드 (메뉴 선택)
python main.py --ticker AAPL MSFT      # 직접 실행 (대화형 스킵)
python main.py --grade S               # 등급 필터
python main.py --save                  # CSV 저장
python main.py --schedule              # 매일 08:00 자동 실행
```

### 실행 파이프라인 (main.py)
```
1. 종목 수집 (Finviz 또는 직접 입력)
2. OHLCV 일괄 수집 (yfinance batch)
3. 당일 등락률 병렬 조회 → -5%↓/+15%↑ SKIP
4. 뉴스 위험 키워드 체크 → 감지 시 SKIP
5. 기술적 지표 계산
6. 7개 체크리스트 채점
7. 등급 분류
8. 정렬 (S→A→B→SKIP) + 출력
9. CSV 저장 (--save 옵션)
```

### Internal Module Interfaces
```python
# finviz_filter.py
def get_filtered_tickers(retries: int = 3) -> list[str]

# data_fetcher.py
def fetch_ohlcv(tickers: list[str]) -> dict[str, pd.DataFrame]
def get_today_changes(tickers: list[str], timeout: int = 6) -> dict[str, float]

# news_filter.py
def check_news_risk(ticker: str) -> tuple[bool, str]

# indicators.py
def calculate_indicators(df: pd.DataFrame) -> dict | None

# checklist.py
def score_ticker(ind: dict) -> dict  # {items, total_score, hard_skip}

# grader.py
def grade(score_result: dict, ticker: str, price: float) -> dict
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

---

## Implementation Phases

### Phase 1 — Core Pipeline ✅ 완료 (2026-04-25)
- **Goal:** 종목 필터링 → 채점 → 터미널 출력
- **추가 구현:** 당일변동 필터, 뉴스 필터, 거래량 이중 조건, 대화형 입력, CSV 저장, --schedule

### Phase 2 — Notifications
- **Goal:** Telegram / KakaoTalk 알림 발송
- **Tasks:**
  - [ ] `notifier/telegram.py` — S급 종목 텔레그램 발송
  - [ ] KakaoTalk 알림 (KAKAO_ACCESS_TOKEN 설정 시)
  - [ ] 환경변수 로드 (.env 파일 지원)
- **DoD:** S급 종목 텔레그램 메시지 수신 확인

### Phase 3 — Advanced (선택)
- **Goal:** 백테스팅 + 웹 대시보드
- **Tasks:**
  - [ ] `backtest.py` — 6개월 데이터로 신호 검증, 승률/수익률
  - [ ] `dashboard.py` — Flask + plotly, localhost:5000
- **DoD:** 백테스트 승률 출력, 대시보드 접속
