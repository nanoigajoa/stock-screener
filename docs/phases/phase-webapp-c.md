# Phase Webapp-C — HTMX 프론트엔드 ✅ 완료 (2026-04-25)

**Goal:** 브라우저에서 스크리닝 실행 및 결과 실시간 표시

## Tasks

- [x] `templates/base.html`
  - HTMX CDN 포함 (1.9.10)
  - 다크 테마 CSS (배경 #0f1117)
  - 등급별 카드 스타일 (S=초록, A=노랑, B=파랑, SKIP=빨강)

- [x] `templates/screen.html`
  - 종목 입력 폼 (공백 구분, 빈칸=전체 Finviz 스캔)
  - 등급 필터 select
  - HTMX 폼 제출 → `#result-area` swap
  - 폴링 패턴: `hx-trigger="every 2s"` → SUCCESS 시 자동 중단

- [x] `api/routes/screen.py` → `_render_result_cards()`
  - 등급별 카드 HTML 서버 렌더링
  - 체크리스트 항목 (✅/❌ + 상세 텍스트)
  - 목표가/손절 표시

## Definition of Done ✅
- [x] 브라우저 `localhost:8000` 접속 시 폼 표시
- [x] 종목 입력 → 폴링 시작 → 결과 카드 자동 표시
- [x] SUCCESS 후 폴링 중단 확인

## 향후 개선 가능 (Phase 3)
- [ ] 차트 미리보기 (Chart.js)
- [ ] 결과 CSV 다운로드 버튼
- [ ] 종목 즐겨찾기/watchlist
- [ ] 모바일 반응형 개선
