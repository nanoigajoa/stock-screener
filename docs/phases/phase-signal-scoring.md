# 매매시점 시그널 스코어링 구현 계획

> **작성일:** 2026-04-28  
> **원본:** `plan.md` (루트 디렉토리)  
> **상태:** 미구현 — 구현 준비 완료

---

## 개요

기존 체크리스트(S/A/B/SKIP) 파이프라인을 유지하면서, 7개 보조지표 기반 **매매시점 시그널 스코어링** 레이어를 추가한다.  
두 시스템은 독립 필드로 공존하며 기존 등급에 영향을 주지 않는다.

### 의존성 그래프

```
Phase 1  requirements.txt (CandleKit 설치)
   │
Phase 2  data_fetcher.py (fetch_intraday)
   │
   ├─ Phase 3  indicators.py — 일봉 지표 5개
   │      (ATR / StochRSI / BB%B / OBV / MA Cross daily)
   │
   ├─ Phase 4  indicators.py — 분봉 지표 2개
   │      (VWAP 15m / MA Cross hourly)
   │
Phase 5  signal_scorer.py (7개 통합 + CandleKit)
   │      ← Phase 1, 3, 4 모두 완료 후 시작
   │
Phase 6  screener_service.py (파이프라인 연결)
   │      ← Phase 5 완료 후 시작
   │
Phase 7  screen.py + screen.css (UI 반영)
          ← Phase 6 완료 후 시작
```

---

## Phase 1 — 의존성 추가

**파일:** `requirements.txt`

**변경 내용:**

```diff
+ git+https://github.com/zhirodadkhah/CandleKit.git@v1.0.1
```

> **이유:** CandleKit은 PyPI 미등록. GitHub URL + 버전 태그 고정으로 Render 빌드 안정성 확보.  
> 태그 없이 URL만 쓰면 저장소 변경 시 빌드 깨짐 (fredapi 사례와 동일한 위험).

**완료 기준:**
- [ ] `pip install -r requirements.txt` 성공
- [ ] `from candlekit import scan_symbol_df, CandlePatterns` import 오류 없음

---

## Phase 2 — 분봉 데이터 수집 레이어

**파일:** `screener/data_fetcher.py`

**변경 내용:** `fetch_intraday()` 함수 추가. 기존 `fetch_ohlcv()`는 수정 없음.

```python
# 기존 _cache 와 별도 — 키 구조가 다름 (3-tuple)
_intraday_cache: dict[tuple[str, date, str], pd.DataFrame] = {}


def fetch_intraday(ticker: str, interval: str, period: str) -> pd.DataFrame | None:
    """
    단일 티커 분봉 데이터 수집. 당일 캐싱 (interval별 독립 캐시).
    실패 시 None 반환 — 호출자가 None 처리 필수.

    Args:
        ticker:   종목 코드 (예: "AAPL")
        interval: yfinance interval 문자열 ("1h", "15m")
        period:   yfinance period 문자열 ("60d", "5d")
    """
    key = (ticker, date.today(), interval)
    if key in _intraday_cache:
        return _intraday_cache[key]
    try:
        df = yf.Ticker(ticker).history(
            interval=interval, period=period, auto_adjust=True
        )
        # timezone 제거 (이후 groupby 연산 단순화)
        if df.index.tzinfo is not None:
            df.index = df.index.tz_localize(None)
        if len(df) < 10:
            return None
        _intraday_cache[key] = df
        return df
    except Exception:
        return None
```

> **캐시 키 설계:** 기존 `_cache`는 `(ticker, period)` 2-tuple.  
> 분봉은 `(ticker, date, interval)` 3-tuple로 별도 분리 → 충돌 없음.

**완료 기준:**
- [ ] `fetch_intraday("AAPL", "15m", "5d")` → DataFrame 반환 (행 수 ≥ 10)
- [ ] `fetch_intraday("AAPL", "1h", "60d")` → DataFrame 반환
- [ ] 존재하지 않는 티커 → None 반환 (예외 없음)
- [ ] 동일 호출 2회 → 두 번째는 캐시 히트 (네트워크 요청 없음)

---

## Phase 3 — 일봉 기반 지표 5개

**파일:** `screener/indicators.py` (기존 함수 아래에 추가, 삭제 없음)

