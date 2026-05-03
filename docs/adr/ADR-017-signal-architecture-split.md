# ADR-017: 매수/매도 신호 로직을 독립 파일로 분리

**날짜:** 2026-05-02  
**상태:** 결정됨

---

## 배경

기존 `api/routes/chart.py`의 `_compute_master_markers(df)` 함수(85줄)가 매수·매도 신호 모두를 하나의 상태 머신 안에서 처리했다.

구체적 문제:
1. **상태 공유** — `in_position` 플래그가 매수/매도 조건을 상호 간섭. 데드크로스 상태가 유지되는 동안 매도 마커가 연속 표시됨.
2. **테스트 불가** — 매수 조건과 매도 조건이 같은 함수 안에 엮여 있어 각각 단독 검증 불가.
3. **파라미터 조정의 어려움** — 매수 감도를 올리면 매도 조건도 영향을 받는 경우 발생.

## 결정

`screener/buy_signal.py`와 `screener/sell_signal.py`를 별도 파일로 분리.  
`chart.py`는 두 모듈을 임포트해 결과를 날짜 기준으로 병합하는 얇은 어댑터만 유지.

```python
# api/routes/chart.py
def _merge_markers(df) -> list[dict]:
    from screener.buy_signal import compute_buy_signals
    from screener.sell_signal import compute_sell_signals
    return sorted(compute_buy_signals(df) + compute_sell_signals(df),
                  key=lambda m: m["time"])
```

## 고려한 대안

| 대안 | 기각 이유 |
|------|----------|
| 상태 머신 내 버그 수정 | 근본 구조가 상태 결합 → 같은 문제 재발 가능 |
| 클래스 기반 SignalEngine | 현재 규모에서 과도한 추상화 |
| 단일 파일 내 함수 분리 | 임포트 경계가 없어 의존성 역전 발생 가능 |

## 결과

- 매수 조건 변경 시 `buy_signal.py`만 수정, 매도에 무영향
- 두 파일 각각 `list[dict]` 반환 (동일 스키마 `{time, type, price, reason}`) → 병합 로직 단순화
- numpy 벡터 연산으로 전봉 배열 사전 계산 → 루프 최소화
