import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from config import DATA_PERIOD
from api.deps import templates

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)


@router.get("/screen", response_class=HTMLResponse)
def screen_page(request: Request):
    from screener.macro_fetcher import get_sidebar_macro
    macro = get_sidebar_macro()
    return templates.TemplateResponse(
        request=request,
        name="screen.html",
        context={"active_page": "screen", "macro": macro},
    )


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/stream/screen")
async def stream_screen(
    tickers: str = "",
    grade_filter: str = "",
    period: str = DATA_PERIOD,
    rsi_min: int = 45,
    rsi_max: int = 65,
    checks: str = "",
    target_1: float = 0,
    target_2: float = 0,
    stop_loss: float = 0,
):
    tickers_list = [t.strip().upper() for t in tickers.split(",") if t.strip()] or None
    grade = grade_filter.strip() or None
    enabled = [c.strip() for c in checks.split(",") if c.strip()] or None
    t1 = target_1 / 100 if target_1 > 0 else None
    t2 = target_2 / 100 if target_2 > 0 else None
    sl = stop_loss / 100 if stop_loss > 0 else None

    async def generate():
        from services.screener_service import run_analysis
        yield _sse("progress", {"stage": "기술적 분석 시작..."})
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    _executor,
                    lambda: run_analysis(
                        tickers_list, grade, period=period,
                        rsi_min=rsi_min, rsi_max=rsi_max, enabled_checks=enabled,
                        target_1_pct=t1, target_2_pct=t2, stop_loss_pct=sl,
                    ),
                ),
                timeout=120.0,
            )
            displayable = result.get("displayable", [])
            summary     = result.get("summary", {})

            if not displayable:
                html = '<div class="result-empty"><p>조건에 맞는 종목이 없습니다.</p></div>'
            else:
                tpl  = templates.get_template("partials/screen_cards.html")
                html = tpl.render(results=displayable, summary=summary)

            yield _sse("done", {"html": html})
        except asyncio.TimeoutError:
            yield _sse("error", {"message": "분석 시간이 초과되었습니다 (120초). 종목 수를 줄이거나 다시 시도해 주세요."})
        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
