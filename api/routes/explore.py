import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from api.deps import templates

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)

# ── 등급 관련 매핑 ───────────────────────────────────────────

_SIG_KO = {
    "STRONG BUY": "매수 권장",
    "BUY":        "매수 가능",
    "WATCH":      "관망",
    "NO SIGNAL":  "무시",
}

_CAT_LABELS = {
    "entry":     "진입",
    "momentum":  "모멘텀",
    "structure": "구조",
    "volume":    "수급",
}

@router.get("/explore", response_class=HTMLResponse)
def explore_page(request: Request):
    from screener.macro_fetcher import get_sidebar_macro
    from screener.fear_greed_fetcher import get_fear_greed

    macro = get_sidebar_macro()
    fg = get_fear_greed()

    return templates.TemplateResponse(
        request=request,
        name="explore.html",
        context={
            "active_page": "explore",
            "macro": macro,
            "fg": fg,
        },
    )

@router.get("/stream/explore")
async def stream_explore(tickers: str = ""):
    tickers_list = [t.strip().upper() for t in tickers.split(",") if t.strip()] or None

    async def generate():
        from services.explore_service import run_explore_analysis
        
        yield _sse("progress", {"stage": "실시간 시장 탐색 중..."})
        
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                lambda: run_explore_analysis(tickers_list),
            )
            items   = result.get("results", [])
            summary = result.get("summary", {})

            if not items:
                html = '<div class="result-empty"><p>조건에 맞는 종목이 없습니다.</p></div>'
            else:
                cards = _render_explore_cards(items)
                html = (
                    f'<div class="explore-summary">'
                    f'시장에서 발견한 {summary.get("analyzed", 0)}개 기회 중 상위 {len(items)}개'
                    f'</div>'
                    f'<div class="explore-results">{cards}</div>'
                )

            yield _sse("done", {"html": html})
        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _render_explore_cards(items: list[dict]) -> str:
    parts = []
    for idx, item in enumerate(items, 1):
        tk = item["ticker"]
        price = item["price"]
        name = item["short_name"]
        domain = item["website_domain"]
        
        found = item["foundation"]
        timing = item["timing"]
        nl_sum = item["nl_summary"]
        
        # (1) 로고
        if domain:
            logo_html = (
                f'<div class="logo-wrapper">'
                f'  <img src="https://logo.clearbit.com/{domain}?size=64" class="company-logo" alt="{tk}" '
                f'       onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';">'
                f'  <div class="logo-fallback" style="display:none;">{tk[0]}</div>'
                f'</div>'
            )
        else:
            logo_html = f'<div class="logo-wrapper"><div class="logo-fallback">{tk[0]}</div></div>'

        # (2) 기초 체력 (Foundation)
        f_grade = found["grade"]
        f_score = found["score"]
        f_max   = found["max_score"]
        f_pct   = (f_score / f_max) * 100
        f_cls   = f"grade-{f_grade.lower()}"
        
        # (3) 매매 타이밍 (Timing)
        t_grade = timing["signal_grade"]
        t_score = timing["signal_score"]
        t_pct   = t_score * 100
        t_cls   = f"sig-{t_grade.lower().replace(' ', '-')}"
        
        # (4) 신호등 및 패턴 텍스트
        cats_html = ""
        for cat, val in timing["breakdown"].items():
            c_cls = "sc-pass" if val >= 1.0 else ("sc-warn" if val > 0 else "sc-fail")
            cats_html += f'<span class="sc-item {c_cls}" data-label="{_CAT_LABELS[cat]}"></span>'
        
        pattern_text = ""
        if timing.get("detected_patterns"):
            p_names = ", ".join(timing["detected_patterns"])
            pattern_text = f'<span class="pattern-badge">✨ {p_names}</span>'

        # (5) 히든 상세 (모달용)
        # 4열 지표 타일 및 타겟 정보 포함
        detail_html = _render_detail_for_modal(item)

        parts.append(
            f'<div class="explore-card {f_cls} {t_cls}" data-ticker="{tk}">'
            f'  <div class="ec-rank">{idx}</div>'
            f'  <div class="ec-header">'
            f'    {logo_html}'
            f'    <div class="ticker-box">'
            f'      <span class="ticker">{tk}</span>'
            f'      <span class="short-name">{name}</span>'
            f'    </div>'
            f'  </div>'
            f'  <div class="ec-metrics">'
            f'    <div class="metric-group">'
            f'      <span class="m-label">기초 체력: {f_grade}급</span>'
            f'      <div class="score-bar-bg"><div class="score-bar-fill" style="width:{f_pct}%"></div></div>'
            f'    </div>'
            f'    <div class="metric-group">'
            f'      <span class="m-label">매수 강도: {t_grade}</span>'
            f'      <div class="score-bar-bg"><div class="score-bar-fill" style="width:{t_pct}%"></div></div>'
            f'    </div>'
            f'  </div>'
            f'  <div class="ec-summary">'
            f'    <div class="ec-summary-top">'
            f'      <div class="ec-cats">{cats_html}</div>'
            f'      {pattern_text}'
            f'    </div>'
            f'    <p class="nl-text">"{nl_sum}"</p>'
            f'  </div>'
            f'  <div class="ec-price-action">'
            f'    <span class="price">${price:,.2f}</span>'
            f'    <button class="chart-btn" data-ticker="{tk}">차분 분석 →</button>'
            f'  </div>'
            f'  <div class="card-detail" hidden>{detail_html}</div>'
            f'</div>'
        )

    return "".join(parts)


