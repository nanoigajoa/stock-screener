# ADR-014: 비율 기반 등급 계산

**날짜:** 2026-04-26
**상태:** 결정됨

---

## 배경

사용자 커스터마이징 기능으로 체크리스트 항목을 on/off할 수 있게 됨.
기존 고정 임계값(`S ≥ 6점, A ≥ 4점, B ≥ 2점`)은 일부 항목이 비활성화되면
만점(max_score)이 줄어들어 기준이 의미 없어짐.

예: MA+RSI(3점) 비활성 → max_score = 6점. S 기준 ≥6 → 사실상 만점만 S급.

## 결정

고정 점수 대신 **비율(ratio = score / max_score)** 로 등급 판단.

```python
_GRADE_RATIOS = [("S", 0.67), ("A", 0.44), ("B", 0.22)]
```

원래 기준(`6/9 ≈ 0.67`, `4/9 ≈ 0.44`, `2/9 ≈ 0.22`)을 그대로 유지하면서
활성화 항목이 몇 개든 동일한 상대적 기준 적용.

## checklist.py 변경

- `score_ticker()` 반환값에 `max_score` 추가
- `enabled_checks=None` → 전체 9점
- `enabled_checks=["ma_alignment","rsi"]` → max_score = 4점

## grader.py 변경

```python
# AS-IS
for grade, threshold in [("S", 6), ("A", 4), ("B", 2)]:
    if score >= threshold: return grade

# TO-BE
max_score = score_result.get("max_score", 9)
ratio = score / max_score
for grade, threshold in _GRADE_RATIOS:
    if ratio >= threshold: return grade
```

## 검증

| 활성 항목 | max_score | S 기준(점) | A 기준(점) |
|-----------|-----------|-----------|-----------|
| 전체 7개  | 9         | ≥ 6.03    | ≥ 3.96    |
| RSI 제외  | 7         | ≥ 4.69    | ≥ 3.08    |
| MA+RSI 제외 | 5       | ≥ 3.35    | ≥ 2.20    |
