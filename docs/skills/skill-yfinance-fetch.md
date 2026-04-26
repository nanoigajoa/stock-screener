## Skill: yFinance OHLCV Fetch

- **Purpose:** 여러 티커의 OHLCV 데이터를 배치로 수집하고 당일 인메모리 캐싱을 적용한다.
- **Inputs:** `tickers: list[str]`
- **Outputs:** `dict[str, pd.DataFrame]` — `{ticker: OHLCV DataFrame}`
- **File:** `screener/data_fetcher.py`

### Best Practices
- `yf.download(group_by="ticker", threads=False)` — Celery 워커 내 pickle 충돌 방지
- 당일 캐싱: `_cache: dict[str, tuple[date, DataFrame]]` (프로세스 단위)
- 웹 멀티워커 환경에서는 Redis 캐시로 교체 필요
- 데이터 부족(30일 미만) 티커는 자동 skip
- `get_today_changes()`: ThreadPoolExecutor(max_workers=6) + 6초 timeout으로 병렬 조회

### Anti-patterns
- `threads=True` in Celery context → RLock pickle 오류
- 루프 내 개별 `get_today_change()` 호출 → 순차 hang 발생
- 전역 `_cache`를 멀티워커 웹 환경에서 그대로 사용 → 워커 간 캐시 미공유

### Example
```python
from screener.data_fetcher import fetch_ohlcv, get_today_changes
ohlcv_map = fetch_ohlcv(["AAPL", "MSFT"])
changes   = get_today_changes(list(ohlcv_map.keys()))
```