### 3-1. ATR 기반 진입존 + 시그널 손절가

```python
def calc_atr_zones(df: pd.DataFrame, period: int = 14) -> dict | None:
    """
    ATR(14) 기반 진입존·시그널 손절가 계산.
    grader.py의 stop_loss(비율 기반)와 별개 필드(signal_stop)로 반환.
    """
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr_val = tr.rolling(period).mean().iloc[-1]
    if pd.isna(atr_val):
        return None
    last = float(close.iloc[-1])
    atr  = float(atr_val)
    return {
        "atr":         round(atr, 4),
        "entry_low":   round(last - 0.5 * atr, 2),
        "entry_high":  round(last + 0.3 * atr, 2),
        "signal_stop": round(last - 2.0 * atr, 2),
    }
```

시그널 채점 조건: ATR 계산 가능 + `entry_low <= price <= entry_high` (진입존 안에 있음)

---

### 3-2. Stochastic RSI + 시그널

```python
def calc_stoch_rsi(
    close: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> dict | None:
    """
    표준 StochRSI: RSI → Stochastic 적용 → %K(SMA 3) → %D(SMA 3).
    0~1 범위 (0.2 = 과매도, 0.8 = 과매수).
    """
    rsi_s   = _rsi(close, rsi_period)          # 기존 _rsi() 재사용
    rsi_min = rsi_s.rolling(stoch_period).min()
    rsi_max = rsi_s.rolling(stoch_period).max()
    stoch   = (rsi_s - rsi_min) / (rsi_max - rsi_min + 1e-9)
    pct_k   = stoch.rolling(k_smooth).mean()
    pct_d   = pct_k.rolling(d_smooth).mean()

    k_cur, d_cur   = pct_k.iloc[-1], pct_d.iloc[-1]
    k_prv, d_prv   = pct_k.iloc[-2], pct_d.iloc[-2]
    if any(pd.isna(v) for v in [k_cur, d_cur, k_prv, d_prv]):
        return None

    if k_cur < 0.2 and k_prv <= d_prv and k_cur > d_cur:
        signal = "buy"    # 과매도 구간에서 상향 돌파
    elif k_cur > 0.8 and k_prv >= d_prv and k_cur < d_cur:
        signal = "sell"   # 과매수 구간에서 하향 이탈
    else:
        signal = "neutral"

    return {
        "k":      round(float(k_cur), 4),
        "d":      round(float(d_cur), 4),
        "signal": signal,
    }
```

시그널 채점 조건: `signal == "buy"`

---

### 3-3. 볼린저밴드 %B + 밴드폭

```python
def calc_bb_advanced(df: pd.DataFrame) -> dict | None:
    """
    기존 _bbands() 재사용. %B와 밴드폭 추가 반환.
    %B < 0.05 → 하단 돌파 직후 (매수 타이밍)
    %B > 0.95 → 상단 돌파 (과매수)
    """
    close = df["Close"]
    upper, middle, lower = _bbands(close)
    u = float(upper.iloc[-1])
    m = float(middle.iloc[-1])
    l = float(lower.iloc[-1])
    c = float(close.iloc[-1])
    band_range = u - l
    if band_range == 0 or any(pd.isna(v) for v in [u, m, l]):
        return None
    pct_b     = (c - l) / band_range
    bandwidth = (band_range / m) if m != 0 else None
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

시그널 채점 조건: `signal == "buy"`

---

### 3-4. OBV 다이버전스

```python
def calc_obv_divergence(df: pd.DataFrame, window: int = 10) -> dict | None:
    """
    OBV 강세/약세 다이버전스 감지.
    window=10 (원본 N=5에서 수정 — 노이즈 방지).
    최근 두 구간(window봉씩)의 가격 피벗 vs OBV 피벗 비교.
    """
    close  = df["Close"]
    volume = df["Volume"]
    if len(df) < window * 2:
        return None

    sign = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv  = (sign * volume).cumsum()

    seg1_c = close.iloc[-(window * 2):-window]
    seg2_c = close.iloc[-window:]
    seg1_o = obv.iloc[-(window * 2):-window]
    seg2_o = obv.iloc[-window:]

    price_lower_low   = float(seg2_c.min()) < float(seg1_c.min())
    obv_higher_low    = float(seg2_o.min()) > float(seg1_o.min())
    price_higher_high = float(seg2_c.max()) > float(seg1_c.max())
    obv_lower_high    = float(seg2_o.max()) < float(seg1_o.max())

    if price_lower_low and obv_higher_low:
        divergence = "bullish"    # 가격 신저점 + OBV 상승 → 강세 다이버전스
    elif price_higher_high and obv_lower_high:
        divergence = "bearish"    # 가격 신고점 + OBV 하락 → 약세 다이버전스
    else:
        divergence = "none"

    return {
        "obv_last":   round(float(obv.iloc[-1]), 0),
        "divergence": divergence,
    }
