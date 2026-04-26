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
async def stream_screen(tickers: str = "", grade_filter: str = ""):
    tickers_list = [t.strip().upper() for t in tickers.split(",") if t.strip()] or None
    grade = grade_filter.strip() or None

    async def generate():
        yield _sse("progress", {"stage": "스크리닝 시작..."})
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                lambda: run_analysis(tickers_list, grade),
            )
            displayable = result.get("displayable", [])
            summary = result.get("summary", {})

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
        "width": 280,
        "height": 130,
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
        f'<div class="tv-widget">'
        f'<div class="tradingview-widget-container__widget"></div>'
        f'<script type="text/javascript" '
        f'src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>'
        f'{config}</script>'
        f'</div>'
    )


def _render_result_cards(results: list[dict]) -> str:
    grade_class = {"S": "grade-s", "A": "grade-a", "B": "grade-b", "SKIP": "grade-skip"}
    grade_label = {"S": "⭐ S급", "A": "🟡 A급", "B": "🔵 B급", "SKIP": "❌ SKIP"}

    parts = []
    for r in results:
        g = r.get("grade", "SKIP")
        css = grade_class.get(g, "")
        label = grade_label.get(g, g)

        checklist_rows = "".join(
            f'<li>{"✅" if item.get("pass") else "❌"} {item["name"]}: {item["detail"]}</li>'
            for item in r.get("checklist", {}).values()
        )

        targets = ""
        if r.get("target_1"):
            targets = (
                f'<div class="targets">'
                f'<span>1차 목표: ${r["target_1"]}</span>'
                f'<span>2차 목표: ${r["target_2"]}</span>'
                f'<span>손절: ${r["stop_loss"]}</span>'
                f'</div>'
            )

        skip_reason = (
            f'<p class="skip-reason">{r.get("reason", "")}</p>'
            if g == "SKIP" and r.get("reason") else ""
        )
        chart = _tv_widget(r["ticker"]) if g != "SKIP" else ""

        parts.append(
            f'<div class="stock-card {css}">'
            f'<div class="card-body">'
            f'<div class="card-info">'
            f'<div class="card-header">'
            f'<span class="ticker">{r["ticker"]}</span>'
            f'<span class="price">${r["price"]:.2f}</span>'
            f'<span class="grade-badge">{label}</span>'
            f'</div>'
            f'{skip_reason}'
            f'<ul class="checklist">{checklist_rows}</ul>'
            f'{targets}'
            f'</div>'
            f'{chart}'
            f'</div>'
            f'</div>'
        )

    return "".join(parts)
