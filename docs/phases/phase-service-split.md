# Phase: 스크리닝 서비스 / 매매시그널 서비스 완전 분리

> **작성일:** 2026-05-01 | **완료:** 2026-05-01  
> **상태:** ✅ Phase 0~6 전체 완료  
> **의존성:** signal_scorer.py, data_fetcher.py, indicators.py 재사용

---

## 배경 및 목적

현재 `screener_service.py` 한 파일이 두 역할을 동시에 수행한다:
- 7개 체크리스트 기반 종목 등급 분류 (스크리닝)
- 4카테고리 가중 시그널 채점 (매매 타이밍)

이로 인해:
- 시그널만 보고 싶어도 스크리닝 파이프라인 전체를 실행해야 함
- 스크리닝을 통과 못한 종목은 시그널 채점 자체가 불가능
- UI에서 두 서비스가 뒤섞여 목적이 불분명

**목표:** 두 서비스를 독립된 페이지·파이프라인으로 분리한다.

---

## 두 서비스 정의

### 스크리닝 서비스 (`/screen`)
> "오늘 어떤 종목을 봐야 하나?" — 우주 탐색기

| 항목 | 내용 |
|------|------|
| 사용 주기 | 주 2~3회 (시장 개장 전 배치) |
| 입력 | Finviz 필터 또는 수동 티커 |
| 핵심 질문 | 이 종목이 *기술적으로 건강한가?* |
| 지표 | MA 정배열 / RSI 구간 / 거래량 / MACD / 지지선 / BB / HH+HL |
| 출력 | S/A/B/SKIP 등급 + 체크리스트 상세 |

### 매매시그널 서비스 (`/signals`)
> "지금 X 종목에 들어가도 되나?" — 타이밍 레이더

| 항목 | 내용 |
|------|------|
| 사용 주기 | 매일 (장 시작 전 / 장 중) |
| 입력 | Watchlist (스크리닝 결과 추가 or 직접 입력) |
| 핵심 질문 | 지금 *가격이 진입 타이밍인가?* |
| 지표 | ATR 진입존 / StochRSI / BB %B / OBV 다이버전스 / 거래대금 급증 / 캔들 패턴 |
| 출력 | STRONG BUY / BUY / WATCH / NO SIGNAL + 진입가 밴드 + 손절가 |

---

## 지표 배분

| 지표 | 스크리닝 | 시그널 | 이유 |
|------|:---:|:---:|------|
| MA 정배열 (5/20/60/120) | ✓ | ✗ | 종목 구조 건강도 |
| RSI(14) | ✓ | ✗ | 스크리닝에서 45~65 범위 확인 |
| 거래량 (절대·상대) | ✓ | ✗ | 유동성 필터 |
| MACD 크로스 | ✓ | ✗ | 중기 방향성 |
| 볼린저밴드 중간선 | ✓ | ✗ | 강세 구간 여부 |
| Higher High + Higher Low | ✓ | ✗ | 추세 지속성 |
| ATR 진입존 | ✗ | ✓ | 눌림목 타이밍 전용 |
| StochRSI 반등 | ✗ | ✓ | 단기 과매도 반등 |
| BB %B | ✗ | ✓ | 밴드 하단 반전 타이밍 |
| OBV 다이버전스 | ✗ | ✓ | 수급 확인 |
| 거래대금 급증 | ✗ | ✓ | 세력 개입 포착 |
| 강세 캔들 패턴 | ✗ | ✓ | 최종 진입 트리거 |

> **혼용 가능 지표:** RSI·거래량은 양쪽에서 사용 가능하나 임계값과 목적이 다름.  
> 코드 레벨에서 중복 없이 각 서비스 내부에서 독립 계산 유지.

---

## 아키텍처: Funnel + Watchlist

```
[스크리닝 서비스]  /screen
 Finviz → N개 후보 → S/A/B/SKIP 등급
    │
    │  (선택적 연결)
    ▼
  카드별 "★ 관심종목 추가" 버튼
    │
    ▼
[Watchlist]  data/watchlist.json
  AAPL, NVDA, MSFT ...
    │
    ▼
[매매시그널 서비스]  /signals
 Watchlist → 4카테고리 채점 → STRONG BUY 순 정렬
 + 진입가 밴드 + 손절가
```

---

## 확정 결정사항