```

시그널 채점 조건: `divergence == "bullish"`

---

### 3-5. MA 크로스 (일봉)

```python
def calc_ma_cross(
    df_daily: pd.DataFrame,
    df_hourly: pd.DataFrame | None = None,
) -> dict:
    """
    일봉 MA20/MA60 크로스 + 시간봉 MA20/MA60 크로스 (선택).
    df_hourly 없으면 hourly = None 반환 (채점 제외, UI 참고 표시용).
    """
    def _detect_cross(fast: pd.Series, slow: pd.Series) -> str:
        if len(fast) < 2 or pd.isna(fast.iloc[-1]) or pd.isna(slow.iloc[-1]):
            return "none"
        curr_above = fast.iloc[-1] > slow.iloc[-1]
        prev_above = fast.iloc[-2] > slow.iloc[-2]
        if not prev_above and curr_above:
            return "golden"
        if prev_above and not curr_above:
            return "dead"
        return "none"

    close_d  = df_daily["Close"]
    daily_cross = _detect_cross(_sma(close_d, 20), _sma(close_d, 60))

    hourly_cross = None
    if df_hourly is not None and len(df_hourly) >= 60:
        close_h = df_hourly["Close"]
        hourly_cross = _detect_cross(_sma(close_h, 20), _sma(close_h, 60))

    return {"daily": daily_cross, "hourly": hourly_cross}
```

시그널 채점 조건: `daily == "golden"` (hourly는 UI 참고 표시, 채점 미포함)

---

**완료 기준 (Phase 3 전체):**
- [ ] 각 함수 단독 호출 → NaN 없이 dict 반환 확인
- [ ] 데이터 부족 케이스 (`len(df) < 20`) → None 반환 확인
- [ ] `calc_atr_zones(df)["signal_stop"]` vs `grader.py`의 `stop_loss` 필드명 다름 확인

---

## Phase 4 — 분봉 기반 지표 2개

**파일:** `screener/indicators.py` (Phase 3에 이어 추가)

> Phase 2의 `fetch_intraday()` 완료 후 진행.

### 4-1. VWAP (15분봉)

```python
def calc_vwap(df_15m: pd.DataFrame | None) -> dict | None:
    """
    15분봉 데이터로 VWAP 계산. 날짜별 일중 초기화 적용.
    df_15m=None → None 반환 (채점 제외).
    """
    if df_15m is None or df_15m.empty:
        return None
    df = df_15m.copy()
    # timezone이 남아있으면 제거 (fetch_intraday에서 처리되나 방어 코드)
    if df.index.tzinfo is not None:
        df.index = df.index.tz_localize(None)

    df["_date"] = df.index.normalize()
    df["_tp"]   = (df["High"] + df["Low"] + df["Close"]) / 3
    df["_tpv"]  = df["_tp"] * df["Volume"]

    # 날짜별 누적합 → 일중 초기화 구현
    df["_cum_tpv"] = df.groupby("_date")["_tpv"].cumsum()
    df["_cum_vol"] = df.groupby("_date")["Volume"].cumsum()
    df["_vwap"]    = df["_cum_tpv"] / df["_cum_vol"]

    last_vwap  = float(df["_vwap"].iloc[-1])
    last_price = float(df["Close"].iloc[-1])
    if pd.isna(last_vwap):
        return None

    return {
        "vwap":   round(last_vwap, 2),
        "signal": "above" if last_price > last_vwap else "below",
    }
