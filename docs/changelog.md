# Changelog — fin_auto

모든 기능 추가 / 수정 / 미구현 계획의 시간순 기록.

---

## [2026-04-25] Phase WebApp A·B·C — FastAPI + SSE 웹앱 전환

### 배경
CLI 전용 스크리너를 브라우저에서 사용 가능한 웹앱으로 전환.
초기 계획(Celery + Redis)에서 **SSE(Server-Sent Events)** 방식으로 변경 (ADR-013).

### 구현 완료

| 파일 | 작업 |
|------|------|
| `services/screener_service.py` | CLI·웹 공용 `run_analysis()` 추출 |
| `api/main.py` | FastAPI 앱 + StaticFiles 마운트 |
| `api/routes/screen.py` | `/stream/screen` SSE 엔드포인트, `/health` |
| `templates/base.html` | Jinja2 레이아웃 (인라인 CSS 제거, 네비게이션 포함) |
| `templates/screen.html` | 스크리닝 메인 페이지 |
| `static/css/base.css` | 전역 스타일 + 네비게이션 (CSS 변수 기반 다크 테마) |
| `static/css/screen.css` | 스크리너 전용 스타일 |
| `static/js/screen.js` | TomSelect + SSE EventSource 핸들러 |

### 변경 (기존 파일)

| 파일 | 변경 내용 |
|------|----------|
| `config.py` | `TODAY_CHANGE_MIN/MAX`, `NEWS_FILTER_ENABLED` 등 상수 추가 |
| `screener/data_fetcher.py` | `threads=False` 추가 (Celery pickle 충돌 방지) |
| `requirements.txt` | `fastapi`, `uvicorn`, `jinja2`, `python-dotenv` 추가 |

---

## [2026-04-26] 사용자 커스터마이징 3종

### 구현 완료

**1. 데이터 기간 선택 (3mo / 6mo / 1yr)**
- `screener/data_fetcher.py`: `fetch_ohlcv(tickers, period=DATA_PERIOD)` — period 파라미터 추가, 캐시 키 `ticker` → `(ticker, period)`
- `services/screener_service.py`: `run_analysis(period=...)` 파라미터 추가
- `api/routes/screen.py`: `period` 쿼리 파라미터 추가
- `templates/screen.html`: 데이터 기간 드롭다운 추가

**2. RSI 범위 조정 (min / max 숫자 입력)**
- `screener/checklist.py`: `score_ticker(ind, rsi_min=RSI_IDEAL_MIN, rsi_max=RSI_IDEAL_MAX, ...)` 시그니처 확장
- `services/screener_service.py`: `run_analysis(rsi_min=..., rsi_max=...)` 파라미터 추가
- `api/routes/screen.py`: `rsi_min`, `rsi_max` 쿼리 파라미터 추가
- `templates/screen.html`: 고급 설정 패널 — RSI min/max 입력 필드

**3. 체크리스트 항목 on/off (7개 토글)**
- `screener/checklist.py`: `enabled_checks: list[str] | None` 파라미터 추가. None이면 전체 7개 채점. 반환값에 `max_score` 포함
- `screener/grader.py`: 고정 임계값 → **비율 기반** 등급 계산
  ```
  _GRADE_RATIOS = [("S", 0.67), ("A", 0.44), ("B", 0.22)]
  # 원래 기준(6/9, 4/9, 2/9) 그대로, 항목 비활성화 시 자동 조정
  ```
- `api/routes/screen.py`: `checks` 쿼리 파라미터 추가 (쉼표 구분)
- `templates/screen.html`: 고급 설정 패널 — 7개 체크박스
- `static/js/screen.js`: 체크박스 상태 수집 → `checks` 파라미터로 전송

---

## [2026-04-27] yfinance 펀더멘털 배지 4종

### 구현 완료

**신규 파일:** `screener/fundamental_fetcher.py`

| 배지 | 조건 | 색상 |
|------|------|------|
| `⚠️ 실적 D-N` | 7일 이내 실적 발표 | 빨간 |
| `📅 실적 D-N` | 8~14일 이내 실적 발표 | 노란 |
| `숏비율 N.Nd` | Short Ratio ≥ 5 | 파란 |
| `목표가 $X (+Y%)` | 애널리스트 컨센서스 목표가 존재 | 초록 |
| `내부자 매수 ✅` | 90일 내 임원 매수 (yfinance) | 금색 |

