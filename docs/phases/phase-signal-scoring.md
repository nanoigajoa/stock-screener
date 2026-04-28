# Phase: 매매시점 표시 기능 이식

> **작성일:** 2026-04-28  
> **원본:** `plan.md` (루트 디렉토리)  
> **상태:** 미구현 — 구현 준비 완료

---

## 목표

기존 체크리스트(S/A/B/SKIP) 파이프라인을 유지하면서, 7개 보조지표 기반 **매매시점 시그널 스코어링** 레이어를 추가한다. 두 시스템은 독립 필드로 공존한다.

---

## 원본 계획 대비 수정 사항 (구현 전 검토 결과)

| 항목 | 원본 | 수정 | 이유 |
|------|------|------|------|
| 캔들 패턴 정의 | 누락 | 양봉 + 아랫꼬리 비율로 정의 | UI 참조 있으나 로직 없음 |
| VWAP 일중 초기화 | "필요" 언급만 | groupby(date)로 구현 명시 | 5일치 15m봉 연속 내려옴 |
| StochRSI K/D | K=3, D=3 (모호) | StochRSI → %K=SMA(3) → %D=SMA(%K,3) 명확화 | 표준 방식 |
| 분봉 캐시 키 | (ticker, period) | **(ticker, date, interval)** 3-tuple | 기존 키와 충돌 |
| 분봉 적용 대상 | 전체 종목 | **displayable 종목에만** | 100종목 × 3회 호출 방지 |
| stop_loss 필드 | 기존과 동일 이름 | **signal_stop**으로 분리 | grader.py의 stop_loss와 충돌 |
| OBV 감지 윈도우 | N=5 | **N=10** | N=5는 노이즈 과다 |
| 시그널 스코어 최대 | 7 | **6+1 = 7** (캔들 패턴 포함 명시) | 원본에서 7번째 항목 누락 |
| hourly MA | 필수 | **선택적 (None 허용)** | 일부 티커 1h 데이터 미제공 |

---

## 구현할 기능 7개 (확정)

### [1] ATR 기반 진입존 + 매매시그널 손절가

**데이터:** 기존 일봉 OHLCV (추가 fetch 없음)

```python
# indicators.py 추가
def calc_atr_zones(df: pd.DataFrame, period: int = 14) -> dict | None:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    last = float(close.iloc[-1])
    if pd.isna(atr):
        return None
    return {
        "atr":        round(float(atr), 4),
        "entry_low":  round(last - 0.5 * atr, 2),
        "entry_high": round(last + 0.3 * atr, 2),
        "signal_stop": round(last - 2.0 * atr, 2),  # grader.py의 stop_loss와 별도 필드
    }
```

**시그널 조건 (signal_scorer 채점):**
- `True` — ATR 데이터 정상 산출 + `entry_low <= price <= entry_high` 또는 price가 entry_low 미만 (아직 진입 전)

---

### [2] VWAP + 시그널

**데이터:** 15분봉 `interval='15m', period='5d'` — 신규 per-ticker fetch

**일중 초기화 구현:**
```python
# data_fetcher.py 추가 함수
def fetch_intraday(ticker: str, interval: str, period: str) -> pd.DataFrame | None:
    cache_key = (ticker, date.today(), interval)
    if cache_key in _cache:
        return _cache[cache_key][1]
    try:
        df = yf.Ticker(ticker).history(interval=interval, period=period)
        if df.empty:
            return None
        _cache[cache_key] = (date.today(), df)
        return df
    except Exception:
        return None

# indicators.py 추가 함수
def calc_vwap(df_15m: pd.DataFrame) -> dict | None:
    if df_15m is None or df_15m.empty:
        return None
    df = df_15m.copy()
    df["date"] = df.index.normalize()              # 날짜별 그룹
    df["tp"]   = (df["High"] + df["Low"] + df["Close"]) / 3
    df["cum_tpv"] = df.groupby("date").apply(
        lambda g: (g["tp"] * g["Volume"]).cumsum()
    ).values
    df["cum_vol"] = df.groupby("date")["Volume"].cumsum()
    df["vwap"] = df["cum_tpv"] / df["cum_vol"]
    last_vwap  = float(df["vwap"].iloc[-1])
    last_price = float(df["Close"].iloc[-1])
    return {
        "vwap":   round(last_vwap, 2),
        "signal": "above" if last_price > last_vwap else "below",
    }
```

**시그널 조건:** `signal == "above"` → True

---

### [3] Stochastic RSI + 시그널

