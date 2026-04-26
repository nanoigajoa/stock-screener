# Phase 1 — Core Pipeline ✅ 완료 (2026-04-25)

**Goal:** Finviz 필터링 → 채점 → 터미널 출력

---

## Tasks

- [x] `requirements.txt` 생성
  - yfinance, finviz, pandas, pandas-ta, numpy, schedule, colorama, requests

- [x] `config.py` 작성
  - FINVIZ_FILTERS, RSI 기준값, 목표가/손절, 스케줄, 출력 설정
  - 추가: TODAY_CHANGE_MIN/MAX, MIN_VOLUME_ABSOLUTE, MIN_RELATIVE_VOLUME, NEWS_FILTER_ENABLED

- [x] `screener/finviz_filter.py`
  - FINVIZ_FILTERS 적용, ETF 키워드 제거, 재시도 3회(지수 백오프)

- [x] `screener/data_fetcher.py`
  - `fetch_ohlcv()` — yfinance 배치 수집, 당일 인메모리 캐싱
  - `get_today_changes()` — ThreadPoolExecutor(max=6) 병렬 조회, 6초 timeout

- [x] `screener/news_filter.py` *(설계 외 추가)*
  - `check_news_risk()` — 48h 이내 뉴스 위험 키워드(희석/실적쇼크) 감지

- [x] `screener/indicators.py`
  - MA5/20/60/120, RSI14, MACD(12,26,9), BB(20,2), Vol MA20
  - 지지/저항 최근 20봉 자동감지, HH/HL 판단
  - pandas-ta 컬럼명 동적 탐색 (버전 호환)

- [x] `screener/checklist.py`
  - 7개 항목 채점, RSI 하드게이트(≥80 → SKIP)
  - MA 정배열: 가변점수 (완전=2, 단기만=1, 실패=0)
  - 거래량: 절대량(≥200만) + 상대량(≥1.5배) 이중 조건

- [x] `screener/grader.py`
  - score → S/A/B/SKIP, 목표가(+8%/+15%), 손절(-15%) 계산

- [x] `notifier/terminal.py`
  - colorama 등급별 색상, S급 ⭐ 강조, 체크리스트 상세 출력

- [x] `utils/logger.py` *(Phase 2 선행 구현)*
  - CSV 저장 (output/results/YYYY-MM-DD.csv)

- [x] `main.py` 파이프라인 통합
  - 실행 순서: Finviz → OHLCV → 당일변동 필터 → 뉴스 필터 → 지표 → 채점 → 등급 → 출력
  - CLI: `--schedule`, `--ticker`, `--grade`, `--save`
  - 대화형 모드: CLI 인수 없이 실행 시 메뉴 + 티커 직접 입력

---

## Definition of Done ✅

- [x] `python main.py` 실행 시 대화형 메뉴 표시
- [x] `python main.py --ticker AAPL` 특정 종목 분석 동작
- [x] RSI ≥ 80 종목 SKIP 처리
- [x] ETF 제거 로직 동작
- [x] 당일 -5% 이상 하락 / +15% 이상 급등 종목 SKIP
- [x] 뉴스 위험 키워드 감지 시 SKIP + 사유 출력
- [x] pandas-ta 버전 무관 컬럼명 동적 탐색
- [x] yfinance fast_info hang → timeout 처리

---

## 설계 대비 변경사항

| 항목 | 원래 설계 | 실제 구현 |
|------|----------|----------|
| 뉴스 필터 | 없음 | `news_filter.py` 추가 (ADR-006) |
| MA 채점 | 이진 (pass/fail) | 가변점수 0/1/2 (ADR-003) |
| 거래량 조건 | 상대량만 | 절대량 + 상대량 이중 조건 (ADR-007) |
| 당일변동 필터 | 없음 | -5%~+15% 범위 외 SKIP (ADR-004) |
| 병렬 조회 | 없음 | ThreadPoolExecutor + timeout (ADR-005) |
| 실행 방식 | CLI 전용 | CLI + 대화형 모드 (ADR-008) |
| logger.py | Phase 2 예정 | Phase 1에 선행 구현 |
| --schedule/--save | Phase 2 예정 | Phase 1에 선행 구현 |