- `services/screener_service.py`: `displayable` 종목에만 `fetch_fundamentals()` 호출 후 `r["extras"]` 삽입
- `api/routes/screen.py`: `_render_extras()` 함수 추가, 배지 HTML 생성
- `static/css/base.css`: `.badge`, `.badge-red`, `.badge-yellow`, `.badge-blue`, `.badge-green`, `.badge-gold` 스타일 추가

---

## [2026-04-27] 프론트엔드 대개편

### 구현 완료

**분리 작업:**
- 인라인 CSS → `static/css/base.css`, `screen.css`, `about.css`
- 인라인 JS → `static/js/screen.js`
- Tom Select CDN 추가 (멀티 티커 입력)

**신규 페이지:**
- `templates/about.html` — 시스템 설명 (초보자용)
  - Hero: 한 줄 소개
  - 데이터 파이프라인 플로우차트 (CSS only)
  - 7개 지표 카드 (쉬운 설명)
  - 등급 기준 카드 (S/A/B/SKIP)
  - 펀더멘털 배지 설명
  - 진입 전략 (목표가/손절)
  - 데이터 지연 안내
- `static/css/about.css` — About 전용 스타일
- `api/main.py`: `/about` 라우트 추가
- `templates/base.html`: 상단 네비게이션 바 (스크리닝 / About 링크, active 표시)

---

## [2026-04-28] 외부 데이터소스 4종 통합

### 구현 완료

**신규 파일 5개:**

| 파일 | 소스 | 방식 | TTL |
|------|------|------|-----|
| `screener/trends_fetcher.py` | pytrends (Google Trends) | Lazy per-ticker | 24h |
| `screener/macro_fetcher.py` | fredapi (FRED) | Startup 배치 | 7일 |
| `screener/congress_fetcher.py` | quiverquant | Startup 배치 | 24h |
| `screener/insider_fetcher.py` | sec-edgar-downloader | Lazy per-ticker | 24h |
| `screener/batch_scheduler.py` | — | 데몬 스레드 | 24h 주기 |

**신규 배지:**

| 배지 | 조건 | 색상 |
|------|------|------|
| `구글 관심 N` | Google Trends 점수 ≥ 60 | 파란 |
| `의원 매수 ✅` | 90일 내 의회 의원 매수 기록 | 금색 |
| `내부자 매수 ✅` | SEC Form 4 기준 90일 내 매수 (yfinance → SEC 교체) | 금색 |

**매크로 배너:** 화면 상단
```
📊 기준금리 3.64% · CPI 3.3% · 실업률 4.3% · 장단기금리차 0.53% · VIX N/A | 안정
```

**기존 파일 변경:**

| 파일 | 변경 내용 |
|------|----------|
| `config.py` | `FRED_API_KEY`, `QUIVERQUANT_API_KEY` 환경변수 추가 |
| `api/main.py` | `@on_event("startup")` → batch_scheduler.start() 비동기 실행 |
| `services/screener_service.py` | extras 수집을 ThreadPoolExecutor 4종 병렬로 전환 |
| `api/routes/screen.py` | `_render_extras()`에 구글관심도·의원매수 배지 추가 |
| `templates/screen.html` | 매크로 배너 추가 (Jinja2 `{{ macro }}` 컨텍스트) |
| `static/css/screen.css` | `.macro-banner`, `.macro-regime` 스타일 추가 |
| `screener/fundamental_fetcher.py` | `insider_bought` 로직 제거 (insider_fetcher.py로 이전) |
| `requirements.txt` | `pytrends`, `fredapi`, `quiverquant`, `sec-edgar-downloader` 추가 |

**환경 설정:**
- `.env` 파일 생성: `FRED_API_KEY=7bfbf998...`
- QuiverQuant 유료 — 키 미설정 시 의원거래 자동 스킵

---

## [2026-04-28] UI 대개편 · 외부 데이터 안정화 · 배치 로그 개선

### 1. 지표 표시 방식 전면 변경 — 항상 전체 표시

**배경:** 기존에는 조건을 충족한 배지만 표시 → 충족 못하면 아예 안 보임.

**변경:** 7개 지표를 항상 전부 표시, 조건 충족 여부에 따라 색상만 다르게.

