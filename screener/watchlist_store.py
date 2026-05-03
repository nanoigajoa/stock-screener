import json
import threading
from pathlib import Path

_PATH = Path("data/watchlist.json")
_lock = threading.Lock()


def load() -> list[str]:
    with _lock:
        if not _PATH.exists():
            return []
        try:
            data = json.loads(_PATH.read_text())
            return [t for t in data if isinstance(t, str)]
        except (json.JSONDecodeError, OSError):
            return []


def save(tickers: list[str]) -> None:
    with _lock:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(tickers, ensure_ascii=False))


def add(ticker: str) -> list[str]:
    ticker = ticker.strip().upper()
    current = load()
    if ticker and ticker not in current:
        current.append(ticker)
        save(current)
    return current


def remove(ticker: str) -> list[str]:
    ticker = ticker.strip().upper()
    current = [t for t in load() if t != ticker]
    save(current)
    return current


def clear() -> list[str]:
    save([])
    return []
