# StockScope 구현 계획서

> **최종 업데이트:** 2026-04-28  
> 이 문서는 원래 plan mode에서 작성된 계획(`zippy-marinating-phoenix.md`)을 실제 구현 결과 기준으로 정리한 것입니다. 계획과 달라진 아키텍처 결정은 각 ADR 문서를 참조하세요.

---

## 전체 구현 상태

| 계획 | 상태 | 비고 |
|------|------|------|
| 웹앱 전환 (FastAPI + SSE) | ✅ 완료 | Celery → SSE로 변경 (ADR-013) |
| 프론트엔드 대개편 | ✅ 완료 | CSS/JS 분리, About 페이지, 네비게이션 |
| 사용자 커스터마이징 3종 | ✅ 완료 | 기간·RSI·체크리스트 |
| yfinance 펀더멘털 배지 4종 | ✅ 완료 | 실적·숏비율·목표가·내부자 |
| 외부 데이터소스 4종 통합 | ✅ 완료 | Trends·FRED·Congress·SEC Form4 |
| GitHub Actions (keepalive + batch) | ✅ 완료 | Render 슬립 방지 + KST 07:00 배치 |

---

## Phase 1 — 웹앱 전환 ✅

### 원래 계획 vs 실제 구현

| 항목 | 원래 계획 | 실제 구현 | ADR |
|------|-----------|-----------|-----|
| 비동기 처리 | Celery + Redis + HTMX 폴링 | FastAPI SSE + EventSource | ADR-013 |
| 프론트엔드 | HTMX | Vanilla JS EventSource | ADR-013 |
| 외부 브로커 | Redis | 없음 (SSE는 브로커 불필요) | ADR-013 |
| 도커 | docker-compose.yml | 사용 안 함, Homebrew | ADR-012 |

### SSE 스트리밍 아키텍처 (현재)

```
클라이언트 (EventSource)
  → GET /stream/screen?tickers=...&period=...
    → generate() 코루틴 (FastAPI StreamingResponse)
      → run_analysis()  ← screener_service.py
        → finviz_filter  → yfinance OHLCV → indicators → checklist → grader
        → fetch_fundamentals (ThreadPoolExecutor)
        → get_trend_scores / get_congress_trades / get_insider_buys (병렬)
      → yield SSE events (progress / result / done / error)
  ← 브라우저 카드 실시간 렌더링
```

### 핵심 파일

| 파일 | 역할 |
|------|------|
| `api/main.py` | FastAPI 앱, startup 훅, refresh 엔드포인트, `/health` |
| `api/routes/screen.py` | SSE 스트리밍, `_render_all_indicators()` 카드 렌더링 |
| `api/routes/tickers.py` | 티커 자동완성 |
| `services/screener_service.py` | `run_analysis()` — CLI·웹 공용 |
| `static/js/screen.js` | EventSource 핸들러, TomSelect, TradingView |

---

## Phase 2 — 프론트엔드 대개편 ✅

### 디렉토리 구조 (현재)

```
fin_auto/
├── static/
│   ├── css/
│   │   ├── base.css        # 전역 스타일 + 네비게이션
│   │   ├── screen.css      # 스크리너 전용 (카드, 배지, 인디케이터)
│   │   └── about.css       # About 페이지 전용
│   └── js/
│       └── screen.js       # EventSource, TomSelect, TradingView
├── templates/
│   ├── base.html           # 네비게이션 포함 베이스 (active_page 변수)
│   ├── about.html          # 기본 진입 페이지 (/ 라우트)
│   └── screen.html         # 스크리너 대시보드 (/screen 라우트)
```

### 라우트 구조

| URL | 핸들러 | 설명 |
|-----|--------|------|
| `GET /` | `about()` | About 페이지 (기본 진입) |
| `GET /screen` | `screen()` | 스크리너 대시보드 |
| `GET /stream/screen` | `stream_screen()` | SSE 스트리밍 |
| `GET /about` | `about()` | About 페이지 |
| `GET /health` | — | Render keepalive 헬스체크 |
| `GET /api/refresh/macro` | — | GitHub Actions 배치 트리거 |
| `GET /api/refresh/fear-greed` | — | GitHub Actions 배치 트리거 |

### About 페이지 섹션

1. Hero — "감이 아닌 데이터로 진입 타이밍을 잡는 미국 주식 스크리너"
2. 데이터 파이프라인 시각화 (Finviz → yfinance → 지표 → 등급)
3. 7개 체크리스트 지표 카드
4. S/A/B/SKIP 등급 기준표
5. 펀더멘털 배지 설명 (출처: yfinance)
6. 공포·탐욕 지수 설명 (SPY 모멘텀 근사, 면책 표시)
7. CTA 섹션 → 스크리너로 이동

---

## Phase 3 — 사용자 커스터마이징 ✅

### 구현된 옵션

| 옵션 | UI | 파라미터 | 기본값 |
|------|----|---------|--------|
| 데이터 기간 | 드롭다운 (3mo/6mo/1yr) | `period` | `6mo` |
| RSI 범위 | min/max 숫자 입력 | `rsi_min`, `rsi_max` | 45 / 65 |
| 체크리스트 항목 | 7개 체크박스 | `checks` | 전체 |

### 등급 비율 기반 산출

