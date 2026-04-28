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

## 미구현 / 계획 중

→ 상세 내용: [docs/phases/phase-future.md](phases/phase-future.md)

| 기능 | 우선순위 | 비고 |
|------|---------|------|
| 목표가·손절 비율 커스터마이징 | 높음 | 사용자 입력 → `target_1_pct`, `stop_loss_pct` 동적 계산 |
| 백테스팅 엔진 | 중간 | 과거 신호 재현 → 승률/MDD 계산 |
| 텔레그램 알림 (Phase 2) | 낮음 | S급 종목 알림 |
| Render 배포 | 중간 | 환경변수 설정 필요 |
| VIX 데이터 복구 | 낮음 | FRED VIXCLS 시리즈 None 반환 이슈 |
