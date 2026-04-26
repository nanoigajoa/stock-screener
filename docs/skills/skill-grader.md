## Skill: Stock Grader

- **Purpose:** 체크리스트 채점 결과를 S/A/B/SKIP 등급으로 분류하고 목표가/손절을 계산한다.
- **Inputs:** `score_result: dict`, `ticker: str`, `price: float`
- **Outputs:** `dict` — StockResult (등급, 점수, 진입전략, 목표가, 손절)
- **File:** `screener/grader.py`

### 등급 기준
| 등급 | 최소 점수 | 진입 전략 |
|------|---------|---------|
| S | 6 | 즉시 전량 진입 가능 |
| A | 4 | 분할 진입 검토 (1차 50% → 조건 확인 후 2차 50%) |
| B | 2 | 대기 — 조건 미충족 |
| SKIP | 0 | 진입 금지 |

### 목표가/손절 공식
```
target_1  = price × 1.08  (+8%)
target_2  = price × 1.15  (+15%)
stop_loss = price × 0.85  (-15%)
```

### Best Practices
- `hard_skip=True`이면 바로 SKIP 반환 (목표가/손절 None)
- 등급 임계값은 `_GRADE_THRESHOLDS` 리스트로 관리 → 수정 용이
- 순수 함수 — I/O 없음, 상태 없음 → 웹/CLI 모두 그대로 사용

### Anti-patterns
- 임계값 하드코딩 — config에서 관리해야 변경 용이

### Example
```python
from screener.grader import grade
result = grade(score_result, "AAPL", 175.0)
print(result["grade"])     # "S"
print(result["target_1"])  # 189.0
```
