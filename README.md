# StockScope

미국 주식 분석 시스템. **스크리닝 서비스** (종목 발굴)와 **매매시그널 서비스** (진입 타이밍)를 독립 운영.

## 주요 기능

### 스크리닝 서비스 `/screen`
- **Finviz 사전 필터** — 거래량·RSI·이평선·EPS 조건으로 유니버스 압축
- **7개 기술적 체크리스트** — MA 정배열, RSI, MACD, 볼린저밴드, 거래량, 지지선, 추세
- **S/A/B/SKIP 등급** — 비율 기반 자동 분류 + 목표가·손절 계산
- **펀더멘털 배지** — 실적발표 D-N, 숏비율, 애널리스트 목표가, 내부자 매수
- **외부 시그널** — Google Trends 관심도, 의원 거래 내역
- **매크로 배너** — FRED API: 기준금리·CPI·실업률·장단기 금리차·VIX
- **★ Watchlist 추가** — 카드에서 직접 매매시그널 서비스로 연동

### 매매시그널 서비스 `/signals`
- **관심종목 관리** — Watchlist 태그 추가/삭제, 서버 영구 저장
- **4카테고리 시그널 채점** — Trend 35% / Momentum 25% / Volume 25% / Pattern 15%
- **STRONG BUY / BUY / WATCH / NO SIGNAL** — 진입가 밴드 + 손절가 표시
- **페이지 접속 시 자동 분석** — SSE 실시간 스트리밍

### 공통
- **Lightweight Charts 모달** — 캔들스틱 + MA20 + 매수/매도 마커 (lazy 렌더링)
- **SSE 실시간 스트리밍** — 분석 진행 상황 즉시 반영

## Tech Stack

| 레이어 | 기술 |
|--------|------|
| 웹 프레임워크 | FastAPI + Jinja2 + SSE |
| 데이터 | yfinance, finviz, pytrends, quiverquant, sec-edgar-downloader |
| 매크로 | FRED REST API (requests 직접 호출) |
| 스케줄링 | GitHub Actions (keepalive + daily batch) |
| 배포 | Render (free plan) |
| 프론트엔드 | Vanilla JS + TomSelect + Lightweight Charts 4.2 |

## 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정 (.env 파일 또는 export)
FRED_API_KEY=your_fred_api_key          # fred.stlouisfed.org 무료 발급
QUIVERQUANT_API_KEY=your_qq_api_key     # quiverquant.com 무료 tier
REFRESH_TOKEN=your_secret_token         # 임의 생성: python3 -c "import secrets; print(secrets.token_hex(32))"

# 서버 실행
./run.sh
```

브라우저에서 `http://localhost:8000` 접속.

## 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `FRED_API_KEY` | 필수 | FRED 매크로 데이터 ([무료 발급](https://fred.stlouisfed.org/docs/api/api_key.html)) |
| `QUIVERQUANT_API_KEY` | 필수 | 의원 거래 데이터 ([무료 tier](https://www.quiverquant.com)) |
| `REFRESH_TOKEN` | 배포 시 필수 | GitHub Actions → Render 배치 refresh 인증 토큰 |
| `RENDER_URL` | GitHub Secrets | Render 배포 URL (keepalive, daily-batch 워크플로우에서 사용) |

## 프로젝트 구조

```
fin_auto/
├── api/
│   ├── main.py                 # FastAPI 앱, startup 훅, refresh 엔드포인트
│   └── routes/
│       ├── screen.py           # SSE 스트리밍, compact 카드 렌더링
│       ├── tickers.py          # 티커 자동완성
│       └── chart.py            # /api/chart-data/{ticker} — LW Charts용 OHLCV+마커
├── screener/
│   ├── finviz_filter.py        # Finviz 사전 필터
│   ├── data_fetcher.py         # yfinance OHLCV + 분봉 수집 + 캐시
│   ├── indicators.py           # MA/RSI/MACD/BB + ATR/StochRSI/OBV/거래대금 계산
│   ├── checklist.py            # 7개 항목 채점
│   ├── grader.py               # S/A/B/SKIP 비율 기반 등급 분류
│   ├── signal_scorer.py        # 4카테고리 매매시그널 채점
│   ├── watchlist_store.py      # Watchlist JSON 저장/로드
│   ├── fundamental_fetcher.py  # yfinance 펀더멘털 (실적/숏/목표가/내부자)
│   ├── trends_fetcher.py       # Google Trends 관심도
│   ├── congress_fetcher.py     # 의원 거래 내역 (quiverquant)
│   ├── insider_fetcher.py      # SEC Form 4 내부자 거래
│   ├── macro_fetcher.py        # FRED 매크로 지표
│   └── batch_scheduler.py      # 서버 시작 시 배치 + 진행 게이지
├── services/
│   ├── screener_service.py     # run_analysis() — 스크리닝 오케스트레이터
│   └── signal_service.py       # run_signal_analysis() — 시그널 오케스트레이터
├── data/
│   └── watchlist.json          # Watchlist 영구 저장 (git 제외)
├── static/
│   ├── css/                    # base.css / screen.css / signals.css / about.css
│   └── js/                     # screen.js / signals.js
├── templates/
│   ├── base.html               # 네비게이션 포함 베이스 레이아웃
│   ├── about.html              # About 페이지 (기본 진입)
│   ├── screen.html             # 스크리닝 대시보드
│   └── signals.html            # 매매시그널 대시보드
├── .github/workflows/
│   ├── keepalive.yml           # 10~14분 간격 ping (Render 슬립 방지)
│   └── daily-batch.yml         # KST 07:00 배치 refresh 트리거
└── docs/
    ├── design_doc.md
    ├── architecture.md
    └── changelog.md
```

## GitHub Actions 설정

Render free plan은 15분 비활성 시 슬립 → 두 워크플로우로 해결.

### Repository Secrets 설정

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret 이름 | 값 |
|-------------|-----|
| `RENDER_URL` | `https://your-app.onrender.com` |
| `REFRESH_TOKEN` | Render Environment Variables에 설정한 동일 토큰 |

### Render Environment Variables 설정

Render 대시보드 → 앱 선택 → **Environment** 탭:

| 변수 | 값 |
|------|-----|
| `FRED_API_KEY` | FRED API 키 |
| `QUIVERQUANT_API_KEY` | QuiverQuant API 키 |
| `REFRESH_TOKEN` | GitHub Secrets의 `REFRESH_TOKEN`과 동일한 값 |

## 등급 기준

| 등급 | 점수 | 행동 |
|------|------|------|
| S | ≥ 6 | 즉시 진입 |
| A | ≥ 4 | 분할 진입 검토 |
| B | ≥ 2 | 대기 |
| SKIP | RSI≥80 또는 0점 | 진입 금지 |

목표가 +8% / +15%, 손절 -7%.

## 매매 타이밍 시그널

차트 모달의 마스터 시그널은 종목 카드 "차트 분석" 버튼 클릭 시 생성됩니다.

| 시그널 | 조건 |
|--------|------|
| 매수 | MA20 > MA60 (상승추세) AND 가격이 MA20±ATR 눌림목 존 AND (RSI 반등 OR 거래대금 2배↑) |
| 매도 | 데드크로스 OR RSI 75 이상→하락 OR ATR 손절(MA20−2×ATR 이탈) |

별도 시그널 스코어링(7개 지표)은 STRONG BUY / BUY / WATCH / NO SIGNAL 4단계로 표시됩니다.