| 파일 | 변경 내용 |
|------|----------|
| `api/routes/screen.py` | `_render_signal_row()` + `_render_extras()` 제거 → `_render_all_indicators()` + `_b()` 헬퍼로 대체 |
| `static/css/screen.css` | `.indicators`, `.sig-ok`, `.sig-bad`, `.sig-warn`, `.sig-dim`, `.sig-na`, `.badge-label`, `.badge-val` 클래스 추가 |

표시 항목: 뉴스 · 내부자 매수 · 의원 매수 · 구글 관심 · 실적 · 숏비율 · 목표가

---

### 2. TradingView 미니 차트 수정

**원인:** TradingView 위젯 스크립트가 부모 div에서 `tradingview-widget-container` 클래스를 찾는데 없었음.

**수정:** `_tv_widget()` 외부 div에 `tradingview-widget-container` 클래스 추가.

```python
# 수정 전
f'<div class="tv-widget">'
# 수정 후
f'<div class="tradingview-widget-container tv-widget">'
```

---

### 3. About 페이지를 기본 진입 페이지로 변경

| 라우트 | 변경 전 | 변경 후 |
|--------|--------|--------|
| `/` | 스크리닝 페이지 | About 페이지 |
| `/screen` | 없음 | 스크리닝 페이지 |
| `/about` | About 페이지 | About 페이지 (유지) |

About Hero에 "Screening 시작하기" CTA 버튼 및 페이지 하단 CTA 섹션 추가.

---

### 4. About 페이지 — 공포탐욕지수 섹션 추가 및 간소화

계산 방법 2줄 요약 표 + 한계 명시:

```
VIX 변동성 지수   50%   낮을수록 탐욕 — (40 − VIX) ÷ 30 × 100
SPY 60일 모멘텀   50%   MA60 대비 위치 — (SPY ÷ MA60 − 1 + 0.10) ÷ 0.20 × 100
```

CNN 공식 지수(7개 지표)와 차이 명시. 이전의 복잡한 박스 레이아웃 → 단순 2행 표로 교체.

---

### 5. FRED API 안정화

**문제:** CPIAUCSL, UNRATE 조회 시 간헐적 500 오류 발생.

**수정:**
- `_get_series()` 에 1회 재시도 로직 추가 (500 오류 시 1초 대기 후 재요청)
- `limit` 파라미터를 `max(limit, 30)` 으로 결측값(`.`) 여유분 확보

---

### 6. 공포탐욕지수 계산 속도 개선

**문제:** SPY 7개월 데이터 다운로드에 30초 소요.

**변경:** `period="7mo"` + `rolling(125)` → `period="4mo"` + `rolling(60)` 으로 단축.

```python
# 수정 전
close = yf.Ticker("SPY").history(period="7mo")["Close"].dropna()
ma125 = close.rolling(125).mean()
pct = (close.iloc[-1] - ma125.iloc[-1]) / ma125.iloc[-1] * 100
mom_score = max(0, min(100, (pct + 15) / 30 * 100))

# 수정 후
close = yf.Ticker("SPY").history(period="4mo")["Close"].dropna()
ma60 = close.rolling(60).mean()
pct = (close.iloc[-1] - ma60.iloc[-1]) / ma60.iloc[-1] * 100
mom_score = max(0, min(100, (pct + 10) / 20 * 100))
```

배치 예상 시간도 실측값 기준으로 조정: 매크로 5s→8s, 공포탐욕 8s→15s.

---

### 7. 배치 스케줄러 — 실시간 진행 게이지

서버 시작 시 터미널에 실시간 타임게이지 표시:

```
┌────────────────────────────────────────────┐
│  📦 배치 데이터 로드 시작  (예상 23초)     │
└────────────────────────────────────────────┘

  ▶ [매크로(FRED)]  예상 ~8초
  ○ [매크로(FRED)]  ████░░░░░░░░░░░░░░░░░░  2.0s / ~8s  (25%)
  ✔ [매크로(FRED)]  ██████████████████████  7.3s / ~8s (완료)
```

- `_progress_loop()`: 별도 스레드에서 0.25초마다 `\r` 덮어써서 게이지 갱신
- `_safe_run()`: 완료/실패 시 게이지 지우고 최종 결과(`✔`/`✗`) 출력
- 구현 파일: `screener/batch_scheduler.py`

---