```

시그널 채점 조건: `signal == "above"`

---

### 4-2. MA 크로스 (시간봉) — calc_ma_cross() 확장

Phase 3의 `calc_ma_cross(df_daily, df_hourly=None)` 시그니처가 이미 `df_hourly`를 받도록 설계됨.  
Phase 4에서는 **호출부**에서 `fetch_intraday(ticker, "1h", "60d")`를 넘기는 것만 추가.

**완료 기준 (Phase 4):**
- [ ] `calc_vwap(df_15m)` → `{"vwap": float, "signal": "above"|"below"}` 반환
- [ ] `df_15m = None` → `None` 반환 (예외 없음)
- [ ] `calc_ma_cross(df_d, df_h)["hourly"]` → "golden"|"dead"|"none" 반환

---

## Phase 5 — 통합 시그널 스코어링

**파일:** `screener/signal_scorer.py` (신규 생성)

> Phase 1(CandleKit), Phase 3(일봉 지표), Phase 4(분봉 지표) 모두 완료 후 진행.

### CandleKit 통합 방식

```python
from candlekit import scan_symbol_df, CandlePatterns

# 우리가 사용할 강세 반전/지속 패턴 목록 (26개 중 선별)
_BULLISH_PATTERNS = [
    CandlePatterns.Hammer,
    CandlePatterns.BullishEngulfing,
    CandlePatterns.PiercingLine,
    CandlePatterns.MorningStar,
    CandlePatterns.MorningDojiStar,
    CandlePatterns.ThreeWhiteSoldiers,
    CandlePatterns.ThreeInsideUp,
    CandlePatterns.ThreeOutsideUp,
    CandlePatterns.BullishKicking,
    CandlePatterns.RisingThreeMethods,
    CandlePatterns.MatHold,
]

def _detect_recent_bullish(df: pd.DataFrame, lookback: int = 3) -> bool:
    """
    최근 lookback봉 안에 강세 패턴이 하나라도 있으면 True.
    컬럼명은 yfinance 기본(대문자) → lowercase 변환 후 전달.
    """
    df_ck = df[["Open", "High", "Low", "Close"]].copy()
    df_ck.columns = ["open", "high", "low", "close"]
    df_ck = df_ck.reset_index(drop=True)
    results = scan_symbol_df(df_ck, patterns=_BULLISH_PATTERNS)
    if results.empty:
        return False
    recent_idx = len(df_ck) - lookback
    return not results[results["index"] >= recent_idx].empty
```

### score_signals() 전체 구조

```python
def score_signals(
    df_daily: pd.DataFrame,
    df_hourly: pd.DataFrame | None = None,
    df_15m:   pd.DataFrame | None = None,
) -> dict:
    """
    7개 보조지표 채점. 기존 checklist와 독립.

    Returns:
        signal_grade:     "STRONG BUY" | "BUY" | "WATCH" | "NO SIGNAL"
        signal_score:     int  (가용 항목 기준)
        signal_max:       int  (None 아닌 항목 수)
        signal_breakdown: dict[str, bool | None]
        entry_low:        float | None
        entry_high:       float | None
        signal_stop:      float | None
    """
    atr    = calc_atr_zones(df_daily)
    stoch  = calc_stoch_rsi(df_daily["Close"])
    bb     = calc_bb_advanced(df_daily)
    obv    = calc_obv_divergence(df_daily)
    ma     = calc_ma_cross(df_daily, df_hourly)
    vwap   = calc_vwap(df_15m)
    candle = _detect_recent_bullish(df_daily)

    # 가격이 진입존 안에 있을 때만 ATR True
    price = float(df_daily["Close"].iloc[-1])
    atr_signal = (
        atr is not None and
        atr["entry_low"] <= price <= atr["entry_high"]
    ) if atr else None

    breakdown = {
        "atr":       atr_signal,
        "vwap":      (vwap["signal"] == "above") if vwap else None,
        "stoch_rsi": (stoch["signal"] == "buy")  if stoch else None,
        "bb_pct_b":  (bb["signal"]   == "buy")   if bb    else None,
        "obv_div":   (obv["divergence"] == "bullish") if obv else None,
        "ma_cross":  ma["daily"] == "golden",
        "candle":    candle,
    }

    # None = 데이터 없음 → 채점 제외, 분모도 줄어듦
    scored  = {k: v for k, v in breakdown.items() if v is not None}
    score   = sum(1 for v in scored.values() if v)
    maximum = len(scored)

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