**데이터:** 기존 일봉 Close (추가 fetch 없음)

**계산 방식 (표준):**
```python
# indicators.py 추가
def calc_stoch_rsi(close: pd.Series, rsi_period=14, stoch_period=14, k=3, d=3) -> dict | None:
    rsi_vals  = _rsi(close, rsi_period)                        # 기존 _rsi() 재사용
    rsi_min   = rsi_vals.rolling(stoch_period).min()
    rsi_max   = rsi_vals.rolling(stoch_period).max()
    stoch_rsi = (rsi_vals - rsi_min) / (rsi_max - rsi_min + 1e-9)
    pct_k     = stoch_rsi.rolling(k).mean()
    pct_d     = pct_k.rolling(d).mean()

    k_now, d_now   = float(pct_k.iloc[-1]),  float(pct_d.iloc[-1])
    k_prev, d_prev = float(pct_k.iloc[-2]),  float(pct_d.iloc[-2])
    if any(pd.isna(v) for v in [k_now, d_now, k_prev, d_prev]):
        return None

    if k_now < 0.2 and k_prev <= d_prev and k_now > d_now:
        signal = "buy"
    elif k_now > 0.8 and k_prev >= d_prev and k_now < d_now:
        signal = "sell"
    else:
        signal = "neutral"

    return {"k": round(k_now, 4), "d": round(d_now, 4), "signal": signal}
```

**시그널 조건:** `signal == "buy"` → True

---

### [4] 볼린저밴드 %B + 밴드폭

**데이터:** 기존 일봉 + 이미 계산된 BB 값 재활용

```python
# indicators.py 추가 (기존 _bbands() 확장)
def calc_bb_advanced(df: pd.DataFrame) -> dict | None:
    close  = df["Close"]
    upper, middle, lower = _bbands(close)   # 기존 함수 재사용
    last_close = float(close.iloc[-1])
    u, m, l = float(upper.iloc[-1]), float(middle.iloc[-1]), float(lower.iloc[-1])
    band_range = u - l
    if band_range == 0 or pd.isna(u):
        return None
    pct_b = (last_close - l) / band_range
    bandwidth = band_range / m if m != 0 else None
    if pct_b < 0.05:
        signal = "buy"
    elif pct_b > 0.95:
        signal = "sell"
    else:
        signal = "neutral"
    return {
        "pct_b":     round(pct_b, 4),
        "bandwidth": round(bandwidth, 4) if bandwidth else None,
        "signal":    signal,
    }
```

**시그널 조건:** `signal == "buy"` → True

---

### [5] OBV 다이버전스 감지

**데이터:** 기존 일봉 OHLCV (추가 fetch 없음)

**피벗 윈도우:** N=10 (원본 N=5에서 수정 — 노이즈 방지)

```python
# indicators.py 추가
def calc_obv_divergence(df: pd.DataFrame, window: int = 10) -> dict | None:
    close  = df["Close"]
    volume = df["Volume"]
    sign   = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv    = (sign * volume).cumsum()

    if len(obv) < window * 2:
        return None

    # 최근 두 구간에서 고점/저점 비교
    seg1_c = close.iloc[-(window*2):-window]
    seg2_c = close.iloc[-window:]
    seg1_o = obv.iloc[-(window*2):-window]
    seg2_o = obv.iloc[-window:]

    price_lower_low = seg2_c.min() < seg1_c.min()
    obv_higher_low  = seg2_o.min() > seg1_o.min()
    price_higher_high = seg2_c.max() > seg1_c.max()
    obv_lower_high    = seg2_o.max() < seg1_o.max()

    if price_lower_low and obv_higher_low:
        divergence = "bullish"
    elif price_higher_high and obv_lower_high:
        divergence = "bearish"
    else:
        divergence = "none"

    return {"obv_last": round(float(obv.iloc[-1]), 0), "divergence": divergence}
```

**시그널 조건:** `divergence == "bullish"` → True

---

### [6] MA 크로스 (일봉 + 시간봉)

**일봉:** 기존 MA20/MA60 재활용  
**시간봉:** `interval='1h', period='60d'` — 신규 per-ticker fetch, 데이터 없으면 `None` 반환

