## Skill: Finviz Scraper

- **Purpose:** Finviz 스크리너 필터를 적용해 조건에 맞는 미국 주식 티커 리스트를 반환한다.
- **Inputs:** `FINVIZ_FILTERS: dict` (config.py에서 로드)
- **Outputs:** `list[str]` — 티커 리스트 (ETF 제거 완료)
- **File:** `screener/finviz_filter.py`

### Best Practices
- 필터 키를 `f"{k}_{v}"` 형식으로 조합해 Screener에 전달
- ETF 키워드(`ETF`, `FUND`, `TRUST`, `SHARES`, `INDEX`, `NOTES`, `PROSHARES`) 기반 제거
- 재시도 3회, 지수 백오프(1s, 2s, 4s) 적용
- 네트워크 실패 시 빈 리스트 반환 (caller가 처리)

### Anti-patterns
- 재시도 없이 단일 요청 → Finviz 일시 차단 시 전체 실패
- ETF 제거 없이 반환 → 채점 결과에 ETF 혼입

### Example
```python
from screener.finviz_filter import get_filtered_tickers
tickers = get_filtered_tickers()  # ["AAPL", "NVDA", ...]
```