**완료 기준:**
- [ ] `score_signals(df_d)` — df_hourly/df_15m 없이 → 5개 항목(vwap=None, ma_cross hourly 제외) 채점
- [ ] `score_signals(df_d, df_h, df_15)` — 7개 항목 전체 채점
- [ ] AAPL 실 데이터로 반환값 타입 확인 (signal_grade: str, score: int, breakdown: dict)
- [ ] 모든 지표 None인 극단 케이스 → `"NO SIGNAL"` 반환

---

## Phase 6 — 파이프라인 연결

**파일:** `services/screener_service.py`

> Phase 5 완료 후 진행.

기존 Step 9 (펀더멘털·외부 데이터 병렬 조회) 이후에 **Step 10** 추가:

```python
# Step 10. 시그널 스코어링 (displayable 종목에만, 병렬)
from screener.signal_scorer import score_signals
from screener.data_fetcher  import fetch_intraday

def _run_signal(r: dict) -> dict:
    tk    = r["ticker"]
    df_d  = ohlcv_map.get(tk)                        # 이미 수집된 일봉 재사용
    df_h  = fetch_intraday(tk, "1h",  "60d")
    df_15 = fetch_intraday(tk, "15m", "5d")
    return score_signals(df_d, df_h, df_15)

with ThreadPoolExecutor(max_workers=4) as ex:
    sig_futures = {
        r["ticker"]: ex.submit(_run_signal, r)
        for r in displayable
    }

for r in displayable:
    sig = sig_futures[r["ticker"]].result()
    r.update(sig)
    # r에 추가되는 키:
    # signal_grade, signal_score, signal_max, signal_breakdown,
    # entry_low, entry_high, signal_stop
    # 기존 grade, score, checklist, stop_loss는 그대로 유지
```

**완료 기준:**
- [ ] `run_analysis(["AAPL"])` 반환 dict에 `signal_grade` 키 존재 확인
- [ ] `stop_loss` (기존) vs `signal_stop` (신규) 필드 모두 존재 확인
- [ ] 기존 `grade` ("S"|"A"|"B"|"SKIP") 값 변경 없음 확인

---

## Phase 7 — UI 반영

**파일:** `api/routes/screen.py`, `static/css/screen.css`

> Phase 6 완료 후 진행.

### 7-1. `api/routes/screen.py` — 시그널 섹션 렌더러 추가

`_render_result_cards()` 내 SKIP이 아닌 종목 카드 HTML에 `_render_signal_section(r)` 호출 추가:

```python
_SIGNAL_LABELS = {
    "atr":       "ATR 진입존",
    "vwap":      "VWAP",
    "stoch_rsi": "StochRSI",
    "bb_pct_b":  "BB %B",
    "obv_div":   "OBV 다이버전스",
    "ma_cross":  "MA 크로스",
    "candle":    "캔들 패턴",
}

_GRADE_CLASS = {
    "STRONG BUY": "sig-strong-buy",
    "BUY":        "sig-buy",
    "WATCH":      "sig-watch",
    "NO SIGNAL":  "sig-nosignal",
}

def _render_signal_section(r: dict) -> str:
    grade     = r.get("signal_grade", "NO SIGNAL")
    score     = r.get("signal_score", 0)
    maximum   = r.get("signal_max", 0)
    breakdown = r.get("signal_breakdown", {})
    entry_low   = r.get("entry_low")
    entry_high  = r.get("entry_high")
    signal_stop = r.get("signal_stop")

    badge = (
        f'<span class="signal-badge {_GRADE_CLASS.get(grade, "sig-nosignal")}">'
        f'{grade} {score}/{maximum}'
        f'</span>'
    )

    entry_html = ""
    if entry_low and entry_high:
        entry_html += (
            f'<div class="entry-info">'
            f'<span class="entry-label">진입존</span>'
            f' ${entry_low:,.2f} ~ ${entry_high:,.2f}'
            f'</div>'
        )
    if signal_stop:
        entry_html += (
            f'<div class="entry-info entry-stop">'
            f'<span class="entry-label">시그널 손절</span>'
            f' ${signal_stop:,.2f}'
            f'</div>'
        )

    checks = ""
    for key, label in _SIGNAL_LABELS.items():
        val = breakdown.get(key)
        if val is None:
            icon, cls = "–", "sig-na"
        elif val:
            icon, cls = "✓", "sig-ok"
        else:
            icon, cls = "✗", "sig-bad"
        checks += f'<span class="signal-check {cls}">{label} {icon}</span>'

    return (
        f'<div class="signal-section">'
        f'{badge}{entry_html}'
        f'<div class="signal-checks">{checks}</div>'
        f'</div>'
    )
```