체크 항목 비활성화 시 `max_score`가 줄어드므로 비율로 계산:

```python
_GRADE_RATIOS = [("S", 0.67), ("A", 0.44), ("B", 0.22)]
# 전체 활성(max_score=9): S≥6.03, A≥3.96, B≥1.98
# RSI 제외(max_score=7): S≥4.69, A≥3.08, B≥1.54
```

---

## Phase 4 — 펀더멘털 배지 4종 ✅

### `screener/fundamental_fetcher.py`

| 데이터 | 소스 | 조건 | 배지 색상 |
|--------|------|------|---------|
| 실적 발표일 | `yf.Ticker().calendar` | 0~7일 | 빨간 |
| 실적 발표일 | `yf.Ticker().calendar` | 8~14일 | 노란 |
| Short Ratio | `info['shortRatio']` | ≥ 5 | 파란 |
| 애널리스트 목표가 | `info['targetMeanPrice']` | 항상 표시 | 초록 |
| 내부자 매수 | `insider_fetcher` (SEC Form 4) | 90일 내 매수 | 금색 |

### 카드 인디케이터 표시 방식

`_render_all_indicators()` — 조건 충족 여부에 관계없이 **모든 지표 항상 표시**:
- `sig-ok` (초록): 조건 충족
- `sig-bad` (빨간): 조건 미충족
- `sig-warn` (노란): 경고 (실적 D-7~14)
- `sig-dim` (회색): 데이터 있으나 기준 미달
- `sig-na` (흐린 회색): 데이터 없음

---

## Phase 5 — 외부 데이터소스 4종 ✅

### 소스별 상세

| 소스 | 파일 | 방식 | TTL | API 키 |
|------|------|------|-----|--------|
| Google Trends | `trends_fetcher.py` | Lazy, 5개씩 묶음 | 24h | 불필요 |
| FRED 매크로 | `macro_fetcher.py` | Startup + requests 직접 호출 | 7일 | 필요 (무료) |
| 의원 거래 | `congress_fetcher.py` | Startup + 메모리 필터링 | 24h | 필요 (무료) |
| SEC Form 4 | `insider_fetcher.py` | Lazy per-ticker | 24h | 불필요 |
| 공포·탐욕 | `fear_greed_fetcher.py` | Startup + SPY 4mo 모멘텀 | 24h | 불필요 |

> **주의:** 원래 계획의 `fredapi>=3.1.0`은 존재하지 않는 버전 (`fredapi` 최신 = 0.5.2).  
> FRED 데이터는 `fredapi` 라이브러리 없이 `requests`로 FRED REST API 직접 호출.  
> 관련 수정: `requirements.txt`에서 `fredapi` 제거.

### FRED 수집 지표

| Series ID | 지표 | 비고 |
|-----------|------|------|
| `FEDFUNDS` | 기준금리 | |
| `CPIAUCSL` | CPI (YoY % 계산) | 500 에러 재시도 로직 적용 |
| `UNRATE` | 실업률 | 500 에러 재시도 로직 적용 |
| `T10Y2Y` | 장단기 금리차 | 경기침체 선행지표 |
| `VIXCLS` | VIX | |

### `batch_scheduler.py` — 실시간 진행 게이지

서버 시작 시 stdout에 타임 게이지 출력:
```
○ [매크로(FRED)] ████░░░░ 2.0s / ~8s (25%)
✔ [매크로(FRED)] ██████████ 7.3s / ~8s (완료)
```
0.25초 간격 업데이트, 완료 시 `✔`로 교체.

---

## Phase 6 — GitHub Actions + Render 배포 ✅

### 워크플로우

| 파일 | 트리거 | 역할 |
|------|--------|------|
| `.github/workflows/keepalive.yml` | `*/10 12-21 * * 1-5` (UTC) | Render 슬립 방지 ping |
| `.github/workflows/daily-batch.yml` | `0 22 * * 0-4` (UTC = KST 07:00) | 매크로·공포탐욕 refresh |

### 필요한 GitHub Repository Secrets

| Secret | 값 |
|--------|----|
| `RENDER_URL` | `https://your-app.onrender.com` |
| `REFRESH_TOKEN` | Render Environment에 설정한 동일 토큰 |

### REFRESH_TOKEN 생성

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
→ GitHub Secrets + Render Environment Variables에 동일 값 설정.

---

## 미래 계획 (미구현)

`docs/phases/phase-future.md` 참조.

가능한 다음 단계:
- 포트폴리오 추적 기능 (보유 종목 watchlist)
- 백테스팅 (`backtest.py`)
- 알림 연동 (Telegram / 카카오)
- 모바일 최적화 (375px 이하 레이아웃)

---

## 관련 문서

| 문서 | 내용 |
|------|------|
| `docs/architecture.md` | 현재 시스템 아키텍처 다이어그램 |
| `docs/changelog.md` | 버전별 변경 이력 |
| `docs/adr/ADR-013-sse-over-celery.md` | SSE 채택 결정 근거 |
| `docs/adr/ADR-015-external-data-sources.md` | 외부 소스 4종 결정 |
| `docs/adr/ADR-016-ttl-memory-cache.md` | TTL 캐시 패턴 |
| `README.md` | 실행 방법, 환경 변수, 설치 가이드 |
