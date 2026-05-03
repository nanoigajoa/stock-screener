# INDICATORS.md — 기술적 지표 계산식 & 논리 레퍼런스

> StockScope에서 사용하는 모든 기술적 지표의 정의, 계산식, 파라미터, 해석 기준.  
> 구현 위치: `screener/indicators.py`, `screener/signal_scorer.py`, `screener/buy_signal.py`, `screener/sell_signal.py`

---

## 목차

1. [이동평균선 (SMA)](#1-이동평균선-sma)
2. [RSI — Relative Strength Index](#2-rsi--relative-strength-index)
3. [MACD](#3-macd)
4. [볼린저밴드 (Bollinger Bands)](#4-볼린저밴드-bollinger-bands)
5. [ATR — Average True Range](#5-atr--average-true-range)
6. [ATR 진입존 & 손절가](#6-atr-진입존--손절가)
7. [StochRSI — Stochastic RSI](#7-stochrsi--stochastic-rsi)
8. [OBV — On-Balance Volume](#8-obv--on-balance-volume)
9. [CMF — Chaikin Money Flow](#9-cmf--chaikin-money-flow)
10. [거래대금 (Dollar Volume)](#10-거래대금-dollar-volume)
11. [Z-Score (통계적 과매도 판단)](#11-z-score-통계적-과매도-판단)
12. [추세 지속성 — Higher High / Higher Low](#12-추세-지속성--higher-high--higher-low)
13. [캔들 패턴](#13-캔들-패턴)
14. [지표 간 관계 요약](#14-지표-간-관계-요약)

---

## 1. 이동평균선 (SMA)

### 정의
단순이동평균(Simple Moving Average). 최근 N일 종가의 산술평균.

### 계산식
```
SMA(N)_t = (Close_t + Close_{t-1} + ... + Close_{t-N+1}) / N
```

### 사용 파라미터
| 기간 | 용도 |
|------|------|
| MA5 | 단기 모멘텀 (체크리스트 정배열 / 차트 매수 마커 MA5골든) |
| MA20 | 중단기 추세 기준선, 볼린저밴드 중간선 |
| MA60 | 중기 추세, 진입존 하단 기준 |
| MA120 | 장기 추세 (체크리스트 완전 정배열 판정) |

### 정배열 조건

**완전 정배열 (checklist 통과):**
```
Price > MA5 > MA20 > MA60 > MA120
```

**상승추세 (신호 공통 전제):**
```
MA20 > MA60
```

**MA5 단기 골든크로스 (차트 매수 마커):**
```
MA5_t > MA20_t  AND  MA5_{t-1} ≤ MA20_{t-1}
```

### 해석
- 단기 > 장기 이평선 → 상승 모멘텀 유지 중
- 역배열(단기 < 장기) → 하락 추세, 체크리스트에서 MA 항목 FAIL
- 정배열 강도는 `(MA20 - MA60) / MA60` 스프레드로 수치화 (signal_scorer Trend 카테고리)

---

## 2. RSI — Relative Strength Index

### 정의
일정 기간 동안의 상승폭 대비 하락폭의 비율로 과매수·과매도를 판단하는 모멘텀 지표. Wilder(1978) 고안.

### 계산식

**1단계: 일별 변화량**
```
Δ_t = Close_t - Close_{t-1}

U_t = max(Δ_t, 0)   ← 상승분
D_t = max(-Δ_t, 0)  ← 하락분
```

**2단계: Wilder 평활 지수이동평균 (EWM, com=13 → α=1/14)**
```
AvgU_t = AvgU_{t-1} × (13/14) + U_t × (1/14)
AvgD_t = AvgD_{t-1} × (13/14) + D_t × (1/14)
```

**3단계: RSI**
```
RS_t  = AvgU_t / AvgD_t
RSI_t = 100 - (100 / (1 + RS_t))
```

### 파라미터
- 기간: **14일** (Wilder 원안)

### 해석 기준

| RSI 구간 | 해석 | 시스템 처리 |
|---------|------|-----------|
| ≥ 80 | 극단 과매수 | **하드게이트: 즉시 SKIP** |
| 65~79 | 과매수 주의 | 체크리스트 RSI FAIL |
| 45~65 | 이상적 매수 구간 | 체크리스트 RSI PASS, 시그널 Momentum 최고점 |
| 35~44 | 과매도 회복 중 | 체크리스트 FAIL, 시그널 Momentum 부분 점수 |
| < 35 | 극단 과매도 | 0점 (추세 붕괴 가능성) |

**시그널 Momentum 점수 산식:**
```
RSI 45~65: rsi_score = 1.0 - |RSI - 55| / 10    (55에서 만점)
RSI 35~45: rsi_score = (RSI - 35) / 10 × 0.6
RSI 65~75: rsi_score = (75 - RSI) / 10 × 0.4
그 외:     rsi_score = 0.0
```

**차트 매수 마커 조건 (RSI반등):**
```
40 ≤ RSI_t ≤ 60  AND  RSI_t > RSI_{t-1} > RSI_{t-2}
```
→ 눌림목 구간에서 2일 연속 상승 = 모멘텀 회복 시점

---

## 3. MACD

### 정의
단기(12일) EMA와 장기(26일) EMA의 차이. 시그널선(9일 EMA)과 교차로 추세 전환 포착.

### 계산식

**EMA (지수이동평균):**
```
EMA(N)_t = Close_t × α + EMA(N)_{t-1} × (1 - α)
           단, α = 2 / (N + 1)

EMA12: α = 2/13 ≈ 0.1538
EMA26: α = 2/27 ≈ 0.0741
```

**MACD 라인:**
```
MACD_t = EMA12_t - EMA26_t
```

**시그널 라인:**
```
Signal_t = EMA9(MACD)_t    α = 2/10 = 0.2
```

**히스토그램:**
```
Hist_t = MACD_t - Signal_t
```

### 파라미터
- Fast: **12일**, Slow: **26일**, Signal: **9일**

### 해석 기준

| 조건 | 해석 | 시스템 처리 |
|------|------|-----------|
| MACD > Signal | 단기 모멘텀 우위 | 체크리스트 MACD PASS |
| MACD < Signal | 모멘텀 약화 | 체크리스트 MACD FAIL |
| Hist: 음→양 전환 | 모멘텀 회복 시작 | 차트 매수 마커 MACD전환 |

---

## 4. 볼린저밴드 (Bollinger Bands)

### 정의
이동평균선을 중심으로 표준편차 배수만큼 상·하 밴드를 그려 가격의 상대적 위치와 변동성을 파악.

### 계산식

**중간선 (MA20):**
```
Middle_t = SMA(20)_t
```

**표준편차:**
```
σ_t = √[ Σ(Close_{t-i} - Middle_t)² / 20 ]   (i = 0..19)
```

**상단 / 하단:**
```
Upper_t = Middle_t + 2 × σ_t
Lower_t = Middle_t - 2 × σ_t
```

**%B (밴드 내 가격 위치, 0~1):**
```
%B_t = (Close_t - Lower_t) / (Upper_t - Lower_t)
```

**밴드폭 (변동성 수준):**
```
BandWidth_t = (Upper_t - Lower_t) / Middle_t
```

### 파라미터
- 기간: **20일**, 표준편차 배수: **2σ**

### 해석 기준

| 조건 | 해석 | 시스템 처리 |
|------|------|-----------|
| Close > Middle | 강세 국면 | 체크리스트 볼린저 PASS |
| Close < Middle | 약세 국면 | 체크리스트 볼린저 FAIL |
| %B < 0.20 | 하단 근처 과매도 | calc_bb_advanced: signal = "buy" |
| %B > 0.80 | 상단 근처 과매수 | calc_bb_advanced: signal = "sell" |

---

## 5. ATR — Average True Range

### 정의
하루 동안의 실질 가격 변동폭. 갭 구간까지 포함하는 변동성 측정 지표. Wilder(1978) 고안.

### 계산식

**True Range (단일 봉):**
```
TR_t = max(
    High_t  - Low_t,           ← 당일 고저 폭
    |High_t - Close_{t-1}|,    ← 갭 포함 상단
    |Low_t  - Close_{t-1}|     ← 갭 포함 하단
)
```

**ATR (Wilder EWM, com=13 → α=1/14):**
```
ATR_t = ATR_{t-1} × (13/14) + TR_t × (1/14)
```
> ⚠️ pandas-ta의 `atr(length=14)` 사용. 단순 롤링 평균(SMA)이 아닌 **Wilder EWM**이므로 동일 기간이라도 값이 다름.

### 파라미터
- 기간: **14일**

### 용도
- 진입존 상단 버퍼 계산
- 손절가 기준 (MA60 - 1.0×ATR)
- `buy_signal.py` 진입존 판단

---

## 6. ATR 진입존 & 손절가

### 정의
MA60(중기 추세 지지선)을 하단, MA20 + 0.5×ATR을 상단으로 하는 눌림목 매수 구간.

### 계산식
```
entry_low   = MA60                     ← 중기 추세 하단 지지
entry_high  = MA20 + 0.5 × ATR(14)    ← 상단 버퍼
signal_stop = MA60 - 1.0 × ATR(14)    ← 손절 기준
```

### 진입존 해석
```
가격이 entry_low ~ entry_high 안 → 상승추세 내 눌림목 = 이상적 진입 타이밍
가격이 entry_high 위             → 이미 돌파한 뒤 = 늦은 추격 진입
가격이 entry_low 아래            → 지지 이탈 = 진입 보류
```

**시그널 Trend 카테고리 내 atr_ok 산식:**
```
entry_low ≤ price ≤ entry_high  → atr_ok = 1.0
price > entry_high              → atr_ok = 0.5
price < entry_low               → atr_ok = 0.0
```

### 공통 전제 (매수 마커)
```
uptrend = MA20 > MA60
in_zone = entry_low ≤ Close ≤ entry_high
```
두 조건이 모두 참인 봉에서만 매수 마커 이유 조건을 검사.

---

## 7. StochRSI — Stochastic RSI

### 정의
RSI 값에 Stochastic 공식을 다시 적용해 RSI의 과매수/과매도 민감도를 높인 지표.

### 계산식

**1단계: RSI(14) 계산** (2번 항목 참고)

**2단계: Stochastic 적용 (기간 14)**
```
StochRSI_t = (RSI_t - min(RSI, 14기간)) / (max(RSI, 14기간) - min(RSI, 14기간))
```

**3단계: K선 (3일 SMA 평활)**
```
K_t = SMA3(StochRSI)_t   → 0~1 정규화 (pandas-ta 결과 ÷ 100)
```

**4단계: D선 (K의 3일 SMA)**
```
D_t = SMA3(K)_t
```

### 파라미터
- RSI 기간: **14**, Stoch 기간: **14**, K 평활: **3**, D 평활: **3**

### 해석 기준

| 조건 | 해석 |
|------|------|
| K < 0.30 | 과매도 구간 |
| K > 0.70 | 과매수 구간 |
| K > K_prev AND K_prev < 0.35 | 과매도 탈출 상승 → StochRSI 보너스 |
| K < D (과매수권) | 하향 전환 시그널 |

**시그널 Momentum 보너스 (stoch_bonus):**
```
K_t > K_{t-1}  AND  K_{t-1} < 0.35
→ stoch_bonus = min((K_t - K_{t-1}) / 0.05, 0.30)
```
0.05 상승마다 +0.30의 보너스, 최대 0.30 상한.

---

## 8. OBV — On-Balance Volume

### 정의
거래량에 방향성(+/-)을 부여해 누적한 수급 흐름 지표. Joe Granville(1963) 고안.

### 계산식
```
OBV_t =
  OBV_{t-1} + Volume_t    if Close_t > Close_{t-1}  ← 상승봉: 매수세
  OBV_{t-1} - Volume_t    if Close_t < Close_{t-1}  ← 하락봉: 매도세
  OBV_{t-1}               if Close_t = Close_{t-1}  ← 보합: 변화 없음
```

**MA 정배열 (추세 판단):**
```
OBV_MA10 = SMA10(OBV)
OBV_MA30 = SMA30(OBV)

OBV_MA10 > OBV_MA30  → "bullish" (수급 유입 추세)
OBV_MA10 < OBV_MA30  → "bearish" (수급 이탈 추세)
```
> 단일 값 비교가 아닌 이동평균 정배열을 사용해 일시적 스파이크에 의한 오신호 방지.

### 시그널 Volume 카테고리 내 obv_intensity:
```
"bullish" → obv_intensity = 1.0
그 외      → obv_intensity = 0.0
```

---

## 9. CMF — Chaikin Money Flow

### 정의
일정 기간 동안 거래량 가중 자금 흐름의 누적 강도. Marc Chaikin 고안.  
범위: -1.0 ~ +1.0.

### 계산식

**Money Flow Multiplier (MFM):**
```
MFM_t = ((Close_t - Low_t) - (High_t - Close_t)) / (High_t - Low_t)
      = (2 × Close_t - High_t - Low_t) / (High_t - Low_t)
```
- MFM = +1.0: 고가 마감 (강한 매수)
- MFM = -1.0: 저가 마감 (강한 매도)
- MFM = 0: 중간 마감

**Money Flow Volume (MFV):**
```
MFV_t = MFM_t × Volume_t
```

**CMF (기간 N = 21일):**
```
CMF_t = Σ(MFV_{t-i}) / Σ(Volume_{t-i})    i = 0..N-1
```

### 파라미터
- 기간: **21일**

### 해석 기준

| CMF 값 | 해석 | 시스템 처리 |
|--------|------|-----------|
| ≥ +0.15 | 강한 매수 압력 | cmf_intensity = 1.0 (만점) |
| 0 ~ +0.15 | 완만한 매수 | cmf_intensity = CMF / 0.15 (선형) |
| ≤ 0 | 매도 압력 | cmf_intensity = 0.0 |

**시그널 Volume 카테고리 내 cmf_intensity:**
```
cmf_intensity = clamp(CMF / 0.15, 0.0, 1.0)    if CMF > 0
              = 0.0                               if CMF ≤ 0
```

---

## 10. 거래대금 (Dollar Volume)

### 정의
주가 × 거래량. 단순 거래량(주수)보다 실질 자금 규모를 반영.

### 계산식
```
DollarVolume_t = Close_t × Volume_t
```

**20일 평균 (전일까지):**
```
AvgDollarVolume_t = mean(DollarVolume_{t-20} ... DollarVolume_{t-1})
```
> `shift(1).rolling(20)` — 당일 값을 제외해 자기참조 방지.

**상대 거래대금 비율:**
```
Ratio_t = DollarVolume_t / AvgDollarVolume_t
```

### 임계값 적용

**스크리닝 체크리스트 거래량 항목:**
```
abs_ok = Volume_t ≥ 2,000,000    ← 절대 거래량 200만 주 이상
rel_ok = Ratio_t ≥ 1.5           ← 평균 대비 1.5배 이상
volume_pass = abs_ok AND rel_ok
```

**차트 매수 마커 볼륨급증 조건:**
```
Ratio_t ≥ 2.0  AND  Close_t > Open_t  (양봉)
```
→ 평균의 2배 거래대금 + 양봉 = 강한 매수세 유입 판단.

---

## 11. Z-Score (통계적 과매도 판단)

### 정의
현재 종가가 최근 20일 평균에서 얼마나 벗어났는지를 표준편차 단위로 표현.

### 계산식
```
μ  = mean(Close_{t-19} ... Close_t)    ← 20일 평균
σ  = std(Close_{t-19} ... Close_t)     ← 20일 표준편차 (ddof=1)
Z  = (Close_t - μ) / σ
```

### 해석 기준

| Z-Score | 해석 | 시그널 보너스 |
|---------|------|------------|
| Z < -2.0 | 극단적 과매도 (2σ 이하) | z_bonus = 0.30 |
| Z < -1.0 | 보통 과매도 (1~2σ) | z_bonus = 0.15 |
| Z ≥ -1.0 | 정상 범위 | z_bonus = 0.0 |

StochRSI 보너스(stoch_bonus)와 **동일 현상을 다른 각도에서 측정**하므로, 둘 중 큰 값만 채택해 이중 계산 방지:
```
momentum_score = min(rsi_score + max(stoch_bonus, z_bonus), 1.0)
```

---

## 12. 추세 지속성 — Higher High / Higher Low

### 정의
최근 20봉을 전반부/후반부로 나눠 고점과 저점이 각각 높아지는지 확인. 건강한 상승추세의 구조적 조건.

### 계산식
```
recent = 최근 20봉
first_half  = recent[0:10]
second_half = recent[10:20]

higher_high = max(second_half.High)  > max(first_half.High)
higher_low  = min(second_half.Low)   > min(first_half.Low)

trend_pass = higher_high AND higher_low
```

### 해석
- 두 조건 모두 참 → 상승 추세 구조 유지 (체크리스트 추세 지속성 PASS)
- 둘 중 하나라도 거짓 → 추세 약화 또는 횡보 (FAIL)

---

## 13. 캔들 패턴

`signal_scorer.py`의 `_detect_recent_bullish()` 함수에서 최근 **3봉** 내 감지.  
Pattern 카테고리에 반영 (가중치 15%).

### 패턴별 계산 조건

---

### Hammer (망치형)
**의미:** 매도세가 강했으나 매수세가 회복. 저점 반등 신호.

```
body       = |Close - Open|
range      = High - Low
upper_wick = High - max(Close, Open)
lower_wick = min(Close, Open) - Low

조건:
  body > 0
  lower_wick ≥ 2 × body    ← 아래 꼬리가 몸통의 2배 이상
  upper_wick ≤ body         ← 위 꼬리는 몸통 이하
  body / range < 0.30       ← 몸통이 전체 범위의 30% 미만
```

---

### Bullish Engulfing (상승 장악형)
**의미:** 전봉 하락을 완전히 덮는 상승봉. 강한 매수 전환.

```
조건:
  Close_{t-1} < Open_{t-1}      ← 이전 봉: 음봉
  Close_t > Open_t               ← 현재 봉: 양봉
  Open_t  ≤ Close_{t-1}          ← 현재 시가 ≤ 이전 종가 (갭다운 허용)
  Close_t ≥ Open_{t-1}           ← 현재 종가 ≥ 이전 시가 (완전 포함)
```

---

### Piercing Line (관통형)
**의미:** 하락 중 반등. 이전 음봉 중간선 위로 마감.

```
prev_mid = (Open_{t-1} + Close_{t-1}) / 2

조건:
  Close_{t-1} < Open_{t-1}       ← 이전 봉: 음봉
  Close_t > Open_t                ← 현재 봉: 양봉
  Open_t < Close_{t-1}            ← 갭다운 시작
  Close_t > prev_mid              ← 이전 봉 중간선 위 마감
```

---

### Morning Star (샛별형, 3봉)
**의미:** 하락 추세 바닥에서의 반전. 3봉 조합 패턴.

```
봉 구성: [-2] 음봉(큰 몸통) | [-1] 소체 | [0] 양봉(큰 몸통)

b1 = |Close_{t-2} - Open_{t-2}|    ← 첫 봉 몸통
b2 = |Close_{t-1} - Open_{t-1}|    ← 중간 봉 몸통
b3 = |Close_t - Open_t|             ← 마지막 봉 몸통
mid_of_first = (Open_{t-2} + Close_{t-2}) / 2

조건:
  Close_{t-2} < Open_{t-2}         ← 첫 봉: 음봉
  b2 < b1 × 0.5                    ← 중간 봉: 첫 봉 절반 이하 소체
  Close_t > Open_t                  ← 마지막 봉: 양봉
  Close_t ≥ mid_of_first           ← 마지막 봉이 첫 봉 중간 이상 회복
  b3 > b1 × 0.5                    ← 마지막 봉 몸통이 충분히 큼
```

---

### Three White Soldiers (적삼병, 3봉)
**의미:** 3봉 연속 강한 양봉 상승. 강한 매수세 지속.

```
조건:
  Close_{t-2} > Open_{t-2}         ← 3봉 모두 양봉
  Close_{t-1} > Open_{t-1}
  Close_t > Open_t
  Close_t > Close_{t-1} > Close_{t-2}    ← 종가 연속 상승
  Open_{t-1} ≥ Open_{t-2}         ← 각 봉의 시가가 전봉 몸통 내에서 시작
  Open_t ≥ Open_{t-1}
```

---

### Liquidity Sweep (유동성 스윕) ★ 최강 신호 (1.5단위)
**의미:** 기관이 개인의 손절 물량을 흡수한 뒤 급반등. 가장 강한 매집 신호.

```
pool = min(Low_{t-20} ... Low_{t-1})    ← 직전 20봉 최저가 (현봉 제외)

조건:
  Low_t < pool     ← 장중에 20봉 저점을 이탈 (개인 손절 유발)
  Close_t > pool   ← 종가는 20봉 저점 위로 회복 (기관 매집 완료)
```

---

### 패턴 단위 및 점수 환산

| 패턴 | 단위 |
|------|:----:|
| LiquiditySweep | 1.5 |
| 그 외 모든 패턴 | 1.0 |

```
units         = Σ(각 패턴 단위)
pattern_score = min(units / 2.0, 1.0)

예:
  패턴 없음               → 0.0
  Hammer                  → 0.5
  BullishEngulfing        → 0.5
  Hammer + Engulfing      → 1.0
  LiquiditySweep          → 0.75
  LiquiditySweep + Hammer → 1.0 (상한)
```

---

## 14. 지표 간 관계 요약

```
┌──────────────────────────────────────────────────────────────┐
│                  시스템 내 지표 사용 맵                        │
├──────────────────┬───────────────────────────────────────────┤
│ 스크리닝 체크리스트 │  사용 지표                               │
│ (checklist.py)    │                                           │
│  MA 정배열        │  SMA 5/20/60/120                          │
│  RSI              │  RSI(14) — Wilder EWM                    │
│  거래량           │  Dollar Volume + 절대·상대 이중 조건       │
│  MACD             │  EMA 12/26/9                              │
│  지지/저항        │  SMA60 ± 8% 범위                          │
│  볼린저밴드       │  BB(20, 2σ) 중간선                        │
│  추세 지속성      │  Higher High / Higher Low (20봉)          │
├──────────────────┼───────────────────────────────────────────┤
│ 시그널 스코어링   │  사용 지표                                 │
│ (signal_scorer)   │                                           │
│  Trend (35%)     │  SMA 20/60 정배열 스프레드 + ATR 진입존    │
│  Momentum (25%)  │  RSI(14) 위치 + StochRSI 탈출 + Z-Score   │
│  Volume (25%)    │  CMF(21) + OBV MA10/MA30 정배열            │
│  Pattern (15%)   │  6종 캔들 패턴                             │
├──────────────────┼───────────────────────────────────────────┤
│ 차트 마커         │  사용 지표                                 │
│ 매수 (buy_signal) │  SMA 20/60/5, ATR(14) 진입존, RSI(14),   │
│                  │  MACD 히스토그램, Dollar Volume             │
│ 매도 (sell_signal)│  SMA 20/60 데드크로스, RSI(14),           │
│                  │  Dollar Volume 1.5배, MA20 붕괴             │
└──────────────────┴───────────────────────────────────────────┘
```

### 계산 라이브러리
모든 지표는 **pandas-ta** 기반으로 계산 (`df.ta.*`).  
ATR과 StochRSI는 pandas-ta의 **Wilder EWM** 방식 사용 — 단순 롤링 평균(SMA)과 결과가 다르므로 외부 검증 시 주의.
