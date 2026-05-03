import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.routes.explore import router as explore_router
from api.routes.screen import router as screen_router
from api.routes.tickers import router as tickers_router
from api.routes.chart import router as chart_router
from api.routes.watchlist import router as watchlist_router
from api.routes.signals import router as signals_router
from api.deps import templates

logger = logging.getLogger(__name__)

_background_task: asyncio.Task | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _background_task
    from screener.batch_scheduler import start_background_scheduler
    _background_task = await start_background_scheduler()
    yield
    logger.info("[App] 백그라운드 태스크 종료 중...")
    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            logger.info("[App] 백그라운드 태스크가 안전하게 취소되었습니다.")

app = FastAPI(title="StockScope", version="3.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(explore_router)
app.include_router(screen_router)
app.include_router(tickers_router)
app.include_router(chart_router)
app.include_router(watchlist_router)
app.include_router(signals_router)

# ── 라우트 (통합) ──────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return RedirectResponse(url="/signals")

@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    from screener.macro_fetcher import get_sidebar_macro
    macro = get_sidebar_macro()
    return templates.TemplateResponse(
        request=request, name="about.html", context={"active_page": "about", "macro": macro}
    )

# ── 기존 경로 리다이렉트 (선택 사항) ─────────────────────────

def _verify_refresh_token(x_refresh_token: str | None) -> None:
    secret = os.getenv("REFRESH_TOKEN", "")
    if not secret or x_refresh_token != secret:
        raise HTTPException(status_code=403, detail="Invalid refresh token")

def _do_macro_refresh():
    from screener.macro_fetcher import refresh_macro
    refresh_macro()

@app.get("/api/refresh/macro")
def api_refresh_macro(
    background_tasks: BackgroundTasks,
    x_refresh_token: str | None = Header(default=None),
):
    # BackgroundTasks를 적용하여 클라이언트 무한 로딩 해결
    _verify_refresh_token(x_refresh_token)
    background_tasks.add_task(_do_macro_refresh)
    return JSONResponse({"status": "accepted", "msg": "Refresh started in background"})