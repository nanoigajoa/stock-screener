import pandas as pd


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - signal_line
    return macd, signal_line, hist


def _bbands(series: pd.Series, length=20, std=2):
    middle = series.rolling(length).mean()
    stddev = series.rolling(length).std()
    upper = middle + std * stddev
    lower = middle - std * stddev
    return upper, middle, lower


def calculate_indicators(df: pd.DataFrame) -> dict | None:
    """OHLCV DataFrame → 기술적 지표 딕셔너리 반환. 계산 불가 시 None."""
    try:
        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        volume = df["Volume"]

        ma5   = _sma(close, 5)
        ma20  = _sma(close, 20)
        ma60  = _sma(close, 60)
        ma120 = _sma(close, 120)

        rsi = _rsi(close, 14)

        macd_line, signal_line, macd_hist = _macd(close)

        bb_upper, bb_middle, bb_lower = _bbands(close, length=20, std=2)

        vol_ma20 = _sma(volume, 20)

        def last(series):
            v = series.iloc[-1] if series is not None and not series.empty else None
            return float(v) if v is not None and pd.notna(v) else None

        price      = last(close)
        ma5_val    = last(ma5)
        ma20_val   = last(ma20)
        ma60_val   = last(ma60)
        ma120_val  = last(ma120)
        rsi_val    = last(rsi)
        vol_val    = float(volume.iloc[-1])
        vol_ma_val = last(vol_ma20)
        macd_val   = last(macd_line)
        signal_val = last(signal_line)
        hist_val   = last(macd_hist)
        bb_u       = last(bb_upper)
        bb_m       = last(bb_middle)
        bb_l       = last(bb_lower)

        recent = df.tail(20)
        support    = float(recent["Low"].min())
        resistance = float(recent["High"].max())

        mid = len(recent) // 2
        first_half  = recent.iloc[:mid]
        second_half = recent.iloc[mid:]
        higher_high = float(second_half["High"].max()) > float(first_half["High"].max())
        higher_low  = float(second_half["Low"].min())  > float(first_half["Low"].min())

        if any(v is None for v in [price, ma5_val, ma20_val, rsi_val, macd_val]):
            return None

        return {
            "price":       price,
            "ma5":         ma5_val,
            "ma20":        ma20_val,
            "ma60":        ma60_val,
            "ma120":       ma120_val,
            "rsi":         rsi_val,
            "volume":      vol_val,
            "vol_ma20":    vol_ma_val,
            "macd":        macd_val,
            "macd_signal": signal_val,
            "macd_hist":   hist_val,
            "bb_upper":    bb_u,
            "bb_middle":   bb_m,
            "bb_lower":    bb_l,
            "support":     support,
            "resistance":  resistance,
            "higher_high": higher_high,
            "higher_low":  higher_low,
        }

    except Exception as e:
        print(f"[Indicators] 계산 실패: {e}")
        return None