### 8. 네비게이션 · UI 개선

| 항목 | 변경 내용 |
|------|----------|
| 네비게이션 텍스트 | 소개 / 스크리닝 시작 → **About / Screening** |
| 네비게이션 크기 | 높이 56px→64px, 로고 1.05rem→1.2rem, 링크 0.875rem→0.95rem |
| 종목 카드 hover | `translateY(-1px)` → `translateY(-3px)` + 진한 그림자 + 테두리 강조 |
| About 카드 hover | pipeline, indicator, grade, badge-explain, fg-simple, cta-section 전체 동일 hover 추가 |
| 배지 출처 표기 | `yfinance Ticker.calendar` 등 → `yfinance` 로 통일 |
| CTA 섹션 스타일 | 구분선 방식 → `about-section` 카드 스타일로 통일 (`section-label/title/desc` 공통 클래스 사용) |

---

## [2026-04-28] GitHub Actions 배치 자동화 + 빌드 오류 수정

### 1. GitHub Actions 워크플로우 2개 추가

**배경:** Render 무료 플랜은 비활성 15분 후 슬립. 서버 내 데몬 스레드(24h)도 슬립 시 소멸.
외부 cron으로 keepalive + 일일 배치를 보장해야 함.

| 파일 | 역할 |
|------|------|
| `.github/workflows/keepalive.yml` | 평일 장 시간대 10분, 그 외 14분 간격 `/health` ping |
| `.github/workflows/daily-batch.yml` | 매일 KST 07:00 서버 웨이크업 후 매크로·공포탐욕 강제 갱신 |

### 2. 갱신 전용 API 엔드포인트 추가 (`api/main.py`)

GitHub Actions가 Render 서버의 캐시를 강제 갱신할 수 있도록 보호된 엔드포인트 추가.

| 경로 | 역할 |
|------|------|
| `GET /api/refresh/macro` | FRED 매크로 데이터 강제 갱신 |
| `GET /api/refresh/fear-greed` | 공포탐욕지수 강제 갱신 |

`X-Refresh-Token` 헤더 검증 — GitHub Secret `REFRESH_TOKEN` 과 Render 환경변수 `REFRESH_TOKEN` 일치해야 허용.

**필요한 설정:**
- GitHub → Repository secrets: `RENDER_URL`, `REFRESH_TOKEN`
- Render → Environment Variables: `REFRESH_TOKEN`, `FRED_API_KEY`

### 3. `fredapi>=3.1.0` 제거 → Render 빌드 오류 해결

**원인:** `fredapi` 최신 버전은 `0.5.2`인데 `>=3.1.0` 명시 → 패키지 없음 → 빌드 실패.

**사실:** `macro_fetcher.py`는 이미 `fredapi`를 쓰지 않고 `requests`로 FRED REST API를 직접 호출 중. 의존성 자체가 불필요했음.

```diff
- fredapi>=3.1.0
+ # fredapi 제거 — macro_fetcher.py가 requests로 FRED REST API 직접 호출
```

---

## [2026-04-29] 매매시점 시그널 스코어링 시스템

### 구현 완료

**신규 파일:** `screener/signal_scorer.py`

기존 S/A/B/SKIP 체크리스트와 완전 독립된 7개 보조지표 기반 매매타이밍 채점.

| 지표 | 신호 조건 |
|------|----------|
| ATR 진입 존 | 현재가가 (MA20 − 0.5×ATR) ~ (MA20 + 0.5×ATR) 범위 내 |
| 거래대금 폭발 | 당일 거래대금 ≥ 직전 20일 평균 × 2배 |
| StochRSI | K선 과매도(≤20) 구간에서 상향 교차 |
| 볼린저밴드 %B | %B ≤ 0.2 (하단 밴드 근처) |
| OBV 다이버전스 | 가격 하락 + OBV 상승 (강세 다이버전스) |
| MA 크로스 | 일봉 MA20 > MA60 골든크로스 상태 |
| 캔들 패턴 | 최근 3봉 내 강세 패턴 (CandleKit, 실패 시 자동 스킵) |

등급: STRONG BUY (≥71%) / BUY (≥43%) / WATCH (≥1) / NO SIGNAL

**`screener/indicators.py` 확장:**

