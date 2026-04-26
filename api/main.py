from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api.routes.screen import router as screen_router
from api.routes.tickers import router as tickers_router

app = FastAPI(title="Stock Screener", version="1.0.0")
app.include_router(screen_router)
app.include_router(tickers_router)

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="screen.html")
