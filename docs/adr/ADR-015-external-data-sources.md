# ADR-015: 외부 데이터소스 4종 통합 전략

**날짜:** 2026-04-28
**상태:** 결정됨

---

## 배경

Finviz 기술적 필터만으로는 다른 스크리닝 도구 대비 차별화 부족.
yfinance 이외 공개 API/라이브러리를 활용해 부가 인사이트 제공.

## 결정된 소스 4개

### 1. Google Trends (pytrends)
- **근거:** 검색 관심도 급상승 = 소셜 모멘텀 조기 포착 가능
- **방식:** Lazy per-ticker, 5개씩 묶음 요청, 배치 간 1초 딜레이
- **표시:** Google Trends 점수 ≥ 60일 때 파란 배지 `구글 관심 N`

### 2. FRED 매크로 (fredapi)
- **근거:** 금리/CPI/VIX 등 거시경제 맥락 없이는 개별 종목 신호 오해 가능
- **방식:** 앱 시작 시 1회 + 7일 TTL. 단일 전역 캐시
- **표시:** 화면 상단 배너 (종목별 배지 아님)

### 3. 의회 의원 거래 (QuiverQuant)
- **근거:** 내부 정보 접근 가능성 있는 의원의 매수는 강한 긍정 신호
- **방식:** 시작 시 전체 목록 fetch → 메모리 보관 → 티커별 필터링
- **제약:** API 유료 → 키 없으면 자동 스킵 (graceful degradation)

### 4. SEC Form 4 내부자 매수 (sec-edgar-downloader)
- **근거:** yfinance `insider_purchases`는 데이터 누락·오류 잦음
- **방식:** SEC EDGAR에서 Form 4 XML 직접 다운로드 후 파싱
- **교체:** fundamental_fetcher의 `insider_bought` 로직 대체
- **표시:** 금색 배지 `내부자 매수 ✅`

## 채택하지 않은 소스

| 소스 | 이유 |
|------|------|
| Alpha Vantage | 무료 500req/day 제한 — 스캔 규모 부적합 |
| Unusual Whales (옵션 플로우) | 유료, 복잡도 대비 효용 불확실 |
| Reddit WSB 감성 | pushshift API 불안정, 노이즈 과다 |

## 아키텍처 원칙

1. **메모리 캐시만 사용** — SQLite/Redis 없음. 프로세스 재시작 시 재fetch
2. **Graceful degradation** — 키 없거나 API 오류 시 배지 생략, 에러 없음
3. **Extras는 displayable 종목에만** — SKIP 종목은 배지 조회 안 함
4. **병렬 조회** — 4개 소스 ThreadPoolExecutor로 동시 실행
