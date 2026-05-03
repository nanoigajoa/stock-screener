# Architecture — fin_auto (2026-05-01 v3 — 스크리닝·매매시그널 서비스 분리 완료)

## 전체 시스템 구성

```
브라우저
  │  GET /              → about.html  (기본 진입 페이지)
  │  GET /screen        → screen.html (스크리닝)
  │  GET /signals       → signals.html (매매시그널)
  │  GET /about         → about.html
  │  GET /stream/screen → SSE 스트림 (스크리닝)
  │  GET /stream/signals→ SSE 스트림 (시그널)
  │
  ▼
FastAPI (api/main.py)
  │
  ├─ StaticFiles /static → static/css/, static/js/
  ├─ Jinja2Templates     → templates/
  ├─ Jinja2 filter: ago(dt) → "방금 전 / N분 전 / N시간 전 / MM/DD"
  │
  ├─ on_startup:
  │    └─ batch_scheduler.start()   # 데몬 스레드 (실시간 터미널 게이지 포함)
  │         ├─ macro_fetcher.refresh_macro()    # FRED REST API, TTL 7일
  │         └─ fear_greed_fetcher.get_fear_greed()  # VIX+SPY 자체 계산, TTL 6h
  │
  ├─ GET /stream/screen (SSE)  ──────────────────────────┐
  │       └─ run_analysis() [screener_service.py]        │
  │                                                      ▼
  │   스크리닝 파이프라인:                         카드 HTML 렌더링
  │     1. get_filtered_tickers()   Finviz 사전 필터
  │     2. fetch_ohlcv()            yfinance OHLCV, TTL 당일
  │     3. get_today_changes()      당일 변동률 필터
  │     4. check_news_risk()        뉴스 리스크 필터
  │     5. calculate_indicators()   MA/RSI/MACD/BB/Volume
  │     6. score_ticker()           7개 체크리스트 채점
  │     7. grade()                  비율 기반 S/A/B/SKIP
  │     8. extras 병렬 조회 (x4):
  │          fetch_fundamentals() / get_trend_scores()
  │          get_congress_trades() / get_insider_buys()
  │
  └─ GET /stream/signals (SSE) ───────────────────────────┐
          └─ run_signal_analysis() [signal_service.py]   │
                                                         ▼
      시그널 파이프라인:                          시그널 카드 HTML
        1. watchlist_store.load()     Watchlist 로드
        2. fetch_ohlcv(daily)         일봉 데이터
        3. fetch_intraday(1h)         시간봉 데이터 (병렬)
        4. score_signals()            4카테고리 가중 채점
        5. STRONG BUY 순 정렬
```

---

## 두 서비스 비교

| 항목 | 스크리닝 `/screen` | 매매시그널 `/signals` |
|------|:---:|:---:|
| 핵심 질문 | 이 종목이 기술적으로 건강한가? | 지금 진입 타이밍인가? |
| 사용 주기 | 주 2~3회 (개장 전) | 매일 (장 시작 전/중) |
| 입력 | Finviz 필터 또는 수동 | Watchlist (스크리닝 연동 또는 직접) |
| 지표 | MA/RSI/MACD/BB/Volume/HH+HL | ATR/StochRSI/BB%B/OBV/거래대금/캔들 |
| 출력 | S/A/B/SKIP + 체크리스트 | STRONG BUY / BUY / WATCH / NO SIGNAL |
| 실행 방식 | 수동 폼 제출 | 페이지 접속 시 자동 (SSE) |

---

## 디렉토리 구조

