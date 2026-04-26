## Skill: Technical Indicators (pandas-ta)

- **Purpose:** OHLCV DataFrame에서 7개 기술적 지표를 계산해 채점에 필요한 수치 dict를 반환한다.
- **Inputs:** `df: pd.DataFrame` (OHLCV, 최소 30일)
- **Outputs:** `dict | None` — 지표 수치 dict, 계산 실패 시 None
- **File:** `screener/indicators.py`

### 계산 지표
| 지표 | 파라미터 | dict 키 |
|------|---------|---------|
| 이동평균 | SMA 5/20/60/120 | `ma5`, `ma20`, `ma60`, `ma120` |
| RSI | 14 | `rsi` |
| MACD | 12/26/9 | `macd`, `macd_signal`, `macd_hist` |
| 볼린저밴드 | 20/2 | `bb_upper`, `bb_middle`, `bb_lower` |
| 거래량 MA | 20 | `vol_ma20` |
| 지지/저항 | 최근 20봉 | `support`, `resistance` |
| 추세 | HH/HL | `higher_high`, `higher_low` |

### Best Practices
- pandas-ta 컬럼명을 `startswith("BBU_")` 동적 탐색으로 버전 호환성 확보
- MACD 컬럼도 동일하게 `startswith("MACD_")` 탐색
- 계산 실패 시 `None` 반환 → caller에서 skip 처리
- 순수 함수 — I/O 없음, 상태 없음 → 웹/CLI 모두 그대로 사용

### Anti-patterns
- 컬럼명 하드코딩 (`"BBU_20_2.0"`) → pandas-ta 버전 변경 시 KeyError

### Example
```python
from screener.indicators import calculate_indicators
ind = calculate_indicators(df)
if ind is None:
    return  # 데이터 부족 등
price = ind["price"]
rsi   = ind["rsi"]
```
