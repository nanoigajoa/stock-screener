# Phase: 매매시그널 품질 고도화 2 — 아키텍처 분리 + 지표 재설계

> **작성일:** 2026-05-02 | **완료:** 2026-05-02  
> **상태:** ✅ 완료  
> **선행 Phase:** phase-service-split (Phase 0~6), Phase Signal QA (2026-05-01)

---

## 배경 및 동기

Phase Signal QA(2026-05-01)에서 6종 구조적 버그를 수정했지만 실운영 중 다음 문제가 지속됐다:

1. **점수 집중 현상** — trend/momentum/volume/pattern 4개 카테고리가 비슷한 숫자를 반환.  
   진단: momentum은 StochRSI < 0.3(과매도)만 점수를 주는데 trend는 MA 정배열(상승 추세)을 요구 →  
   *과매도 + 상승 추세* 는 거의 공존 불가 → momentum이 항상 0, volume spike는 드물어 항상 0.5.

2. **차트 마커 신뢰성 문제** — 매수 마커 직후 하락, 매도 마커 직후 상승하는 케이스가 목격됨.  
   진단: 기존 `_compute_master_markers()`가 포지션 상태 머신으로 "데드크로스 상태가 유지되는 동안" 매도를 연속 표시했고, 단일 파일 내 85줄 로직이 조건 간 간섭을 일으킴.

3. **신호 품질 지표 부재** — 거래대금 spike와 OBV만으로는 실제 자금 유입/유출 방향을 정량화하기 어려움.

---

## 목표

| 목표 | 측정 기준 |
|------|----------|
| 차트 마커 논리 분리 | buy_signal.py / sell_signal.py 독립 실행, 서로 의존 없음 |
| 점수 분산 확보 | 4개 카테고리가 독립적으로 0~1 사이 연속값을 생성 |
| 신호 품질 향상 | CMF·Z-Score·LiquiditySweep 지표 추가로 커버리지 확장 |
| 마커 호버 UX | 마커 위 커서 → 이유·날짜·가격 툴팁 표시 |

---

## 구현 내용

### 1. 차트 마커 아키텍처 분리 (ADR-017)

**변경 전:** `api/routes/chart.py` 내 `_compute_master_markers(df)` — 85줄 상태 머신  
**변경 후:** 두 독립 모듈 + 단순 병합 함수

```
screener/buy_signal.py   ← 매수 조건만 담당
screener/sell_signal.py  ← 매도 조건만 담당
                               ↓
api/routes/chart.py  →  _merge_markers(df)
                           buy + sell → 날짜 정렬 병합
```

#### `screener/buy_signal.py`

numpy 벡터 연산으로 전봉 OHLCV 배열 사전 계산 후 조건 마스킹:

```python
# 매수 조건: 상승추세 + 진입존 + (RSI 모멘텀 OR 거래대금 2배↑ + 양봉)
rsi_mom = (rsi >= 40) & (rsi <= 60) & (rsi > rsi_prev) & (rsi_prev > rsi_prev2)
vol_spk = (value / avg_value >= 2.0) & is_bull
buy_cond = valid & uptrend & in_zone & (rsi_mom | vol_spk)
```

반환: `list[dict]` — `{time, type: "buy", price, reason}`

#### `screener/sell_signal.py`

세 가지 조건 모두 **이벤트 전환(transition)** 방식 — 상태 지속이 아닌 교차 당일만 발화:

| 조건 | 로직 |
|------|------|
| Dead Cross | `MA20 < MA60` **AND** 직전봉 `MA20 ≥ MA60` |
| RSI 과매수 이탈 | 2봉 전 RSI ≥ 70, 이후 2봉 연속 하락 |
| MA20 하방 이탈 | 종가 MA20 밑으로 교차 + 음봉 + 거래대금 1.5배↑ |

```python
dead_cross  = (m20 < m60) & (m20_prev >= m60_prev)
rsi_exit    = (rsi_prev2 >= 70) & (rsi_prev < rsi_prev2) & (rsi < rsi_prev)
ma20_break  = (c < m20) & (c_prev >= m20_prev) & is_bear & vol_up
```

반환: `list[dict]` — `{time, type: "sell", price, reason}`

#### `api/routes/chart.py` 변경

```python
# 변경 전 (85줄 상태 머신)
def _compute_master_markers(df) -> list[dict]: ...

# 변경 후 (6줄)
def _merge_markers(df) -> list[dict]:
    from screener.buy_signal import compute_buy_signals
    from screener.sell_signal import compute_sell_signals
    return sorted(compute_buy_signals(df) + compute_sell_signals(df),
                  key=lambda m: m["time"])
```

---

### 2. 모멘텀 점수 재설계 — RSI 종형 곡선 (ADR-019)

**문제:** 기존 StochRSI < 0.3 조건은 *과매도 구간에서만* 점수 발생 → 상승 추세 종목에서 항상 0점.

**해결:** RSI 자체를 주 지표로 전환, "건강한 상승 모멘텀 구간"에서 최고점:

```
RSI 구간    점수 공식                   예시
─────────   ──────────────────────      ───────────────
45 ~ 65     1.0 − |rsi − 55| / 10       rsi=55 → 1.0
                                         rsi=45 → 0.0
35 ~ 45     (rsi − 35) / 10 × 0.6       rsi=40 → 0.30
65 ~ 75     (75 − rsi) / 10 × 0.4       rsi=70 → 0.20
< 35 / > 75 0.0                         극단 구간 제외
```