| 항목 | 결정 |
|------|------|
| Watchlist 저장 | JSON 파일 (`data/watchlist.json`), 추후 DB 연동 |
| 시그널 실행 | 페이지 접속 시 자동 실행 (SSE 스트리밍) |
| 스크리닝 → 시그널 연결 | 카드별 개별 추가 버튼 |
| 시그널 단독 사용 | 허용 (티커 직접 입력) |

---

## 신규 파일 목록

```
fin_auto/
├── data/
│   └── watchlist.json              ← Watchlist 저장 파일 (git ignore)
├── screener/
│   └── watchlist_store.py          ← Phase 1: JSON 저장/로드 레이어
├── services/
│   └── signal_service.py           ← Phase 3: 시그널 오케스트레이터
├── api/routes/
│   ├── watchlist.py                ← Phase 2: CRUD REST API
│   └── signals.py                  ← Phase 4: /signals 페이지 + SSE
├── templates/
│   └── signals.html                ← Phase 5: 시그널 대시보드
└── static/
    ├── css/signals.css             ← Phase 5
    └── js/signals.js               ← Phase 5
```

---

## Phase 0 — 기존 코드 정리

**목표:** screener_service.py에서 signal 코드 제거. 스크리닝은 등급만 반환.

**변경 파일:**

| 파일 | 변경 내용 |
|------|----------|
| `services/screener_service.py` | Step 10 시그널 블록 제거, signal 관련 import 제거 |
| `api/routes/screen.py` | `_render_view_controls()` 제거, 시그널 탭 HTML 제거, `data-signal-*` 속성 제거 |
| `static/js/screen.js` | `_switchView`, `_applySignalFilter`, `_SIGNAL_ORDER` 제거 |

**완료 기준:**
- 스크리닝 결과 카드에 signal_grade 미포함
- `/screen` 페이지 — 탭 없음, 등급뷰만 존재
- 스크리닝 속도 단축 (시간봉 fetch 없어짐)

---

## Phase 1 — Watchlist 저장소

**신규 파일:** `screener/watchlist_store.py`

```python
WATCHLIST_PATH = Path("data/watchlist.json")

def load() -> list[str]
def save(tickers: list[str]) -> None
def add(ticker: str) -> list[str]      # 중복 무시, 대문자 정규화
def remove(ticker: str) -> list[str]
def clear() -> list[str]
```

**완료 기준:**
- `add("aapl")` → `["AAPL"]` 저장, 대문자 정규화 확인
- 서버 재시작 후 `load()` → 이전 목록 복원
- `data/watchlist.json` `.gitignore` 추가

---

## Phase 2 — Watchlist REST API

**신규 파일:** `api/routes/watchlist.py`

```
GET    /api/watchlist           → {"tickers": ["AAPL", "NVDA"]}
POST   /api/watchlist/{ticker}  → {"tickers": [...]}  (추가)
DELETE /api/watchlist/{ticker}  → {"tickers": [...]}  (삭제)
DELETE /api/watchlist           → {"tickers": []}     (전체 초기화)
```

**변경 파일:** `api/main.py` — watchlist 라우터 include

**완료 기준:**
- `curl -X POST http://localhost:8000/api/watchlist/AAPL` → 200 + 목록 반환
- `curl -X DELETE http://localhost:8000/api/watchlist/AAPL` → 200 + 삭제 확인
- `curl http://localhost:8000/api/watchlist` → 현재 목록 반환

---

## Phase 3 — 시그널 서비스 백엔드

**신규 파일:** `services/signal_service.py`

```python
def run_signal_analysis(tickers: list[str]) -> dict:
    """
    Returns:
    {
        "results": [
            {
                "ticker": str,
                "price": float,
                "signal_grade": "STRONG BUY"|"BUY"|"WATCH"|"NO SIGNAL",
                "signal_score": float,       # 0.0~1.0
                "signal_breakdown": {        # 4카테고리
                    "trend": float,
                    "momentum": float,
                    "volume": float,
                    "pattern": float,
                },
                "entry_low": float | None,
                "entry_high": float | None,
                "signal_stop": float | None,
            },
            ...
        ],
        "summary": {
            "total": int,
            "strong_buy": int,
            "buy": int,
            "watch": int,
            "no_signal": int,
        }
    }
    """
```