### 7-2. `static/css/screen.css` — 시그널 섹션 스타일

```css
/* ── 시그널 섹션 ─────────────────────────────── */
.signal-section {
    border-top: 1px solid var(--border);
    padding-top: 0.8rem;
    margin-top:  0.8rem;
}

.signal-badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    margin-bottom: 0.5rem;
}
.sig-strong-buy { background: rgba(72,187,120,0.2);  color: #68d391; }
.sig-buy        { background: rgba(154,230,180,0.15); color: #9ae6b4; }
.sig-watch      { background: rgba(236,201,75,0.15);  color: #f6e05e; }
.sig-nosignal   { background: rgba(160,174,192,0.08); color: var(--text3); }

.entry-info       { font-size: 0.78rem; color: var(--text2); margin: 0.15rem 0; }
.entry-stop       { color: #fc8181; }
.entry-label      { color: var(--text3); margin-right: 0.3rem; font-size: 0.72rem; }

.signal-checks {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-top: 0.5rem;
}
.signal-check {
    font-size: 0.7rem;
    padding: 0.12rem 0.45rem;
    border-radius: 3px;
    border: 1px solid var(--border);
}
```

**완료 기준:**
- [ ] AAPL 스캔 → 카드 하단에 시그널 배지 + 진입존 + 체크리스트 표시
- [ ] `signal_grade = "NO SIGNAL"` → 회색 배지, 진입존 없음
- [ ] SKIP 등급 카드 → 시그널 섹션 없음 (기존 SKIP 렌더링 유지)
- [ ] 기존 S/A/B/SKIP 배지, 체크리스트, 펀더멘털 배지 변경 없음

---

## 파일 변경 요약

| Phase | 파일 | 작업 |
|-------|------|------|
| 1 | `requirements.txt` | CandleKit GitHub URL 추가 |
| 2 | `screener/data_fetcher.py` | `fetch_intraday()` + `_intraday_cache` 추가 |
| 3 | `screener/indicators.py` | `calc_atr_zones`, `calc_stoch_rsi`, `calc_bb_advanced`, `calc_obv_divergence`, `calc_ma_cross` 추가 |
| 4 | `screener/indicators.py` | `calc_vwap` 추가 (Phase 3 파일 이어서) |
| 5 | `screener/signal_scorer.py` | 신규 생성 (`score_signals`, `_detect_recent_bullish`) |
| 6 | `services/screener_service.py` | Step 10 시그널 블록 추가 |
| 7 | `api/routes/screen.py` | `_render_signal_section()` 추가 + 카드에 연결 |
| 7 | `static/css/screen.css` | 시그널 섹션 스타일 추가 |

---

## 성능 예상 (displayable 10개 기준)

| 단계 | 추가 시간 | 비고 |
|------|---------|------|
| 일봉 지표 5개 | +0~1s | 기존 df 재사용 |
| 분봉 fetch (1h × 10) | +3~8s | ThreadPoolExecutor 병렬 |
| 분봉 fetch (15m × 10) | +3~8s | 위와 동시 실행 |
| CandleKit 패턴 스캔 | +0~1s | pandas 연산 |
| **합계** | **+6~17s** | 기존 대비 최대 +17s |

---

## 제약 조건

1. 기존 함수/필드 삭제 금지 — 추가만
2. `stop_loss` (grader, 비율 기반) ≠ `signal_stop` (ATR 기반) — 필드명 혼용 금지
3. 분봉 fetch는 `displayable` 종목에만 적용 (SKIP 제외)
4. 모든 신규 지표 함수: 데이터 부족 / 계산 불가 시 `None` 반환
5. `signal_scorer.py`는 `screener/` 하위에 위치
