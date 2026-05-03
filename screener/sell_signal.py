"""매도 청산 신호 계산."""
import numpy as np
import pandas as pd


def compute_sell_signals(df: pd.DataFrame) -> list[dict]:
    """
    일봉 DataFrame → 매도 신호 마커 리스트. 포지션과 무관하게 독립 발동.

    조건:
      - 데드크로스: MA20이 MA60 아래로 전환되는 날 (전환일 1회만)
      - RSI 과열 이탈: RSI 70 이상에서 2일 연속 하락 전환
      - MA20 붕괴: 가격이 MA20 위→아래 전환 + 음봉 + 거래량 1.5배
    """
    if len(df) < 62:
        return []

    close  = df["Close"]
    high   = df["High"]
    open_  = df["Open"]
    volume = df["Volume"]

    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    delta    = close.diff()
    avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    rsi      = 100 - (100 / (1 + avg_gain / avg_loss))

    value     = close * volume
    avg_value = value.shift(1).rolling(20).mean()

    n        = len(df)
    c_arr    = close.values
    o_arr    = open_.values
    h_arr    = high.values
    m20_arr  = ma20.values
    m60_arr  = ma60.values
    rsi_arr  = rsi.values
    val_arr  = value.values
    avg_arr  = avg_value.values
    dates    = [str(ts.date() if hasattr(ts, "date") else ts) for ts in df.index]

    m20_prev  = np.empty(n); m20_prev[0]   = np.nan; m20_prev[1:]   = m20_arr[:-1]
    m60_prev  = np.empty(n); m60_prev[0]   = np.nan; m60_prev[1:]   = m60_arr[:-1]
    rsi_prev  = np.empty(n); rsi_prev[0]   = np.nan; rsi_prev[1:]   = rsi_arr[:-1]
    rsi_prev2 = np.empty(n); rsi_prev2[:2] = np.nan; rsi_prev2[2:]  = rsi_arr[:-2]
    c_prev    = np.empty(n); c_prev[0]     = np.nan; c_prev[1:]     = c_arr[:-1]

    valid = (
        ~np.isnan(m20_arr) & ~np.isnan(m60_arr) & ~np.isnan(rsi_arr) &
        ~np.isnan(rsi_prev) & ~np.isnan(rsi_prev2) &
        ~np.isnan(m20_prev) & ~np.isnan(m60_prev) &
        ~np.isnan(c_prev)   & ~np.isnan(avg_arr)  &
        (np.arange(n) >= 62)
    )

    # 데드크로스: MA20이 MA60 아래로 넘어가는 전환일만
    dead_cross = (m20_arr < m60_arr) & (m20_prev >= m60_prev)

    # RSI 과열 이탈: 2일 전 RSI >= 70 → 2일 연속 하락
    rsi_exit = (rsi_prev2 >= 70) & (rsi_prev < rsi_prev2) & (rsi_arr < rsi_prev)

    # MA20 붕괴: 가격 MA20 위→아래 전환 + 음봉 + 거래량 1.5배
    is_bear    = c_arr < o_arr
    vol_up     = np.where(avg_arr > 0, val_arr / avg_arr, 0.0) >= 1.5
    ma20_break = (c_arr < m20_arr) & (c_prev >= m20_prev) & is_bear & vol_up

    sell_cond = valid & (dead_cross | rsi_exit | ma20_break)

    markers = []
    for i in np.where(sell_cond)[0]:
        if dead_cross[i]:
            reason = "데드크로스"
        elif rsi_exit[i]:
            reason = "RSI과열이탈"
        else:
            reason = "MA20붕괴"
        markers.append({
            "time":   dates[i],
            "type":   "sell",
            "price":  round(float(h_arr[i]) * 1.02, 4),
            "reason": reason,
        })

    return markers
