"""매수 진입 신호 계산."""
import numpy as np
import pandas as pd
import pandas_ta as ta


def compute_buy_signals(df: pd.DataFrame) -> list[dict]:
    """
    일봉 DataFrame → 매수 신호 마커 리스트.

    공통 전제: 상승추세(MA20>MA60) + 진입존(MA60~MA20+0.5ATR)

    이유 종류 (우선순위 순):
      MA5골든  : MA5가 MA20을 상향 돌파 (단기 골든크로스)
      RSI+볼륨 : RSI반등 + 볼륨급증 동시 발생
      RSI반등  : RSI 40~60 구간 + 2일 연속 상승
      MACD전환 : MACD 히스토그램 음→양 전환
      볼륨급증 : 양봉 + 거래대금 20일 평균 2배 이상
    """
    if len(df) < 62:
        return []

    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    open_  = df["Open"]
    volume = df["Volume"]

    ma5  = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    delta    = close.diff()
    avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    rsi      = 100 - (100 / (1 + avg_gain / avg_loss))

    # pandas-ta ATR (Wilder EWM) — signal_scorer의 calc_atr_zones와 동일 방식
    atr = df.ta.atr(length=14)
    if atr is None:
        return []

    # MACD 히스토그램 (EMA12 − EMA26 − 시그널9)
    ema12     = close.ewm(span=12, min_periods=12).mean()
    ema26     = close.ewm(span=26, min_periods=26).mean()
    macd_hist = (ema12 - ema26) - (ema12 - ema26).ewm(span=9, min_periods=9).mean()

    value     = close * volume
    avg_value = value.shift(1).rolling(20).mean()

    n         = len(df)
    c_arr     = close.values
    o_arr     = open_.values
    hi_arr    = high.values
    lo_arr    = low.values
    m5_arr    = ma5.values
    m20_arr   = ma20.values
    m60_arr   = ma60.values
    atr_arr   = atr.values
    rsi_arr   = rsi.values
    mh_arr    = macd_hist.values
    val_arr   = value.values
    avg_arr   = avg_value.values
    dates     = [str(ts.date() if hasattr(ts, "date") else ts) for ts in df.index]

    def _prev(arr: np.ndarray) -> np.ndarray:
        p = np.empty(n); p[0] = np.nan; p[1:] = arr[:-1]; return p

    def _prev2(arr: np.ndarray) -> np.ndarray:
        p = np.empty(n); p[:2] = np.nan; p[2:] = arr[:-2]; return p

    rsi_prev  = _prev(rsi_arr)
    rsi_prev2 = _prev2(rsi_arr)
    m5_prev   = _prev(m5_arr)
    m20_prev  = _prev(m20_arr)
    mh_prev   = _prev(mh_arr)

    valid = (
        ~np.isnan(m5_arr)  & ~np.isnan(m5_prev)  &
        ~np.isnan(m20_arr) & ~np.isnan(m20_prev) &
        ~np.isnan(m60_arr) & ~np.isnan(atr_arr)  &
        ~np.isnan(rsi_arr) & ~np.isnan(rsi_prev) & ~np.isnan(rsi_prev2) &
        ~np.isnan(mh_arr)  & ~np.isnan(mh_prev)  &
        ~np.isnan(avg_arr) & (np.arange(n) >= 62)
    )

    uptrend = m20_arr > m60_arr
    in_zone = (m60_arr <= c_arr) & (c_arr <= m20_arr + 0.5 * atr_arr)

    # RSI 2일 연속 상승 + 40~60 눌림목 구간
    rsi_mom = (
        (rsi_arr >= 40) & (rsi_arr <= 60) &
        (rsi_arr > rsi_prev) & (rsi_prev > rsi_prev2)
    )

    # 양봉 + 거래대금 2배 스파이크
    is_bull = c_arr > o_arr
    vol_spk = (np.where(avg_arr > 0, val_arr / avg_arr, 0.0) >= 2.0) & is_bull

    # MA5 단기 골든크로스 (MA5가 MA20을 상향 돌파)
    ma_golden = (m5_arr > m20_arr) & (m5_prev <= m20_prev)

    # MACD 히스토그램 음→양 전환
    macd_turn = (mh_arr > 0) & (mh_prev <= 0)

    # Fair Value Gap (SMC): 과거 강세 충격파가 남긴 지지 공백에 가격 진입
    # 공백 구간: [High[j-2], Low[j]] — price 재방문 시 기관 지지 기대
    fvg_support = np.zeros(n, dtype=bool)
    for i in range(4, n):
        p = c_arr[i]
        for j in range(max(2, i - 20), i - 1):
            if lo_arr[j] > hi_arr[j - 2]:  # bullish FVG at candle j
                zone_bot = hi_arr[j - 2]
                zone_top = lo_arr[j]
                if zone_bot <= p <= zone_top * 1.02:
                    fvg_support[i] = True
                    break

    # 메인 진입존 시그널 (MA60~MA20+0.5ATR 구간 내 모멘텀 트리거)
    main_cond = valid & uptrend & in_zone & (rsi_mom | vol_spk | ma_golden | macd_turn)
    # FVG 구조적 진입 (진입존 조건 불필요 — 기관 지지선 자체가 진입 근거)
    fvg_cond  = valid & uptrend & fvg_support
    buy_cond  = main_cond | fvg_cond

    markers = []
    for i in np.where(buy_cond)[0]:
        if ma_golden[i]:
            reason = "MA5골든"
        elif fvg_support[i]:
            reason = "FVG반등"
        elif rsi_mom[i] and vol_spk[i]:
            reason = "RSI+볼륨"
        elif rsi_mom[i]:
            reason = "RSI반등"
        elif macd_turn[i]:
            reason = "MACD전환"
        else:
            reason = "볼륨급증"

        markers.append({
            "time":   dates[i],
            "type":   "buy",
            "price":  round(float(lo_arr[i]) * 0.98, 4),
            "reason": reason,
        })

    return markers