```python
# indicators.py 추가
def calc_ma_cross(df_daily: pd.DataFrame, df_hourly: pd.DataFrame | None = None) -> dict:
    close_d  = df_daily["Close"]
    ma20_d   = _sma(close_d, 20)
    ma60_d   = _sma(close_d, 60)
    # 직전 봉 기준 크로스 감지
    def _cross(fast, slow):
        if len(fast) < 2 or fast.iloc[-1] is None or slow.iloc[-1] is None:
            return "none"
        curr_above = fast.iloc[-1] > slow.iloc[-1]
        prev_above = fast.iloc[-2] > slow.iloc[-2]
        if not prev_above and curr_above:
            return "golden"
        if prev_above and not curr_above:
            return "dead"
        return "none"

    daily_cross = _cross(ma20_d, ma60_d)

    hourly_cross = None
    if df_hourly is not None and len(df_hourly) >= 60:
        close_h = df_hourly["Close"]
        ma20_h  = _sma(close_h, 20)
        ma60_h  = _sma(close_h, 60)
        hourly_cross = _cross(ma20_h, ma60_h)

    return {"daily": daily_cross, "hourly": hourly_cross}
```

**시그널 조건:** `daily == "golden"` → True  
(hourly는 UI 참고 표시용, 채점에 미포함 — 데이터 불안정)

---

### [7] 캔들 패턴 (원본 누락 → 신규 정의)

**데이터:** 기존 일봉 OHLCV 마지막 봉 (추가 fetch 없음)

**패턴 정의:**
- **양봉 확인:** `close > open`
- **몸통 비율:** `(close - open) / open > 0.003` (0.3% 이상 — 도지 제외)
- **아랫꼬리 우세:** `(open - low) / (close - low) > 0.4` (지지 확인 구조)

```python
# indicators.py 추가
def calc_candle_pattern(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    o, h, l, c = float(last["Open"]), float(last["High"]), float(last["Low"]), float(last["Close"])
    body    = c - o
    full_range = h - l if h != l else 1e-9
    is_bullish  = body > 0
    body_ratio  = body / o if o != 0 else 0
    lower_shadow = o - l if is_bullish else c - l
    lower_ratio  = lower_shadow / full_range
    if is_bullish and body_ratio > 0.003 and lower_ratio > 0.4:
        pattern = "hammer_bull"   # 망치형 양봉 (강한 매수 신호)
    elif is_bullish and body_ratio > 0.003:
        pattern = "bull"          # 일반 양봉
    else:
        pattern = "neutral"
    return {"pattern": pattern, "body_ratio": round(body_ratio, 4)}
```

**시그널 조건:** `pattern in ("hammer_bull", "bull")` → True

---

## 통합 시그널 스코어링

**파일:** `screener/signal_scorer.py` (신규 생성)

```python
# signal_scorer.py
from screener.indicators import (
    calc_atr_zones, calc_vwap, calc_stoch_rsi,
    calc_bb_advanced, calc_obv_divergence, calc_ma_cross, calc_candle_pattern,
)

_SIGNAL_LABELS = {
    "atr":       "ATR 진입존",
    "vwap":      "VWAP 위치",
    "stoch_rsi": "StochRSI",
    "bb_pct_b":  "BB %B",
    "obv_div":   "OBV 다이버전스",
    "ma_cross":  "MA 크로스",
    "candle":    "캔들 패턴",
}

def score_signals(
    df_daily, df_hourly=None, df_15m=None
) -> dict:
    """
    7개 보조지표 채점. 기존 checklist와 독립.
    Returns:
        {
            "signal_grade":     "STRONG BUY" | "BUY" | "WATCH" | "NO SIGNAL",
            "signal_score":     int (0~7),
            "signal_breakdown": { label: bool | None },
            "entry_low":        float | None,
            "entry_high":       float | None,
            "signal_stop":      float | None,
        }
    """
    atr    = calc_atr_zones(df_daily)
    stoch  = calc_stoch_rsi(df_daily["Close"])
    bb     = calc_bb_advanced(df_daily)
    obv    = calc_obv_divergence(df_daily)
    ma     = calc_ma_cross(df_daily, df_hourly)
    vwap   = calc_vwap(df_15m)
    candle = calc_candle_pattern(df_daily)

    breakdown = {
        "atr":       atr is not None,                                    # 진입존 산출 가능
        "vwap":      vwap["signal"] == "above" if vwap else None,
        "stoch_rsi": stoch["signal"] == "buy"  if stoch else None,
        "bb_pct_b":  bb["signal"]   == "buy"   if bb    else None,
        "obv_div":   obv["divergence"] == "bullish" if obv else None,
        "ma_cross":  ma["daily"] == "golden",
        "candle":    candle["pattern"] in ("hammer_bull", "bull") if candle else None,
    }

    # None(데이터 없음)은 채점 제외, 가용 항목만 합산
    scored  = {k: v for k, v in breakdown.items() if v is not None}
    score   = sum(1 for v in scored.values() if v)
    maximum = len(scored)  # 가용 항목 수 (vwap/hourly 없으면 감소)

    if maximum == 0:
        grade = "NO SIGNAL"
    elif score >= max(5, round(maximum * 0.71)):
        grade = "STRONG BUY"
    elif score >= max(3, round(maximum * 0.43)):
        grade = "BUY"
    elif score >= 1:
        grade = "WATCH"
    else:
        grade = "NO SIGNAL"

    return {
        "signal_grade":     grade,
        "signal_score":     score,
        "signal_max":       maximum,
        "signal_breakdown": breakdown,
        "entry_low":        atr["entry_low"]   if atr else None,
        "entry_high":       atr["entry_high"]  if atr else None,
        "signal_stop":      atr["signal_stop"] if atr else None,
    }
```

