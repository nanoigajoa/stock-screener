# 시그널 스코어링 로직 레퍼런스

> 최종 업데이트: 2026-05-03  
> 관련 파일: `screener/signal_scorer.py`, `screener/buy_signal.py`, `screener/sell_signal.py`, `services/signal_service.py`

---

## 1. 두 시스템의 구분

| 시스템 | 목적 | 파일 | 출력 |
|--------|------|------|------|
| **스크리닝** | 종목 건강도 평가 | `checklist.py` → `grader.py` | S/A/B/SKIP 등급 |
| **매매시그널** | 진입 타이밍 판단 | `signal_scorer.py` | STRONG BUY / BUY / WATCH / NO SIGNAL |
| **차트 마커** | 과거 진입·청산 시점 시각화 | `buy_signal.py` / `sell_signal.py` | 캔들 차트 화살표 |

세 시스템은 **완전 독립**으로 동작한다. 스크리닝 등급이 S여도 시그널이 NO SIGNAL일 수 있고, 반대도 가능하다.

---

## 2. 매매시그널 전체 파이프라인

```
[watchlist.json]
      │
      ▼
signal_service.run_signal_analysis()
      │
      ├─ fetch_ohlcv()          일봉 OHLCV (6mo, TTL 캐시)
      ├─ fetch_intraday()       1시간봉 (60d)  ← Trend MA 정배열 보조
      ├─ fetch_fundamentals()   로고용 도메인 추출
      │
      │  장 중(is_market_open)이면
      └─ yf.fast_info lastPrice  실시간 가격 갱신 (5분 캐시)
            │
            ▼
      score_signals(df_daily, df_hourly)   ← signal_scorer.py
            │
            ├─ calc_atr_zones()    진입존·손절가
            ├─ calc_stoch_rsi()    StochRSI k/d + RSI
            ├─ calc_obv_divergence()  OBV MA10 vs MA30 정배열
            ├─ calc_ma_alignment()    일봉·시간봉 MA 정배열
            ├─ calc_cmf()             Chaikin Money Flow (21일)
            └─ _detect_recent_bullish()  최근 3봉 캔들 패턴
                  │
                  ▼
            4카테고리 가중 합산
                  │
                  ▼
      STRONG BUY / BUY / WATCH / NO SIGNAL
            │
            ▼
      결과 정렬 (STRONG BUY 우선, 동점 → signal_score 내림차순)
```

---

## 3. 4카테고리 스코어링 상세

모든 카테고리 점수는 **0.0 ~ 1.0** 범위 float.

### 3-1. Trend (가중치 35%)

**MA 정배열 강도 (ma_intensity)**
```
spread_pct = (MA20 - MA60) / MA60
ma_intensity = clamp(spread_pct / 0.05, 0.0, 1.0)
# 스프레드 5% 이상이면 만점, MA20 ≤ MA60이면 0점
```

**진입존 위치 (atr_ok)**
```
진입존 = MA60(하단) ~ MA20 + 0.5*ATR(상단)

가격이 진입존 안     → atr_ok = 1.0  (이상적 타이밍)
가격이 진입존 위     → atr_ok = 0.5  (늦은 진입)
가격이 진입존 아래   → atr_ok = 0.0
```

**최종:** `trend_score = (ma_intensity + atr_ok) / 2`

---

### 3-2. Momentum (가중치 25%)

**RSI 위치 점수 (rsi_score)**
```
RSI 45~65  → 1.0 - |RSI - 55| / 10   (55에서 만점 1.0, 양 끝 0.0)
RSI 35~45  → (RSI - 35) / 10 × 0.6   (과매도 회복 중)
RSI 65~75  → (75 - RSI) / 10 × 0.4   (과매수 진입 주의)
RSI < 35 / > 75 → 0.0
```

**StochRSI 과매도 탈출 보너스 (stoch_bonus)**
```
K > K_prev  AND  K_prev < 0.35
→ stoch_bonus = min((K - K_prev) / 0.05, 0.30)
```

**Z-Score 통계적 과매도 보너스 (z_bonus)**
```
z = (종가 - 20일평균) / 20일표준편차

z < -2.0 → z_bonus = 0.30  (2σ 이하 극단 과매도)
z < -1.0 → z_bonus = 0.15  (1~2σ 과매도)
```
> stoch_bonus와 z_bonus는 같은 현상을 두 각도에서 관측 → 큰 쪽 하나만 채택 (이중 계산 방지)

**최종:** `momentum_score = min(rsi_score + max(stoch_bonus, z_bonus), 1.0)`

---

### 3-3. Volume (가중치 25%)

**CMF 강도 (cmf_intensity)**
```
CMF(Chaikin Money Flow, 21일)

CMF > 0    → cmf_intensity = min(CMF / 0.15, 1.0)  (0.15 이상 = 만점)
CMF ≤ 0    → cmf_intensity = 0.0
```