```
fin_auto/
│
├── config.py                    # 전역 상수 + 환경변수
├── requirements.txt
├── .env                         # API 키 (git 제외)
├── run.sh                       # 서버 실행 스크립트
│
├── api/
│   ├── main.py                  # FastAPI 앱 + 라우터 등록 + 배치 스케줄러 시작
│   └── routes/
│       ├── screen.py            # /stream/screen (SSE), /health
│       ├── chart.py             # /api/chart-data/{ticker}
│       ├── tickers.py           # /api/tickers 자동완성
│       ├── watchlist.py         # /api/watchlist CRUD
│       └── signals.py           # /signals 페이지 + /stream/signals SSE
│
├── services/
│   ├── screener_service.py      # run_analysis() — 스크리닝 오케스트레이터
│   └── signal_service.py        # run_signal_analysis() — 시그널 오케스트레이터
│
├── screener/
│   ├── finviz_filter.py         # Finviz 필터 → 티커 리스트
│   ├── data_fetcher.py          # yfinance OHLCV + 시간봉 수집, TTL 캐시
│   ├── indicators.py            # MA/RSI/MACD/BB + ATR/StochRSI/BB%B/OBV 등
│   ├── checklist.py             # 7개 항목 채점 (enabled_checks, max_score)
│   ├── grader.py                # 비율 기반 S/A/B/SKIP 등급
│   ├── news_filter.py           # 뉴스 리스크 필터
│   ├── signal_scorer.py         # 4카테고리 가중 시그널 채점 (trend/momentum/volume/pattern)
│   ├── buy_signal.py            # 차트 마커용 매수 신호 엔진 (numpy 벡터 연산)
│   ├── sell_signal.py           # 차트 마커용 매도 신호 엔진 (전환 이벤트 방식)
│   ├── watchlist_store.py       # Watchlist JSON 저장/로드 (threading.Lock)
│   ├── fundamental_fetcher.py   # yfinance: 실적일, 숏비율, 목표가
│   ├── trends_fetcher.py        # pytrends: Google 관심도 (TTL 24h)
│   ├── macro_fetcher.py         # FRED REST API: 매크로 지표 (TTL 7일)
│   ├── congress_fetcher.py      # quiverquant: 의원 거래 (TTL 24h)
│   ├── insider_fetcher.py       # yfinance insider: 내부자 매수 (TTL 24h)
│   └── batch_scheduler.py       # 데몬 스레드 배치 (macro + congress)
│
├── data/
│   └── watchlist.json           # Watchlist 영구 저장 (git 제외)
│
├── static/
│   ├── css/
│   │   ├── base.css             # 전역 스타일 + 네비게이션 (CSS 변수 다크 테마)
│   │   ├── screen.css           # 스크리너 페이지 전용
│   │   ├── about.css            # About 페이지 전용
│   │   └── signals.css          # 시그널 페이지 전용
│   └── js/
│       ├── screen.js            # TomSelect + SSE + 차트 모달 + Watchlist 브리지
│       └── signals.js           # Watchlist 태그 + SSE + 필터 + 차트 모달
│
├── templates/
│   ├── base.html                # 레이아웃 (네비게이션, CSS/JS 블록)
│   ├── screen.html              # 스크리닝 메인 + 매크로 배너
│   ├── signals.html             # 시그널 대시보드 (Watchlist 패널 + 필터 + 카드)
│   └── about.html               # 시스템 설명 (초보자용)
│
└── docs/
    ├── design_doc.md
    ├── architecture.md           # 이 파일
    ├── changelog.md
    ├── adr/                      # ADR-001 ~ ADR-016
    ├── skills/                   # 핵심 구현 스킬 레퍼런스
    └── phases/
        ├── phase-service-split.md  # Phase 0~6 구현 이력
        └── phase-future.md         # 미구현 기능 계획
```

---

## 데이터 캐시 전략

| 모듈 | 캐시 방식 | TTL | 키 |
|------|---------|-----|---|
| `data_fetcher` | dict | 당일 (date) | `(ticker, period)` |
| `fundamental_fetcher` | dict | 당일 (date) | `(ticker, date)` |
| `trends_fetcher` | dict + datetime | 24h | `ticker` |
| `macro_fetcher` | dict + datetime | 7일 | `"macro"` |
| `congress_fetcher` | list + datetime | 24h | 전체 목록 1개 |
| `insider_fetcher` | dict + datetime | 24h | `ticker` |

---

## 등급 계산 (비율 기반)

