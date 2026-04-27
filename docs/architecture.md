# Architecture — fin_auto (현재 상태 기준 2026-04-28 v2)

## 전체 시스템 구성

```
브라우저
  │  GET /              → about.html  (기본 진입 페이지)
  │  GET /screen        → screen.html (스크리닝)
  │  GET /about         → about.html
  │  GET /stream/screen → SSE 스트림
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
  └─ GET /stream/screen (SSE)
       │
       ▼
  ThreadPoolExecutor (main executor)
       │
       ▼
  run_analysis() [services/screener_service.py]
       │
       ├─ 1. get_filtered_tickers()   # Finviz 사전 필터
       ├─ 2. fetch_ohlcv()            # yfinance OHLCV, TTL 당일
       ├─ 3. get_today_changes()      # 당일 변동률 필터
       ├─ 4. check_news_risk()        # 뉴스 리스크 필터
       ├─ 5. calculate_indicators()   # MA/RSI/MACD/BB/Volume
       ├─ 6. score_ticker()           # 7개 체크리스트 채점 (enabled_checks)
       ├─ 7. grade()                  # 비율 기반 S/A/B/SKIP
       │
       └─ 8. extras 병렬 조회 (ThreadPoolExecutor x4):
            ├─ fetch_fundamentals()   # yfinance: 실적일/숏비율/목표가/내부자
            ├─ get_trend_scores()     # pytrends: Google 관심도 (TTL 24h)
            ├─ get_congress_trades()  # 파일 기반: data/congress_trades.json
            └─ get_insider_buys()    # yfinance insider_purchases (TTL 24h)

카드 렌더링 (_render_all_indicators):
  → 7개 지표 항상 전체 표시 (조건 충족 여부 = 색상만 다름)
  → 뉴스 / 내부자매수 / 의원매수 / 구글관심 / 실적 / 숏비율 / 목표가
```

---

## 디렉토리 구조 (전체)

```
fin_auto/
│
├── main.py                      # CLI 진입점 (argparse)
├── config.py                    # 전역 상수 + 환경변수
├── requirements.txt
├── .env                         # API 키 (git 제외)
│
├── api/
│   ├── main.py                  # FastAPI 앱 + 라우터 등록 + 배치 스케줄러 시작
│   └── routes/
│       ├── screen.py            # /stream/screen (SSE), /health
│       └── tickers.py           # 기타 티커 관련 라우트
│
├── services/
│   └── screener_service.py      # run_analysis() — CLI·웹 공용 코어
│
├── screener/
│   ├── finviz_filter.py         # Finviz 필터 → 티커 리스트
│   ├── data_fetcher.py          # yfinance OHLCV 수집, TTL 캐시
│   ├── indicators.py            # MA5/20/60/120, RSI14, MACD, BB20, Volume
│   ├── checklist.py             # 7개 항목 채점 (enabled_checks, max_score)
│   ├── grader.py                # 비율 기반 S/A/B/SKIP 등급
│   ├── news_filter.py           # 뉴스 리스크 필터
│   ├── fundamental_fetcher.py   # yfinance: 실적일, 숏비율, 목표가
│   ├── trends_fetcher.py        # pytrends: Google 관심도 (TTL 24h)
│   ├── macro_fetcher.py         # fredapi: FRED 매크로 (TTL 7일)
│   ├── congress_fetcher.py      # quiverquant: 의원 거래 (TTL 24h)
│   ├── insider_fetcher.py       # sec-edgar: Form 4 내부자 매수 (TTL 24h)
│   └── batch_scheduler.py       # 데몬 스레드 배치 (macro + congress)
│
├── notifier/
│   ├── terminal.py              # colorama CLI 출력
│   └── telegram.py              # 텔레그램/카카오 알림 (미완성)
│
├── utils/
│   └── logger.py
│
├── static/
│   ├── css/
│   │   ├── base.css             # 전역 스타일 + 네비게이션 (CSS 변수 다크 테마)
│   │   ├── screen.css           # 스크리너 페이지 전용
│   │   └── about.css            # About 페이지 전용
│   └── js/
│       └── screen.js            # TomSelect + SSE EventSource
│
├── templates/
│   ├── base.html                # 레이아웃 (네비게이션, CSS/JS 블록)
│   ├── screen.html              # 스크리닝 메인 + 매크로 배너
│   └── about.html               # 시스템 설명 (초보자용)
│
├── output/results/              # CLI CSV 저장 경로
│
└── docs/                        # 이 문서들
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

**공통 패턴:**
```python
_cache: dict[str, tuple[any, datetime]] = {}
_TTL = 86400

def _is_fresh(key):
    if key not in _cache: return False
    _, fetched_at = _cache[key]
    return (datetime.now() - fetched_at).total_seconds() < _TTL
```

---

## 등급 계산 (비율 기반)

```python
_GRADE_RATIOS = [("S", 0.67), ("A", 0.44), ("B", 0.22)]

ratio = score / max_score  # max_score = 활성화된 항목 weight 합계
# 전체 9점 기준: S ≥ 6.03, A ≥ 3.96, B ≥ 1.98
```

체크리스트 항목 일부를 비활성화해도 등급 기준이 자동으로 조정됨.

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
| GET | `/about` | About 페이지 |
| GET | `/health` | 헬스체크 |
| GET | `/stream/screen` | SSE 스크리닝 스트림 |
| GET | `/api/tickers` | 티커 자동완성 검색 |

### /stream/screen 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `tickers` | string | `""` | 쉼표 구분 티커 (비우면 Finviz 전체 스캔) |
| `grade_filter` | string | `""` | S/A/B 단일 등급 필터 |
| `period` | string | `"6mo"` | 데이터 기간 (3mo/6mo/1y) |
| `rsi_min` | int | `45` | RSI 하한 |
| `rsi_max` | int | `65` | RSI 상한 |
| `checks` | string | `""` | 활성 체크리스트 항목 (쉼표 구분, 비우면 전체) |

---

## 환경변수

| 변수 | 필수 | 용도 |
|------|------|------|
| `FRED_API_KEY` | 권장 | FRED 매크로 배너 (없으면 배너 숨김) |
| `QUIVERQUANT_API_KEY` | 선택 | 의원거래 배지 (유료, 없으면 스킵) |
| `TELEGRAM_BOT_TOKEN` | 선택 | 텔레그램 알림 (미구현) |
| `TELEGRAM_CHAT_ID` | 선택 | 텔레그램 알림 (미구현) |
| `KAKAO_ACCESS_TOKEN` | 선택 | 카카오 알림 (미구현) |

---

## 실행 방법

```bash
# 패키지 설치 (최초 1회)
pip install -r requirements.txt

# 웹앱 실행
python -m uvicorn api.main:app --reload --port 8000

# CLI 실행 (그대로 유지)
python main.py --ticker AAPL MSFT
python main.py --grade S --save
```