**OBV 정배열 (obv_intensity)**
```
OBV_MA10 > OBV_MA30  → obv_intensity = 1.0  (수급 유입 추세)
그 외                → obv_intensity = 0.0
```

**최종:** `volume_score = (cmf_intensity + obv_intensity) / 2`

---

### 3-4. Pattern (가중치 15%)

최근 3봉 강세 캔들 패턴 탐지 후 단위 합산:

| 패턴 | 단위 | 설명 |
|------|:----:|------|
| LiquiditySweep | 1.5 | 20봉 최저가 장중 이탈 후 종가 회복 (기관 매집 신호) |
| MorningStar | 1.0 | 3봉 샛별형 |
| ThreeWhiteSoldiers | 1.0 | 3봉 연속 양봉 상승 |
| BullishEngulfing | 1.0 | 이전 음봉 몸통 완전 포함 양봉 |
| PiercingLine | 1.0 | 이전 음봉 중간선 이상 마감 |
| Hammer | 1.0 | 아래 꼬리 ≥ 2×몸통 |

```
units = Σ(각 패턴 단위)
pattern_score = min(units / 2.0, 1.0)
# LiquiditySweep 단독 → 0.75, LiquiditySweep + 1개 → 1.0
```

---

## 4. 가중 합산 & 등급 결정

```
total = trend×0.35 + momentum×0.25 + volume×0.25 + pattern×0.15
```

**확인 게이트:** 4개 카테고리 중 2개 이상이 0 초과여야 등급 부여.  
(단일 카테고리만 좋은 종목은 NO SIGNAL로 처리)

| 등급 | 조건 |
|------|------|
| STRONG BUY | total ≥ 0.60 |
| BUY | total ≥ 0.40 |
| WATCH | total ≥ 0.20 |
| NO SIGNAL | total < 0.20 또는 활성 카테고리 < 2개 |

---

## 5. 진입존 & 손절가 (ATR 기반)

```
ATR = pandas-ta atr(14)  ← Wilder EWM 방식

entry_low   = MA60                     ← 추세 하단 지지
entry_high  = MA20 + 0.5 × ATR        ← 상단 진입 버퍼
signal_stop = MA60 − 1.0 × ATR        ← 손절 기준
```

---

## 6. 차트 마커 로직

### 6-1. 매수 마커 (`buy_signal.py`)

**공통 전제:** 상승추세(MA20 > MA60) + 진입존(MA60 ≤ 가격 ≤ MA20+0.5ATR)

| 이유 | 조건 |
|------|------|
| `MA5골든` | MA5가 MA20을 상향 돌파 (단기 골든크로스) |
| `RSI+볼륨` | RSI반등 + 볼륨급증 동시 발생 |
| `RSI반등` | RSI 40~60 구간 + 2일 연속 상승 |
| `MACD전환` | MACD 히스토그램 음→양 전환 |
| `볼륨급증` | 양봉 + 거래대금 20일 평균 2배 이상 |

우선순위: `MA5골든` > `RSI+볼륨` > `RSI반등` > `MACD전환` > `볼륨급증`

마커 가격: `저가 × 0.98` (차트 아래 여백)

### 6-2. 매도 마커 (`sell_signal.py`)

포지션과 무관하게 독립 발동:

| 이유 | 조건 |
|------|------|
| `데드크로스` | MA20이 MA60을 하향 돌파 (전환일 1회) |
| `RSI과열이탈` | RSI 70 이상 상태에서 2일 연속 하락 |
| `MA20붕괴` | 가격이 MA20 위→아래 전환 + 음봉 + 거래량 1.5배 |

마커 가격: `고가 × 1.02` (차트 위 여백)

---

## 7. 스크리닝 체크리스트 (참고)

매매시그널과 독립. `/screen` 페이지 S/A/B 등급에만 사용.

| # | 항목 | 조건 |
|---|------|------|
| 1 | 이동평균선 정배열 | 가격 > MA5 > MA20 > MA60 > MA120 완전 정배열 |
| 2 | RSI(14) | RSI_IDEAL_MIN(45) ~ RSI_IDEAL_MAX(65) 이내 |
| 3 | 거래량 | 절대량 ≥ 200만 + 상대량 ≥ 평균 1.5배 |
| 4 | MACD | MACD 선 > 시그널 선 |
| 5 | 지지/저항 | MA60 ≤ 가격 ≤ MA60×1.08 (눌림목 타점) |
| 6 | 볼린저밴드 | 가격 > BB 중간선 |
| 7 | 추세 지속성 | Higher High + Higher Low 구조 (최근 20봉) |

**RSI 하드게이트:** RSI ≥ 80이면 채점 없이 즉시 SKIP