**보조 보너스 (둘 중 강한 쪽 채택, 이중 계산 방지):**

```python
# StochRSI 방향 보너스: 과매도권(k_prev < 0.35)에서 상승 중
stoch_bonus = min((k - k_prev) / 0.05, 0.3) if k > k_prev and k_prev < 0.35

# Z-Score 과매도 보너스: 통계적 저점 확인
z = (close[-1] - close[-20:].mean()) / close[-20:].std()
z_bonus = 0.30 if z < -2.0 else 0.15 if z < -1.0 else 0.0

momentum_score = min(rsi_score + max(stoch_bonus, z_bonus), 1.0)
```

---

### 3. 수급 지표 교체 — CMF 도입 (ADR-018)

**문제:** 거래대금 spike(ratio ≥ 2.0 = 1.0)는 발화 빈도가 낮아 volume_score가 항상 0.5(OBV 0/1 평균).

**해결:** CMF(Chaikin Money Flow)로 교체 — 자금 유입/유출을 -1~+1 연속값으로 표현:

```python
cmf_intensity = 0.0
if cmf_val > 0:
    cmf_intensity = min(cmf_val / 0.15, 1.0)  # 0.15 이상 = 만점
volume_score = (cmf_intensity + obv_intensity) / 2
```

| 값 범위 | 의미 |
|---------|------|
| +0.15 이상 | 강한 매수 압력 → `cmf_intensity = 1.0` |
| 0 ~ +0.15 | 완만한 매수 → 선형 증가 |
| 음수 | 매도 압력 → 0점 |

---

### 4. LiquiditySweep 패턴 추가

**정의:** 직전 20봉 최저가(liquidity pool)를 장중 일시 이탈한 뒤 종가로 회복하는 캔들.  
기관이 개인의 손절 물량을 흡수(sweep)한 후 급반등하는 강한 매집 신호.

```python
pool = min(l[i - 20 : i])   # 직전 20봉 최저가
if l[i] < pool and c[i] > pool:
    detected.append("LiquiditySweep")
```

**패턴 가중치 체계:**

```python
units = sum(1.5 if p == "LiquiditySweep" else 1.0 for p in patterns)
pattern_score = min(units / 2.0, 1.0)
```

| 패턴 조합 | 단위 합 | 점수 |
|---------|--------|------|
| LiquiditySweep 단독 | 1.5 | 0.75 |
| LiquiditySweep + 1개 | 2.5 | 1.0 |
| 일반 패턴 2개 | 2.0 | 1.0 |
| 일반 패턴 1개 | 1.0 | 0.5 |

---

### 5. 마커 호버 툴팁 (signals.js + signals.css)

LWC v4의 `subscribeCrosshairMove` 이벤트를 사용, 마커 날짜와 커서 날짜를 비교해 툴팁 표시:

```javascript
chart.subscribeCrosshairMove(param => {
  const timeStr = _timeToStr(param.time);  // BusinessDay → "YYYY-MM-DD"
  const marker  = _allMarkers.find(m => m.time === timeStr);
  if (!marker) { tooltip.style.display = 'none'; return; }
  tooltip.innerHTML =
    `<div class="mt-type">${isBuy ? '▲ BUY' : '▼ SELL'}</div>` +
    `<div class="mt-reason">${marker.reason}</div>` +
    `<div class="mt-meta">${timeStr} · $${marker.price.toFixed(2)}</div>`;
  tooltip.style.display = 'block';
});
```

**주의:** LWC v4에서 `param.time`은 string `"YYYY-MM-DD"`가 아닌  
`{year, month, day}` BusinessDay 객체로 반환됨 → `_timeToStr()` 변환 헬퍼 필요.

---

## 변경 파일 요약

| 파일 | 상태 | 주요 변경 |
|------|------|---------|
| `screener/buy_signal.py` | 신규 | numpy 벡터화 매수 조건 엔진 |
| `screener/sell_signal.py` | 신규 | 3종 전환 이벤트 매도 조건 엔진 |
| `api/routes/chart.py` | 변경 | `_compute_master_markers()` → `_merge_markers()` |
| `screener/indicators.py` | 변경 | `calc_cmf()` 추가, `calc_stoch_rsi` k_prev/rsi 반환, `calc_ma_alignment` ma20/ma60 값 반환 |
| `screener/signal_scorer.py` | 변경 | RSI 종형 모멘텀, CMF 수급, LiquiditySweep, Z-Score |
| `templates/signals.html` | 변경 | `#marker-tooltip` div 추가 |
| `static/css/signals.css` | 변경 | `.marker-tooltip`, `.type-buy`, `.type-sell` 스타일 |
| `static/js/signals.js` | 변경 | `_timeToStr()`, `subscribeCrosshairMove` 툴팁 로직 |

---

## ADR 목록

| ID | 결정 |
|----|------|
| [ADR-017](../adr/ADR-017-signal-architecture-split.md) | 매수/매도 신호 파일 분리 |
| [ADR-018](../adr/ADR-018-cmf-over-spike.md) | CMF로 거래대금 spike 교체 |
| [ADR-019](../adr/ADR-019-rsi-momentum-redesign.md) | RSI 종형 곡선 모멘텀 재설계 |

---

## 미구현 항목

| 항목 | 이유 | 향후 방향 |
|------|------|----------|
| AVWAP (Anchored VWAP) | 앵커 기준점 자동 선택 알고리즘 복잡도 높음 | 별도 Phase로 분리 (사용자 선택 앵커 구현 필요) |