### 등급 기준

| 등급 | 조건 | 배지 색상 |
|------|------|---------|
| STRONG BUY | score ≥ 5 (또는 가용 항목의 71% 이상) | 초록 |
| BUY | score ≥ 3 (또는 가용 항목의 43% 이상) | 연두 |
| WATCH | score ≥ 1 | 노랑 |
| NO SIGNAL | score = 0 | 회색 |

---

## 데이터 수집 수정

**파일:** `screener/data_fetcher.py`

```python
# 추가: 분봉 단일 티커 fetch (캐시 키 3-tuple)
_intraday_cache: dict[tuple[str, date, str], pd.DataFrame] = {}

def fetch_intraday(ticker: str, interval: str, period: str) -> pd.DataFrame | None:
    """단일 티커 분봉 데이터. 실패 시 None 반환 (호출자가 None 처리)."""
    key = (ticker, date.today(), interval)
    if key in _intraday_cache:
        return _intraday_cache[key]
    try:
        df = yf.Ticker(ticker).history(interval=interval, period=period, auto_adjust=True)
        df.index = df.index.tz_localize(None) if df.index.tzinfo else df.index
        if len(df) < 10:
            return None
        _intraday_cache[key] = df
        return df
    except Exception:
        return None
```

**기존 `fetch_ohlcv()`는 변경 없음.** 분봉은 displayable 종목에서만 호출.

---

## 파이프라인 연결

**파일:** `services/screener_service.py`

기존 `run_analysis()` 내 Step 9 (펀더멘털·외부 데이터) 이후에 추가:

```python
# Step 10. 시그널 스코어링 (displayable 종목에만)
from screener.signal_scorer import score_signals
from screener.data_fetcher import fetch_intraday

def _fetch_signal(r: dict) -> dict:
    tk = r["ticker"]
    df_d  = ohlcv_map.get(tk)       # 이미 수집된 일봉 재사용
    df_h  = fetch_intraday(tk, "1h",  "60d")
    df_15 = fetch_intraday(tk, "15m", "5d")
    return score_signals(df_d, df_h, df_15)

with ThreadPoolExecutor(max_workers=4) as ex:
    signal_futures = {r["ticker"]: ex.submit(_fetch_signal, r) for r in displayable}

for r in displayable:
    sig = signal_futures[r["ticker"]].result()
    r.update(sig)   # signal_grade, signal_score, signal_breakdown, entry_low, entry_high, signal_stop 병합
```

**기존 `grade`, `score`, `checklist`, `stop_loss` 필드는 그대로 유지.**

---

## UI 수정

### `api/routes/screen.py` — `_render_all_indicators()` 확장

시그널 배지 + 진입 정보를 기존 카드 하단에 추가:

