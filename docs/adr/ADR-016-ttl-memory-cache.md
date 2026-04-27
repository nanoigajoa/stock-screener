# ADR-016: TTL 기반 메모리 캐시 패턴

**날짜:** 2026-04-28
**상태:** 결정됨

---

## 배경

외부 API 4종 각각 TTL이 다름 (7일, 24h). 기존 `fundamental_fetcher`의
`(ticker, date)` 키 패턴은 당일 캐시만 지원 → 소스별 TTL 미세 조정 불가.

## 결정

**datetime 비교 기반 TTL 패턴** 표준화:

```python
from datetime import datetime

_cache: dict[str, tuple[any, datetime]] = {}
_TTL = 86400  # 소스별 상이

def _is_fresh(key: str) -> bool:
    if key not in _cache:
        return False
    _, fetched_at = _cache[key]
    return (datetime.now() - fetched_at).total_seconds() < _TTL

def get_data(key: str):
    if not _is_fresh(key):
        _fetch(key)
    return _cache.get(key, (None, None))[0]
```

## TTL 결정 근거

| 소스 | TTL | 이유 |
|------|-----|------|
| Google Trends | 24h | 일간 단위 변화, 과도한 API 호출 방지 |
| FRED 매크로 | 7일 | 월간 지표, 잦은 갱신 불필요 |
| 의원거래 | 24h | 공시 지연 존재, 실시간 불필요 |
| SEC Form 4 | 24h | EDGAR 공시 처리 지연 (1~2일) |
| OHLCV | 당일 (date key) | 장 마감 후 완성, 당일 재사용 안전 |
| 펀더멘털 | 당일 (date key) | yfinance 기준, 당일 재조회 불필요 |

## Render 슬립 대응

무료 티어 슬립 시 메모리 캐시 소멸 → 복귀 후 첫 요청에서 재fetch.
Lazy fallback 패턴: `_is_fresh()` 실패 → 즉시 `_fetch()` 호출.
배치 스케줄러 `on_startup` 핸들러가 시작 시 자동 1회 실행.