| 함수 | 설명 |
|------|------|
| `calc_atr_zones(df)` | ATR(14) 기반 진입 존 + 손절가 계산 |
| `calc_stoch_rsi(close)` | StochRSI(14,3,3) 과매도 반등 감지 |
| `calc_bb_advanced(df)` | 볼린저밴드 %B + 스퀴즈 감지 |
| `calc_obv_divergence(df)` | OBV vs 가격 강세 다이버전스 |
| `calc_ma_cross(df_d, df_h)` | 일봉/시간봉 MA 크로스 상태 |
| `calc_value_spike(df)` | 거래대금 급증 배수 계산 |

**`screener/data_fetcher.py` 확장:**
- `fetch_intraday(ticker, interval, period)` 추가 — 분봉 데이터 수집, 당일 캐싱

---

## [2026-04-30] Lightweight Charts 모달 + 마스터 시그널

### 구현 완료

**신규 파일:** `api/routes/chart.py`

| 항목 | 내용 |
|------|------|
| 엔드포인트 | `GET /api/chart-data/{ticker}` |
| 반환 | `ohlcv` (캔들), `ma20` (이동평균), `markers` (매수/매도 마커) |
| 캐시 재사용 | `data_fetcher._cache` 직접 접근 → 재요청 없음 |
| 캐시 미스 | ThreadPoolExecutor + 10초 타임아웃으로 yfinance 6mo 수집 |

**마스터 시그널 (`_compute_master_markers`):**

MA(추세) + RSI(눌림목) + 거래대금(수급) 3중 결합

| 조건 | 판단 |
|------|------|
| MA20 > MA60 AND 가격이 MA20±ATR 존 내 AND (RSI 반등 OR 거래대금 2배↑) | 매수 |
| 데드크로스 OR RSI 고점 하락(≥75→하락) OR ATR 손절(MA20−2×ATR 이탈) | 매도 |

포지션 상태 변수로 연속 도배 방지.

**카드 경량화 — compact + 모달 구조로 전면 교체:**

| 항목 | 변경 |
|------|------|
| `api/routes/screen.py` | `_tv_widget()` 삭제, compact 카드 + hidden `.card-detail` 분리 |
| `templates/base.html` | Lightweight Charts 4.2.0 CDN 추가 |
| `templates/screen.html` | 차트 모달 HTML 추가 (signal-select, show-buy/sell 체크박스) |
| `static/js/screen.js` | 모달 열기/닫기, fetchAndRenderChart, applyMarkers, ESC/외부클릭 핸들러 |
| `static/css/screen.css` | `.card-compact`, `.chart-btn`, `.modal-overlay`, `.modal-box` 등 스타일 추가 |
| `api/main.py` | chart router 등록 |

**성능 효과:** 20종목 스캔 시 Canvas 0개 (기존 TradingView 위젯 20개 → 0개), 버튼 클릭 시점에만 생성.

---

## [2026-04-30] 개발 환경 안정화

### 문제 및 해결

**근본 원인:** macOS iCloud Drive가 Desktop 폴더를 동기화하면서 `.venv` 내 패키지 파일들을 evict(로컬 삭제) → `fastapi/__init__.py` 등 읽기 불가 → 서버 기동 실패

| 증상 | 원인 | 해결 |
|------|------|------|
| 서버 `Started reloader process`에서 멈춤 | StatReload가 `.venv` 10,609개 파일 전체 스캔 | `watchfiles` 설치 → WatchFiles 리로더로 전환 |
| `pip._internal.cli.main` 오류 | iCloud eviction으로 pip 소스 파일 소멸 | ensurepip으로 pip 재설치 |
| 차트 무한 로딩 | StatReload 재시작 → 캐시 초기화 + yfinance 타임아웃 없음 | ThreadPoolExecutor 10초 타임아웃 |
| 임포트 실패 (`fastapi`, `uvicorn` 등) | iCloud가 `.venv` 파일 evict | `.venv`를 iCloud 밖(`~/fin_auto_venv`)으로 이전 + 심링크 |

**신규 파일:** `run.sh`

```bash
#!/bin/bash
lsof -ti :8000 | xargs kill -9 2>/dev/null
~/fin_auto_venv/bin/python -m uvicorn api.main:app --reload --port 8000 \
  --reload-dir api --reload-dir screener --reload-dir services \
  --reload-dir static --reload-dir templates
```