def _render_detail_for_modal(item: dict) -> str:
    """통합 분석 모달 상세 HTML: [좌: 기초 체력 / 우: 매매 타이밍 + 브리핑]"""
    # 1. 타겟 정보 (Top)
    entry_low = item["timing"].get("entry_low")
    entry_high = item["timing"].get("entry_high")
    zone = f"${entry_low:,.2f} ~ ${entry_high:,.2f}" if entry_low else "계산 중"
    
    # 2. 기초 체력 타일 (Left)
    found_tiles = []
    for c_id, c in item["foundation"]["checklist"].items():
        is_pass = c.get("pass", False)
        cls = "pass" if is_pass else "fail"
        icon = "✅" if is_pass else "❌"
        found_tiles.append(
            f'<div class="grid-item {cls}" title="{c.get("detail", "")}">'
            f'  <span class="icon">{icon}</span>'
            f'  <span class="name">{c["name"].strip()}</span>'
            f'</div>'
        )

    # 3. 매매 타이밍 타일 (Right)
    time_tiles = []
    for cat, val in item["timing"]["breakdown"].items():
        if val >= 1.0:
            cls, icon = "pass", "🟢"
        elif val > 0:
            cls, icon = "warn", "🟡"
        else:
            cls, icon = "fail", "🔴"
        
        label = _CAT_LABELS.get(cat, cat)
        time_tiles.append(
            f'<div class="grid-item {cls}">'
            f'  <span class="icon">{icon}</span>'
            f'  <span class="name">{label}</span>'
            f'</div>'
        )

    # 4. 차트 모양 (Patterns)
    patterns = item["timing"].get("detected_patterns", [])
    pattern_html = ""
    if patterns:
        p_badges = "".join([f'<span class="pattern-badge-large">✨ {p}</span>' for p in patterns])
        pattern_html = (
            f'<div class="col-header" style="margin-top:1.5rem;">차트 패턴 (Shape)</div>'
            f'<div class="pattern-container">{p_badges}</div>'
        )
    else:
        pattern_html = (
            f'<div class="col-header" style="margin-top:1.5rem;">차트 패턴 (Shape)</div>'
            f'<div class="pattern-none">특별한 강세 패턴 없음</div>'
        )

    return (
        f'<div class="modal-target-zone">'
        f'  <span class="tz-label">적정 진입 타점</span>'
        f'  <span class="tz-val">{zone}</span>'
        f'</div>'
        f'<div class="modal-split-view">'
        f'  <div class="split-col split-left">'
        f'    <div class="col-header">기술적 기초 체력 (Foundation)</div>'
        f'    <div class="indicator-grid grid-4">{"".join(found_tiles)}</div>'
        f'  </div>'
        f'  <div class="split-col split-right">'
        f'    <div class="col-header">매매 타이밍 및 수급 (Timing)</div>'
        f'    <div class="indicator-grid grid-2">{"".join(time_tiles)}</div>'
        f'    {pattern_html}'
        f'    <div class="col-header" style="margin-top:1.5rem;">AI 분석 브리핑</div>'
        f'    <div class="nl-briefing-box">"{item["nl_summary"]}"</div>'
        f'  </div>'
        f'</div>'
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
