import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from services.screener_service import run_analysis

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/stream/screen")
async def stream_screen(
    tickers: str = "",
    grade_filter: str = "",
    period: str = "6mo",
    rsi_min: int = 45,
    rsi_max: int = 65,
    checks: str = "",
):
    tickers_list = [t.strip().upper() for t in tickers.split(",") if t.strip()] or None
    grade = grade_filter.strip() or None
    enabled = [c.strip() for c in checks.split(",") if c.strip()] or None

    async def generate():
        yield _sse("progress", {"stage": "기술적 분석 시작..."})
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                lambda: run_analysis(tickers_list, grade, period=period, rsi_min=rsi_min, rsi_max=rsi_max, enabled_checks=enabled),
            )
            displayable = result.get("displayable", [])
            summary    = result.get("summary", {})

            if not displayable:
                html = '<div class="result-empty"><p>조건에 맞는 종목이 없습니다.</p></div>'
            else:
                cards = _render_result_cards(displayable)
                html = (
                    f'<div class="result-container">'
                    f'<p class="summary">'
                    f'총 {summary.get("total", 0)}개 분석 | '
                    f'SKIP {summary.get("skipped", 0)}개 | '
                    f'표시 {summary.get("displayed", 0)}개'
                    f'</p>{cards}</div>'
                )

            yield _sse("done", {"html": html})
        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _tv_widget(ticker: str) -> str:
    config = json.dumps({
        "symbol": ticker,
        "width": 300,
        "height": 150,
        "locale": "en",
        "dateRange": "3M",
        "colorTheme": "dark",
        "trendLineColor": "rgba(99, 179, 237, 1)",
        "underLineColor": "rgba(99, 179, 237, 0.15)",
        "underLineBottomColor": "rgba(99, 179, 237, 0)",
        "isTransparent": True,
        "autosize": False,
        "largeChartUrl": f"https://www.tradingview.com/chart/?symbol={ticker}",
    })
    return (
        f'<div class="tradingview-widget-container tv-widget">'
        f'<div class="tradingview-widget-container__widget"></div>'
        f'<script type="text/javascript" '
        f'src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>'
        f'{config}</script>'
        f'</div>'
    )


def _b(label: str, value: str, cls: str) -> str:
    """배지 하나 렌더링 헬퍼."""
    return f'<span class="badge {cls}"><span class="badge-label">{label}</span><span class="badge-val">{value}</span></span>'


def _render_all_indicators(r: dict, extras: dict, price: float) -> str:
    """모든 지표를 항상 표시. 조건 충족 여부에 따라 색상만 다름."""
    rows = []

    # ── 1. 뉴스 ──────────────────────────────────────
    news_ok = r.get("news_ok")
    if news_ok is True:
        rows.append(_b("뉴스", "이상 없음 ✅", "sig-ok"))
    elif news_ok is False:
        rows.append(_b("뉴스", "위험 ⚠️", "sig-bad"))
    else:
        rows.append(_b("뉴스", "필터 꺼짐", "sig-dim"))

    # ── 이하 extras 없으면 N/A 처리 ──────────────────
    na = not extras

    # ── 2. 내부자 매수 (SEC Form 4) ──────────────────
    insider = extras.get("insider_bought") if not na else None
    if insider is True:
        rows.append(_b("내부자 매수", "있음 ✅", "sig-ok"))
    elif insider is False:
        rows.append(_b("내부자 매수", "없음", "sig-dim"))
    else:
        rows.append(_b("내부자 매수", "N/A", "sig-na"))

    # ── 3. 의원 매수 (Congress) ───────────────────────
    congress = extras.get("congress_bought") if not na else None
    if congress is True:
        rows.append(_b("의원 매수", "있음 ✅", "sig-ok"))
    elif congress is False:
        rows.append(_b("의원 매수", "없음", "sig-dim"))
    else:
        rows.append(_b("의원 매수", "N/A", "sig-na"))

    # ── 4. 구글 트렌드 ────────────────────────────────
    trend = extras.get("trend_score") if not na else None
    if trend is not None:
        cls = "sig-ok" if trend >= 60 else ("sig-warn" if trend >= 40 else "sig-dim")
        rows.append(_b("구글 관심", str(trend), cls))
    else:
        rows.append(_b("구글 관심", "N/A", "sig-na"))

    # ── 5. 실적 발표일 ────────────────────────────────
    days = extras.get("days_to_earnings") if not na else None
    if days is not None and days >= 0:
        if days <= 7:
            rows.append(_b("실적", f"D-{days} ⚠️", "sig-bad"))
        elif days <= 14:
            rows.append(_b("실적", f"D-{days}", "sig-warn"))
        else:
            rows.append(_b("실적", f"D-{days}", "sig-dim"))
    else:
        rows.append(_b("실적", "정보없음", "sig-na"))

    # ── 6. 숏비율 ─────────────────────────────────────
    short = extras.get("short_ratio") if not na else None
    if short is not None:
        cls = "sig-bad" if short >= 5 else "sig-dim"
        rows.append(_b("숏비율", f"{short:.1f}d", cls))
    else:
        rows.append(_b("숏비율", "N/A", "sig-na"))

    # ── 7. 애널리스트 목표가 ──────────────────────────
    target = extras.get("analyst_target") if not na else None
    if target and price > 0:
        pct = (target - price) / price * 100
        sign = "+" if pct >= 0 else ""
        cls = "sig-ok" if pct >= 5 else ("sig-warn" if pct >= 0 else "sig-bad")
        rows.append(_b("목표가", f"${target:.0f} ({sign}{pct:.0f}%)", cls))
    else:
        rows.append(_b("목표가", "N/A", "sig-na"))

    return f'<div class="indicators">{"".join(rows)}</div>'