`.venv` 구조:
- 실체: `~/fin_auto_venv` (iCloud 미동기화 홈 디렉토리)
- 심링크: `Desktop/fin_auto/.venv` → `~/fin_auto_venv`

**`screener/macro_fetcher.py` 성능 개선:**
- FRED 5개 시리즈 순차 → `ThreadPoolExecutor(max_workers=5)` 병렬 (~50s → ~10s)
- `get_macro_context()` 비차단 — 백그라운드 스레드 실행 후 캐시 즉시 반환
- `threading.Lock` 으로 이중 실행 방지

---

---

## [2026-05-01] 시그널 채점 로직 고도화 6종 (Phase Signal QA)

### 배경

Phase 0~6에서 구현된 4카테고리 채점 로직을 코드 리뷰 후 6가지 구조적 문제 발견.
실제 STRONG BUY가 거의 발생하지 않고, 지표 강도 정보가 소실되는 문제를 수정.

### 수정 내용

**1. MA 이벤트 감지 → 현재 정배열 상태 (`screener/indicators.py`)**
- `calc_ma_cross` (lookback 20봉 내 크로스 이벤트) → `calc_ma_alignment` (현재 MA20 > MA60 여부)
- 21일 전 골든크로스가 있어도 이벤트 기반 감지는 `"none"` 반환하던 문제 해결
- 반환값: `"bullish"` / `"bearish"` / `"none"`

**2. ATR 진입존 anchor 교체 (`screener/indicators.py`)**
- 기존: `MA20 ± ATR` 중심 → 골든크로스(MA20 상승) 시 가격이 존 위에 있어 `atr_ok=False`
- 변경: `entry_low = MA60`, `entry_high = MA20 + 0.5*ATR`
- 이제 MA 정배열 + 가격이 두 선 사이 = 공존 가능한 눌림 진입 구간
- 역배열(MA20 < MA60)이면 entry_low > entry_high → 자동으로 빈 구간(atr_ok=False)

**3. STRONG BUY 임계값 조정 (`screener/signal_scorer.py`)**
- 기존 0.70 → 변경 0.60 (trend=1.0 + momentum=1.0 = 0.35+0.25 = 0.60으로 도달 가능)
- BUY: 0.45 → 0.40

**4. 지표 강도 이진화 제거 (`screener/signal_scorer.py`)**
- StochRSI: `k < 0.3` 조건 bool → `(0.3 - k) / 0.3` 연속값 (k=0 → 1.0, k=0.29 → 0.03)
- BB %B: `pct_b < 0.20` bool → `(0.20 - pct_b) / 0.20` 연속값
- 거래대금: `ratio >= 2.0` bool → `min((ratio - 1.0) / 1.0, 1.0)` 연속값 (1x→0, 2x→1.0)
- `_cat_score(bool, bool)` → `_cat_score(float, float)` 타입 변경

**5. OBV 다이버전스 감지 개선 (`screener/indicators.py`)**
- 기존: 세그먼트 min/max 단순 비교 → 일시적 급락 하나가 결과 뒤집는 문제
- 변경: OBV_MA10 vs OBV_MA30 정배열 상태 (빠른 MA > 느린 MA = 수급 상승 추세)

**6. Pattern Score 이진 처리 제거 (`screener/signal_scorer.py`)**
- 기존: `1.0 if patterns else 0.0` (1개나 11개나 동일)
- 변경: `min(len(patterns) / 2.0, 1.0)` (2개 이상 = 1.0)

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `screener/indicators.py` | `calc_ma_alignment` 추가 (calc_ma_cross alias 유지), `calc_atr_zones` anchor 교체, `calc_obv_divergence` MA 방식으로 교체 |
| `screener/signal_scorer.py` | import 교체, 조건식 업데이트, 강도값 연속화, 임계값 조정 |
| `tests/test_indicators.py` | `calc_atr_zones` 빈 구간(역배열) 테스트 어서션 주석 업데이트 |

---

## [2026-05-01] 스크리닝·매매시그널 서비스 분리 완료 (Phase 0~6)

### 배경

현재 `screener_service.py` 한 파일이 스크리닝(7개 체크리스트)과 매매시그널(4카테고리)을 동시에 처리한다.
이로 인해 시그널만 보고 싶어도 스크리닝 전체를 실행해야 하고, 스크리닝을 통과하지 못한 종목은 시그널 채점 자체가 불가능했다.

