# ADR-018: 거래대금 Spike 지표를 CMF(Chaikin Money Flow)로 교체

**날짜:** 2026-05-02  
**상태:** 결정됨

---

## 배경

기존 수급(Volume) 카테고리는 두 지표의 평균으로 계산됐다:

```
volume_score = (spike_intensity + obv_intensity) / 2
```

- `spike_intensity`: `거래대금 / 직전 20일 평균` 비율 → 1x=0.0, 2x=1.0
- `obv_intensity`: OBV_MA10 > OBV_MA30 이면 1.0, 아니면 0.0

### 실제 동작 분석

- `obv_intensity`는 OBV 정배열 여부(0 또는 1)이므로 평균 0.5에 고정
- `spike_intensity`는 2배 이상 거래대금 급증이 없으면 0.0
- 결과: `volume_score = (0.0 + 0.5) / 2 = 0.25` 고착 → 분포 없이 항상 비슷한 숫자

거래대금 spike는 이벤트성(가끔 발화)이고, OBV binary는 방향만 표시해 강도 정보가 없었다.

## 결정

`spike_intensity`를 **CMF(Chaikin Money Flow, length=21)**로 교체.

```python
cmf_intensity = 0.0
if cmf_val > 0:
    cmf_intensity = min(cmf_val / 0.15, 1.0)

volume_score = (cmf_intensity + obv_intensity) / 2
```

### CMF를 선택한 이유

| 특성 | spike | CMF |
|------|-------|-----|
| 범위 | 0~1 (이벤트성) | -1~+1 (연속값) |
| 발화 빈도 | 낮음 (2배↑ 조건) | 높음 (매일 계산) |
| 방향 정보 | 없음 (크기만) | 있음 (+ = 매수압력) |
| 강도 정보 | 있음 | 있음 |
| 기간 커버리지 | 단일 봉 | 21봉 누적 |

CMF > 0 = 매수 압력 (Accumulation), CMF < 0 = 매도 압력 (Distribution).  
0.15 임계값 근거: Chaikin 원저자 권고값 (+0.25는 강세, +0.15는 매수 구역 진입).

## 고려한 대안

| 대안 | 기각 이유 |
|------|----------|
| MFI(Money Flow Index) | RSI 계열 → momentum 카테고리와 중복 |
| VWAP 편차 | 일봉 VWAP는 당일에만 의미, 히스토리 비교 어려움 |
| spike 임계값 낮추기 | 1.5배로 낮추면 노이즈 증가, 근본 구조(이벤트성) 미해결 |

## 결과

`calc_cmf(df, length=21)` → `screener/indicators.py` 신규 함수 추가.  
`signal_scorer.py` import에서 `calc_value_spike` 제거, `calc_cmf` 추가.  
`calc_bb_advanced` 사용도 제거 (momentum을 RSI 기반으로 재설계함에 따라 BB%B 불필요).