def _render_result_cards(results: list[dict]) -> str:
    grade_class = {"S": "grade-s", "A": "grade-a", "B": "grade-b", "SKIP": "grade-skip"}
    grade_label = {"S": "S급", "A": "A급", "B": "B급", "SKIP": "SKIP"}
    grade_icon  = {"S": "⭐", "A": "🟡", "B": "🔵", "SKIP": "❌"}

    parts = []
    for r in results:
        g      = r.get("grade", "SKIP")
        css    = grade_class.get(g, "")
        label  = grade_label.get(g, g)
        icon   = grade_icon.get(g, "")
        score  = r.get("score", 0)
        max_sc = r.get("max_score", 9)
        extras = r.get("extras", {})

        # ── 체크리스트 ──
        checklist_rows = "".join(
            f'<li class="{"check-pass" if item.get("pass") else "check-fail"}">'
            f'<span class="check-icon">{"✅" if item.get("pass") else "❌"}</span>'
            f'<span class="check-name">{item["name"]}</span>'
            f'<span class="check-detail">{item["detail"]}</span>'
            f'</li>'
            for item in r.get("checklist", {}).values()
        )

        # ── 목표가 ──
        targets = ""
        if r.get("target_1"):
            targets = (
                f'<div class="targets">'
                f'<div class="target-box target-1">'
                f'<span class="target-label">1차 목표</span>'
                f'<span class="target-value">${r["target_1"]}</span>'
                f'</div>'
                f'<div class="target-box target-2">'
                f'<span class="target-label">2차 목표</span>'
                f'<span class="target-value">${r["target_2"]}</span>'
                f'</div>'
                f'<div class="target-box stop">'
                f'<span class="target-label">손절</span>'
                f'<span class="target-value">${r["stop_loss"]}</span>'
                f'</div>'
                f'</div>'
            )

        skip_reason = (
            f'<p class="skip-reason">{r.get("reason", "")}</p>'
            if g == "SKIP" and r.get("reason") else ""
        )

        indicators_html = _render_all_indicators(r, extras, r.get("price", 0)) if g != "SKIP" else ""
        chart           = _tv_widget(r["ticker"]) if g != "SKIP" else ""

        # 점수 표시 (SKIP 제외)
        score_html = ""
        if g != "SKIP":
            score_html = (
                f'<div class="score-display">'
                f'<span class="score-num">{score}</span>'
                f'<span class="score-max">/{max_sc}</span>'
                f'</div>'
            )

        parts.append(
            f'<div class="stock-card {css}">'
            f'  <div class="card-accent"></div>'
            f'  <div class="card-body">'
            f'    <div class="card-info">'
            f'      <div class="card-header">'
            f'        <div class="card-header-left">'
            f'          <span class="ticker">{r["ticker"]}</span>'
            f'          <span class="price">${r["price"]:.2f}</span>'
            f'        </div>'
            f'        <div class="card-header-right">'
            f'          {score_html}'
            f'          <span class="grade-badge">{icon} {label}</span>'
            f'        </div>'
            f'      </div>'
            f'      {indicators_html}'
            f'      {skip_reason}'
            f'      <ul class="checklist">{checklist_rows}</ul>'
            f'      {targets}'
            f'    </div>'
            f'    {chart}'
            f'  </div>'
            f'</div>'
        )

    return "".join(parts)