```python
def _render_signal_section(r: dict) -> str:
    grade = r.get("signal_grade", "NO SIGNAL")
    score = r.get("signal_score", 0)
    maximum = r.get("signal_max", 0)
    breakdown = r.get("signal_breakdown", {})
    entry_low  = r.get("entry_low")
    entry_high = r.get("entry_high")
    signal_stop = r.get("signal_stop")

    badge_class = {
        "STRONG BUY": "sig-strong-buy",
        "BUY":        "sig-buy",
        "WATCH":      "sig-watch",
        "NO SIGNAL":  "sig-nosignal",
    }.get(grade, "sig-nosignal")

    badge = f'<span class="signal-badge {badge_class}">{grade} {score}/{maximum}</span>'

    # 진입 정보
    entry_html = ""
    if entry_low and entry_high:
        entry_html = (
            f'<div class="entry-info">'
            f'<span class="entry-label">진입존</span> ${entry_low:,.2f} ~ ${entry_high:,.2f}'
            f'</div>'
        )
    if signal_stop:
        entry_html += (
            f'<div class="entry-info entry-stop">'
            f'<span class="entry-label">시그널 손절</span> ${signal_stop:,.2f}'
            f'</div>'
        )

    # 지표별 체크
    checks_html = ""
    label_map = {
        "atr":       "ATR 진입존",
        "vwap":      "VWAP",
        "stoch_rsi": "StochRSI",
        "bb_pct_b":  "BB %B",
        "obv_div":   "OBV 다이버전스",
        "ma_cross":  "MA 크로스",
        "candle":    "캔들",
    }
    for key, label in label_map.items():
        val = breakdown.get(key)
        if val is None:
            icon, cls = "–", "sig-na"
        elif val:
            icon, cls = "✓", "sig-ok"
        else:
            icon, cls = "✗", "sig-bad"
        checks_html += f'<span class="signal-check {cls}">{label} {icon}</span>'

    return (
        f'<div class="signal-section">'
        f'{badge}{entry_html}'
        f'<div class="signal-checks">{checks_html}</div>'
        f'</div>'
    )
```

### `static/css/screen.css` — 시그널 섹션 스타일 추가

```css
.signal-section {
    border-top: 1px solid var(--border);
    padding-top: 0.8rem;
    margin-top: 0.8rem;
}
.signal-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
}
.sig-strong-buy { background: rgba(72,187,120,0.2); color: #68d391; }
.sig-buy        { background: rgba(154,230,180,0.2); color: #9ae6b4; }
.sig-watch      { background: rgba(236,201,75,0.2);  color: #f6e05e; }
.sig-nosignal   { background: rgba(160,174,192,0.1); color: var(--text3); }

.entry-info { font-size: 0.78rem; color: var(--text2); margin: 0.2rem 0; }
.entry-stop { color: #fc8181; }
.entry-label { color: var(--text3); margin-right: 0.3rem; }

.signal-checks {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-top: 0.4rem;
}
.signal-check {
    font-size: 0.72rem;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    border: 1px solid var(--border);
}
```

---

## 작업 순서

```
1. screener/data_fetcher.py   — fetch_intraday() 추가 (캐시 키 3-tuple)
2. screener/indicators.py     — 지표 함수 7개 추가 (calc_atr_zones ~ calc_candle_pattern)
3. screener/signal_scorer.py  — 신규 생성 (score_signals)
4. services/screener_service.py — Step 10 시그널 스코어링 블록 추가
5. api/routes/screen.py       — _render_signal_section() 추가, 카드 렌더링에 연결
6. static/css/screen.css      — 시그널 섹션 스타일 추가
```

---

## 성능 예상 (displayable 10개 기준)

| 단계 | 소요 시간 | 비고 |
|------|---------|------|
| 기존 파이프라인 | 30~60s | 변경 없음 |
| 시그널 지표 계산 | +0~1s | daily 재사용, pandas only |
| 분봉 fetch (1h + 15m) | +5~15s | ThreadPoolExecutor 4개 병렬 |
| 합계 | ~35~75s | 기존 대비 최대 +15s |

---

## 제약 조건 (원본 유지)

1. 기존 함수/로직 삭제 금지 — 추가만
2. snake_case 네이밍 컨벤션 유지
3. 각 지표 함수 독립 호출 가능
4. yfinance 호출 실패 시 `None` 반환 → 상위에서 처리
5. 분봉 캐시 적용 (3-tuple 키)
6. 신규 파일은 `screener/` 하위

---

## 검증 체크리스트

- [ ] `fetch_intraday("AAPL", "15m", "5d")` → DataFrame 반환 확인
- [ ] `calc_atr_zones(df)` → entry_low/entry_high/signal_stop 숫자 확인
- [ ] `calc_stoch_rsi(close)` → k/d/signal 반환, NaN 없음 확인
- [ ] `score_signals(df_d)` → vwap=None, hourly=None 상태에서도 5개 지표 채점 확인
- [ ] AAPL 단일 스캔 → 시그널 배지 카드 하단 표시 확인
- [ ] 분봉 데이터 없는 종목(OTC 등) → `None` graceful 처리 확인
- [ ] 기존 S/A/B/SKIP 등급 → 변경 없음 확인
