## Skill: HTMX 폴링 패턴 (서버 렌더링 실시간 업데이트)

- **Purpose:** JavaScript 없이 서버 렌더링 HTML을 주기적으로 갱신해 비동기 작업 결과를 표시한다.
- **Inputs:** task_id (URL 파라미터)
- **Outputs:** HTML 조각 — 서버가 렌더링, HTMX가 DOM에 swap
- **Files:** `templates/screen.html`, `templates/base.html`, `api/routes/screen.py`

### 핵심 패턴
```html
<!-- 폼 제출 → HTML 조각 swap -->
<form hx-post="/htmx/screen"
      hx-target="#result-area"
      hx-swap="innerHTML">

<!-- 서버 응답: 폴링 트리거 포함 -->
<div hx-get="/htmx/results/{task_id}"
     hx-trigger="every 2s"
     hx-swap="outerHTML">  ← outerHTML: div 자체를 교체
  ⏳ 처리 중...
</div>

<!-- SUCCESS 응답: hx-trigger 없음 → 폴링 자동 중단 -->
<div class="result-container">
  ...결과 카드...
</div>
```

### Best Practices
- 폴링 중단: SUCCESS/FAILURE 응답에서 `hx-trigger` 속성을 포함하지 않으면 자동 중단
- `hx-swap="outerHTML"`: div 자체를 교체 (내부만 교체하는 `innerHTML`과 다름)
- 서버는 HTML 조각만 반환 (전체 페이지 아님)
- Jinja2로 결과 카드 서버 렌더링 → React 빌드 과정 불필요
- `hx-indicator`: 제출 버튼에 로딩 상태 적용 (`htmx-request` CSS 클래스 자동 추가)

### Anti-patterns
- `hx-trigger="every 2s"`를 SUCCESS 응답에도 포함 → 무한 폴링
- WebSocket 사용 → 5~10초 작업에 과도한 복잡도
- 전체 페이지 반환 → 레이아웃이 매 폴링마다 깜빡임

### Polling vs WebSocket 선택 기준
| 작업 시간 | 선택 |
|---------|------|
| 5~30초 | HTMX 폴링 (2~3초 간격) |
| 30초~수분 | SSE (Server-Sent Events) |
| 실시간 스트림 | WebSocket |