**재사용 모듈:**
- `screener/data_fetcher.py` — `fetch_ohlcv()`, `fetch_intraday()`
- `screener/signal_scorer.py` — `score_signals()` (변경 없음)

**파이프라인:**
```
tickers → fetch_ohlcv(daily) → [병렬] fetch_intraday(1h)
       → score_signals(df_daily, df_hourly) per ticker
       → STRONG BUY 순 정렬
       → return
```

**완료 기준:**
- `run_signal_analysis(["AAPL", "NVDA"])` → 두 종목 signal_grade 포함 결과
- 스크리닝 실행 없이 단독 호출 가능

---

## Phase 4 — 시그널 페이지 API

**신규 파일:** `api/routes/signals.py`

```python
@router.get("/signals")
def signals_page(request: Request): ...         # signals.html 렌더링

@router.get("/stream/signals")
async def stream_signals(tickers: str = ""):    # SSE 스트리밍
    # tickers 비어있으면 Watchlist 자동 로드
    # SSE events: progress / done / error
```

**SSE done 이벤트 payload:**
```json
{
  "html": "<div class='signal-results'>...</div>",
  "watchlist": ["AAPL", "NVDA"]
}
```

**변경 파일:** `api/main.py` — signals 라우터 include, `templates/base.html` — nav 링크 추가

---

## Phase 5 — 시그널 페이지 프론트엔드

**신규 파일:** `templates/signals.html`, `static/js/signals.js`, `static/css/signals.css`

**UI 레이아웃:**
```
/signals
┌──────────────────────────────────────────────┐
│ 관심종목                                      │
│ [AAPL ×] [NVDA ×] [MSFT ×]   [+ 추가]        │
├──────────────────────────────────────────────┤
│ 필터: [전체] [⚡ STRONG BUY] [▲ BUY] [◎ WATCH]│
├──────────────────────────────────────────────┤
│ ⚡ NVDA   $870   STRONG BUY  87%             │
│   추세 ◑  모멘텀 ✓  수급 ✓  패턴 ✓          │
│   진입존 $852~$865  손절 $821   [차트 분석 →] │
├──────────────────────────────────────────────┤
│ ▲ AAPL   $272   BUY  61%                    │
│   추세 ✓  모멘텀 ◑  수급 ✗  패턴 ✓          │
│   진입존 $262~$267  손절 $254   [차트 분석 →] │
└──────────────────────────────────────────────┘
```

**JS 주요 기능:**
- 페이지 로드 시 자동 SSE 시작 (Watchlist 자동 로드)
- 관심종목 태그 추가/삭제 (POST/DELETE `/api/watchlist/{ticker}`)
- 필터 클릭 → 클라이언트 사이드 grade 필터링
- 차트 분석 버튼 → 기존 chart modal 재사용 (LW Charts)

**nav 추가:** `base.html` 네비게이션에 `/signals` 링크

---

## Phase 6 — 스크리닝 → 시그널 브리지

**목표:** 스크리닝 카드에서 관심종목 개별 추가.

**변경 파일:**
- `api/routes/screen.py` — 카드 compact 헤더에 watchlist 버튼 추가
  ```html
  <button class="watchlist-btn" data-ticker="AAPL" title="관심종목 추가">★</button>
  ```
- `static/js/screen.js` — watchlist-btn 클릭 핸들러
  ```javascript
  // POST /api/watchlist/{ticker}
  // 성공 → 버튼 class="watchlist-btn added" (노란 별)
  // 이미 있으면 → disabled
  ```
- 페이지 로드 시 현재 Watchlist 조회 → 이미 추가된 종목 버튼 상태 반영

---

## 검증 순서

```
Phase 0: ./run.sh → /screen 접속 → 스크리닝 실행 → 탭 없음, 카드 정상
Phase 1: Python REPL → watchlist_store.add("AAPL") → watchlist.json 확인
Phase 2: curl로 CRUD 테스트
Phase 3: Python REPL → run_signal_analysis(["AAPL"]) → 결과 확인
Phase 4: curl http://localhost:8000/stream/signals?tickers=AAPL → SSE 응답 확인
Phase 5: /signals 접속 → 자동 분석 → 카드 렌더링 → 필터 동작
Phase 6: /screen 스크리닝 후 ★ 버튼 → /signals 접속 → 해당 종목 포함 확인
```
