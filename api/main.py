import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.routes.screen import router as screen_router
from api.routes.tickers import router as tickers_router

logger = logging.getLogger(__name__)

app = FastAPI(title="StockScope", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(screen_router)
app.include_router(tickers_router)

templates = Jinja2Templates(directory="templates")


def _ago(dt) -> str:
    """datetime → '방금 전 / N분 전 / N시간 전 / MM/DD' 문자열."""
    if dt is None:
        return "알 수 없음"
    from datetime import datetime
    diff = (datetime.now() - dt).total_seconds()
    if diff < 60:
        return "방금 전"
    if diff < 3600:
        return f"{int(diff // 60)}분 전"
    if diff < 86400:
        return f"{int(diff // 3600)}시간 전"
    return dt.strftime("%m/%d")


templates.env.filters["ago"] = _ago


@app.on_event("startup")
async def on_startup():
    """앱 시작 시 배치 스케줄러(매크로, 의원거래) 백그라운드 실행."""
    from screener.batch_scheduler import start as start_batch, _ESTIMATES
    total_est = sum(_ESTIMATES.values())
    logger.info("=" * 50)
    logger.info("[App] StockScope 서버 시작")
    logger.info(f"[App] 백그라운드 데이터 로드 시작 (예상 {total_est}초)")
    for name, sec in _ESTIMATES.items():
        logger.info(f"[App]   · {name}: ~{sec}초")
    logger.info("[App] 로드 완료 전에도 스크리닝은 즉시 사용 가능")
    logger.info("=" * 50)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, start_batch)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="about.html", context={"active_page": "about"}
    )


@app.get("/screen", response_class=HTMLResponse)
async def screen(request: Request):
    from screener.macro_fetcher import get_macro_context
    from screener.fear_greed_fetcher import get_fear_greed
    macro = get_macro_context()
    fear_greed = get_fear_greed()
    return templates.TemplateResponse(
        request=request,
        name="screen.html",
        context={"active_page": "screen", "macro": macro, "fear_greed": fear_greed},
    )


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse(
        request=request, name="about.html", context={"active_page": "about"}
    )
