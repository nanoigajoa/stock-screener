import json
from datetime import datetime

from fastapi.templating import Jinja2Templates
from screener.macro_fetcher import get_macro_context
from screener.fear_greed_fetcher import get_fear_greed


def _ago(dt) -> str:
    if dt is None:
        return "알 수 없음"
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = (now - dt).total_seconds()
    if diff < 60: return "방금 전"
    if diff < 3600: return f"{int(diff // 60)}분 전"
    if diff < 86400: return f"{int(diff // 3600)}시간 전"
    return dt.strftime("%m/%d")


templates = Jinja2Templates(directory="templates")
templates.env.filters["ago"] = _ago
templates.env.filters["tojson"] = lambda obj: json.dumps(obj, ensure_ascii=False)
templates.env.globals["get_macro"] = get_macro_context
templates.env.globals["get_fg"] = get_fear_greed