**결정:** 두 서비스를 완전히 독립된 페이지·파이프라인으로 분리한다.

### 서비스 정의 확정

| 서비스 | URL | 핵심 질문 | 지표 |
|--------|-----|---------|------|
| 스크리닝 | `/screen` | 이 종목이 기술적으로 건강한가? | MA/RSI/MACD/BB/HH+HL |
| 매매시그널 | `/signals` | 지금 진입 타이밍인가? | ATR/StochRSI/BB%B/OBV/거래대금/캔들 |

### 아키텍처 결정

| 항목 | 결정 |
|------|------|
| Watchlist 저장 | JSON 파일 (`data/watchlist.json`), 추후 DB 연동 가능 |
| 시그널 실행 방식 | 페이지 접속 시 자동 실행 (SSE 스트리밍) |
| 스크리닝 → 시그널 연결 | 카드별 ★ 버튼으로 개별 추가 |
| 시그널 단독 사용 | 허용 (티커 직접 입력 가능) |

### 구현 Phase 목록

| Phase | 내용 | 신규 파일 |
|-------|------|---------|
| Phase 0 | 기존 코드 정리 (signal 블록 제거) | — |
| Phase 1 | Watchlist JSON 저장소 | `screener/watchlist_store.py` |
| Phase 2 | Watchlist REST API | `api/routes/watchlist.py` |
| Phase 3 | 시그널 서비스 백엔드 | `services/signal_service.py` |
| Phase 4 | 시그널 페이지 API + SSE | `api/routes/signals.py` |
| Phase 5 | 시그널 프론트엔드 | `templates/signals.html`, `static/js/signals.js`, `static/css/signals.css` |
| Phase 6 | 스크리닝 → 시그널 브리지 | `api/routes/screen.py` (★ 버튼), `static/js/screen.js` (핸들러), `static/css/screen.css` |

**Phase 6 상세 — 스크리닝 카드 Watchlist 브리지:**
- 카드 헤더 `card-compact-actions` 래퍼에 `★` 버튼 추가 (non-SKIP 카드만)
- 이미 추가된 종목 → 노란색 표시 (`wl-added`)
- 페이지 로드 시 현재 Watchlist 조회 → 버튼 상태 초기화

---

## [2026-05-02] 매매시그널 품질 고도화 2 — 아키텍처 분리 + 지표 재설계

> 상세 이력: `docs/phases/phase-signal-quality-2.md`

### 배경

4개 카테고리 점수(trend/momentum/volume/pattern)가 비슷한 숫자에 집중되는 현상과
차트 마커의 신뢰성 문제(매수 후 하락, 매도 후 상승)를 진단·수정한 Phase.

진단 결과:
- **모멘텀 ≈ 0**: StochRSI < 0.3(과매도)이 trend(상승 추세)와 상호 배타적 — 동시 만족 불가
- **수급 ≈ 0.25**: 거래대금 2배 spike는 발화 빈도 낮아 volume_score가 0.25에 고착
- **마커 노이즈**: 상태 머신이 데드크로스 유지 기간 동안 매도 마커를 연속 표시

### 1. 차트 마커 아키텍처 분리 (ADR-017)

**신규 파일 2개:**

| 파일 | 역할 |
|------|------|
| `screener/buy_signal.py` | numpy 벡터 연산 기반 매수 조건 엔진 |
| `screener/sell_signal.py` | 전환(transition) 이벤트 기반 매도 조건 엔진 |

**`api/routes/chart.py`:**
- `_compute_master_markers()` (85줄 상태 머신) 완전 삭제
- `_merge_markers(df)` (6줄 병합 함수)로 교체

**매수 조건** (`buy_signal.py`):
```python
# 상승 추세 + 진입존 + (RSI 모멘텀 회복 OR 거래대금 2배↑ + 양봉)
rsi_mom = (rsi >= 40) & (rsi <= 60) & (rsi > rsi_prev) & (rsi_prev > rsi_prev2)
vol_spk = (value / avg_value >= 2.0) & is_bull
buy_cond = valid & uptrend & in_zone & (rsi_mom | vol_spk)
```

