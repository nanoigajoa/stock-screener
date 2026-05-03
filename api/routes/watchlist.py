from fastapi import APIRouter
from screener import watchlist_store

router = APIRouter(prefix="/api/watchlist")


@router.get("")
def get_watchlist():
    return {"tickers": watchlist_store.load()}


@router.post("/{ticker}")
def add_ticker(ticker: str):
    return {"tickers": watchlist_store.add(ticker)}


@router.delete("/{ticker}")
def remove_ticker(ticker: str):
    return {"tickers": watchlist_store.remove(ticker)}


@router.delete("")
def clear_watchlist():
    return {"tickers": watchlist_store.clear()}
