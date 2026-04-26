## Skill: Checklist Scorer

- **Purpose:** 기술적 지표 dict를 받아 7개 항목을 가중치 기반으로 채점한다.
- **Inputs:** `ind: dict` (indicators dict)
- **Outputs:** `dict` — `{items, total_score, hard_skip, hard_skip_reason}`
- **File:** `screener/checklist.py`

### 채점 항목 (최대 9점)
| # | 항목 | 키 | 최대 점수 |
|---|------|---|---------|
| 1 | MA 정배열 | `ma_alignment` | 2 (가변: 완전=2, 단기=1) |
| 2 | RSI 45~65 | `rsi` | 2 |
| 3 | 거래량 이중 조건 | `volume` | 1 |
| 4 | MACD 골든크로스 | `macd` | 1 |
| 5 | 지지선 위 반등 | `support` | 1 |
| 6 | 볼린저밴드 중간선 위 | `bollinger` | 1 |
| 7 | HH + HL 추세 | `trend` | 1 |

### Best Practices
- RSI ≥ 80 하드게이트: 즉시 `hard_skip=True` 반환, 나머지 채점 스킵
- MA 정배열은 가변 점수 (완전 정배열 2점, 단기만 1점)
- 거래량: 절대량(≥200만) + 상대량(≥1.5배) 이중 조건
- 각 항목에 `pass`(표시용) + `score`(점수) 분리 저장
- `total_score = sum(item["score"] for item in items.values())`
- 순수 함수 — I/O 없음, 상태 없음

### Anti-patterns
- `sum(weight if pass)` 방식 → MA 부분점수 반영 불가
- RSI 하드게이트 없이 전체 채점 → 과매수 종목 허통

### Example
```python
from screener.checklist import score_ticker
result = score_ticker(ind)
if result["hard_skip"]:
    print(result["hard_skip_reason"])  # "RSI 82.3 ≥ 80 (과매수)"
else:
    print(result["total_score"])       # 0~9
```