**매도 조건** (`sell_signal.py`) — 3종 전환 이벤트:
```python
dead_cross  = (m20 < m60) & (m20_prev >= m60_prev)        # 교차 당일만
rsi_exit    = (rsi_prev2 >= 70) & (rsi_prev < rsi_prev2) & (rsi < rsi_prev)
ma20_break  = (c < m20) & (c_prev >= m20_prev) & is_bear & vol_up
```

### 2. 모멘텀 점수 재설계 — RSI 종형 곡선 (ADR-019)

기존 StochRSI/BB%B 과매도 기반 → **RSI 45~65 건강한 상승 구간** 중심으로 전환.

```
RSI 55 → 1.0 (최고점)
RSI 45/65 → 0.0
RSI 35~45 → 0.0~0.6 (눌림목 회복 중)
RSI 65~75 → 0.4~0.0 (과매수 경계)
```

**보조 보너스 (강한 쪽만 채택, 이중 계산 방지):**
- StochRSI 방향 보너스: k_prev < 0.35 구간에서 k 상승 중 → 최대 +0.30
- Z-Score 보너스: 2σ 이하 통계적 과매도 → +0.30, 1~2σ → +0.15

### 3. 수급 지표 교체 — CMF 도입 (ADR-018)

거래대금 spike(`calc_value_spike`) → **CMF 21봉** 교체.

| 지표 | 범위 | 발화 빈도 |
|------|------|---------|
| 거래대금 spike | 0~1 (이벤트성) | 낮음 (2배↑ 조건) |
| CMF | −1~+1 (연속값) | 높음 (매일 계산) |

```python
cmf_intensity = min(cmf_val / 0.15, 1.0) if cmf_val > 0 else 0.0
volume_score  = (cmf_intensity + obv_intensity) / 2
```

### 4. LiquiditySweep 패턴 추가 (`signal_scorer.py`)

직전 20봉 최저가(liquidity pool) 장중 이탈 후 종가 회복 = 기관 매집 신호.

가중치: LiquiditySweep = **1.5단위** (일반 패턴은 1.0단위), 2단위 이상 = 1.0.

### 5. Z-Score 모멘텀 보너스 추가 (`signal_scorer.py`)

통계적 과매도 검증 — StochRSI 보너스와 `max()` 로 교차 검증:
```python
z = (close[-1] - mean_20) / std_20
z_bonus = 0.30 if z < -2.0 else 0.15 if z < -1.0 else 0.0
```

### 6. 차트 마커 호버 툴팁 (`signals.js` + `signals.css`)

LWC v4 `subscribeCrosshairMove` 이용, 마커 위 커서 시 이유·날짜·가격 표시.  
`_timeToStr()` 헬퍼: LWC v4 `{year, month, day}` BusinessDay 객체 → `"YYYY-MM-DD"` 변환.

### 변경 파일

| 파일 | 상태 | 변경 내용 |
|------|------|---------|
| `screener/buy_signal.py` | 신규 | 매수 신호 엔진 |
| `screener/sell_signal.py` | 신규 | 매도 신호 엔진 |
| `api/routes/chart.py` | 변경 | 상태 머신 → `_merge_markers()` |
| `screener/indicators.py` | 변경 | `calc_cmf()` 신규, `calc_stoch_rsi` k_prev/rsi 추가, `calc_ma_alignment` ma20/ma60 값 반환 |
| `screener/signal_scorer.py` | 변경 | RSI 종형 모멘텀, CMF 수급, LiquiditySweep, Z-Score |
| `templates/signals.html` | 변경 | `#marker-tooltip` div 추가 |
| `static/css/signals.css` | 변경 | `.marker-tooltip`, `.type-buy/.type-sell` 스타일 |
| `static/js/signals.js` | 변경 | `_timeToStr()`, `subscribeCrosshairMove` 툴팁 |

---

## 미구현 / 계획 중

| 기능 | 우선순위 | 비고 |
|------|---------|------|
| AVWAP (Anchored VWAP) | 중간 | 앵커 기준점 자동 선택 알고리즘 복잡도 높음 — 별도 Phase |
| 텔레그램 알림 | 낮음 | S급 종목 알림 (batch_scheduler 통합) |
| 백테스팅 엔진 | 낮음 | 과거 신호 재현 → 승률/MDD 계산 |
| Render 배포 | 중간 | render.yaml 존재, 환경변수 설정 필요 |
| VIX yfinance fallback | 낮음 | FRED VIXCLS 지연 시 `^VIX` fallback |
