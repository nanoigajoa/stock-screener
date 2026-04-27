# 미구현 기능 계획 — phase-future

> 브레인스토밍 + 구체화된 아이디어. 우선순위 순.

---

## 1순위 — 목표가·손절 비율 커스터마이징

### 현황
`config.py`에 고정값:
```python
TARGET_1_PCT = 0.08   # +8%
TARGET_2_PCT = 0.15   # +15%
STOP_LOSS_PCT = 0.15  # -15%
```

### 계획
사용자가 고급 설정에서 직접 조정 가능하도록 변경.

**변경 파일:**
- `templates/screen.html`: 고급 설정에 슬라이더 3개 추가
  ```
  1차 목표 [+5% ───●─── +20%]  현재: +8%
  2차 목표 [+5% ─────────●── +30%]  현재: +15%
  손절     [−5% ─────●────── −25%]  현재: −15%
  ```
- `api/routes/screen.py`: `target1`, `target2`, `stoploss` 쿼리 파라미터 추가
- `services/screener_service.py`: `run_analysis(target1_pct, target2_pct, stop_loss_pct)` 파라미터 추가
- `screener/grader.py`: `grade()` 함수에 비율 파라미터 전달

**구현 난이도:** 낮음. 기존 구조에 파라미터 추가만 하면 됨.

---

## 2순위 — 백테스팅 엔진

### 목표
"이 신호가 과거에 얼마나 맞았는가?"를 사용자에게 보여줌.

### 방법론 (사용자 관점에서 와닿는 방식)

**단순 승률 백테스트:**
- 과거 N개월 데이터에서 동일한 7개 체크리스트 신호 발생 시점 찾기
- 그 다음 날부터 N일 후 +8% 도달 여부 측정
- 결과: `승률 68% (최근 6개월, 신호 37회)`

**구현 포인트:**
```python
def backtest_ticker(ticker: str, period: str = "1y") -> dict:
    df = fetch_ohlcv_full(ticker, period)
    signals = []
    for i in range(120, len(df) - 20):
        window = df.iloc[:i]
        ind = calculate_indicators(window)
        result = score_ticker(ind)
        if result["total_score"] >= 6:  # S급 신호
            entry_price = df.iloc[i]["Close"]
            future = df.iloc[i:i+20]["Close"]
            hit = any(future >= entry_price * 1.08)
            signals.append({"date": df.index[i], "hit": hit})
    
    win_rate = sum(s["hit"] for s in signals) / len(signals) if signals else 0
    return {"signals": len(signals), "win_rate": round(win_rate * 100, 1)}
```

**표시:**
- 종목 카드에 `백테스트 승률 68%` 배지 추가
- About 페이지에 방법론 설명

**제약:**
- yfinance 데이터 기준 (15~20분 지연, 충분히 정확)
- 티커당 ~2초 추가 소요 → extras 병렬 조회에 포함

---

## 3순위 — VIX 데이터 복구

### 현황
FRED `VIXCLS` 시리즈가 현재 `None` 반환 중. 배너에 `VIX N/A` 표시됨.

### 원인 파악 필요
```python
# macro_fetcher.py 에서
vix = _safe("VIXCLS")  # → None
```
- FRED VIXCLS 업데이트 지연 가능성
- 대안: `yfinance.download("^VIX", period="5d")["Close"].iloc[-1]`

### 수정 방법
`macro_fetcher.py`의 `_fetch()` 함수에 yfinance fallback 추가:
```python
vix = _safe("VIXCLS")
if vix is None:
    try:
        import yfinance as yf
        vix_df = yf.download("^VIX", period="5d", progress=False)
        if not vix_df.empty:
            vix = round(float(vix_df["Close"].iloc[-1]), 2)
    except Exception:
        pass
```

---

## 4순위 — Render 배포

### 현황
로컬 실행만 가능. Render 무료 티어는 슬립 후 재시작 시 메모리 캐시 초기화됨.

### 배포 준비 체크리스트
- [ ] `requirements.txt` 최신화 확인
- [ ] `Procfile` 생성: `web: uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- [ ] Render 환경변수 설정: `FRED_API_KEY`
- [ ] 슬립 복귀 시 배치 스케줄러 재실행 확인 (`on_startup` 핸들러가 처리)
- [ ] Lazy fallback 동작 검증 (캐시 없을 때 즉시 fetch)

### Render 슬립 이슈
- 무료 티어: 15분 비활성 시 슬립
- 슬립 복귀: 30~60초 콜드스타트
- 해결책: batch_scheduler의 `_loop()`가 startup 시 즉시 1회 실행하므로 자동 복구

---

## 5순위 — 텔레그램·카카오 알림

### 현황
`notifier/telegram.py` 파일 존재하지만 웹앱과 미연동.

### 계획
- S급 종목 발견 시 자동 발송 (batch_scheduler에 통합)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 환경변수 사용
- `KAKAO_ALERT_GRADES = ["S"]` 설정값 활용

---

## 6순위 (장기) — 추가 외부 데이터소스

| 소스 | 내용 | 비용 |
|------|------|------|
| Alpha Vantage | 실시간 주가 (15분 지연 해소) | 무료 tier 500req/day |
| Unusual Whales | 옵션 플로우 (기관 방향성) | 유료 |
| Reddit WSB 감성 | 소셜 모멘텀 | pushshift API (무료) |
| SEC 8-K 실시간 | 중요 공시 자동 감지 | SEC EDGAR 무료 |

---

## 구현 순서 권장

```
목표가 커스터마이징 (1~2시간)
  → VIX 복구 (30분)
    → 백테스팅 (1~2일)
      → Render 배포 (2~3시간)
        → 텔레그램 알림 (1~2시간)
```