```python
_GRADE_RATIOS = [("S", 0.67), ("A", 0.44), ("B", 0.22)]

ratio = score / max_score  # max_score = 활성화된 항목 weight 합계
# 전체 9점 기준: S ≥ 6.03, A ≥ 3.96, B ≥ 1.98
```

체크리스트 항목 일부를 비활성화해도 등급 기준이 자동으로 조정됨.

---

## 시그널 채점 (4카테고리)

| 카테고리 | 가중치 | 세부 지표 | 점수 방식 |
|---------|:---:|---------|---------|
| Trend (추세) | 35% | MA 정배열(MA20>MA60) + 가격이 진입존(MA60~MA20+0.5ATR) 안 | 0/1 구조 조건 |
| Momentum (모멘텀) | 25% | StochRSI k<0.3 강도 + BB %B<0.20 강도 | 연속값 강도 |
| Volume (수급) | 25% | OBV_MA10>OBV_MA30 정배열 + 거래대금 급증 강도(1x→0, 2x→1.0) | 연속값 강도 |
| Pattern (캔들) | 15% | 최근 3봉 내 강세 캔들 패턴 수 (2개 이상 = 1.0) | 수 기반 정규화 |

등급 임계값: STRONG BUY ≥ 0.60 / BUY ≥ 0.40 / WATCH ≥ 0.20 / NO SIGNAL

> **설계 원칙:** Trend는 "맞는 구조인가" (0/1), Momentum·Volume은 "얼마나 강한가" (연속값).
> trend=1.0 + momentum=1.0 → 총점 0.60 = STRONG BUY 도달 가능.

---

## 체크리스트 항목 (7개)

| 키 | 이름 | Weight |
|----|------|--------|
| `ma_alignment` | MA 정배열 (price > 5>20>60>120MA) | 2 |
| `rsi` | RSI 45~65 (hard gate: ≥80 → SKIP) | 2 |
| `volume` | 거래량 > 평균 1.5배 | 1 |
| `macd` | MACD 골든크로스 | 1 |
| `support` | 지지선 위 반등 | 1 |
| `bollinger` | 볼린저밴드 중간선 위 | 1 |
| `trend` | Higher High + Higher Low | 1 |

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | About 페이지 (기본 진입) |
| GET | `/screen` | 스크리닝 메인 페이지 |
| GET | `/signals` | 매매시그널 대시보드 (Phase 5+) |
| GET | `/about` | About 페이지 |
| GET | `/health` | 헬스체크 |
| GET | `/stream/screen` | SSE 스크리닝 스트림 |
| GET | `/stream/signals` | SSE 시그널 스트림 |
| GET | `/api/tickers` | 티커 자동완성 검색 |
| GET | `/api/chart-data/{ticker}` | 캔들 + MA + 마커 데이터 |
| GET | `/api/watchlist` | Watchlist 조회 |
| POST | `/api/watchlist/{ticker}` | Watchlist 추가 |
| DELETE | `/api/watchlist/{ticker}` | Watchlist 삭제 |
| DELETE | `/api/watchlist` | Watchlist 전체 초기화 |
| GET | `/api/refresh/macro` | FRED 매크로 강제 갱신 |
| GET | `/api/refresh/fear-greed` | 공포탐욕지수 강제 갱신 |

---

## 환경변수

| 변수 | 필수 | 용도 |
|------|------|------|
| `FRED_API_KEY` | 권장 | FRED 매크로 배너 (없으면 배너 숨김) |
| `QUIVERQUANT_API_KEY` | 선택 | 의원거래 배지 (유료, 없으면 스킵) |
| `REFRESH_TOKEN` | 선택 | GitHub Actions 캐시 강제 갱신 인증 |
| `TELEGRAM_BOT_TOKEN` | 선택 | 텔레그램 알림 (미구현) |
| `KAKAO_ACCESS_TOKEN` | 선택 | 카카오 알림 (미구현) |

---

## 실행 방법

```bash
# 웹앱 실행 (권장)
./run.sh

# 직접 실행
uvicorn api.main:app --reload --port 8000
```
