import pandas as pd
import pandas_ta as ta

def calculate_indicators(df: pd.DataFrame) -> dict | None:
    """OHLCV DataFrame → 기술적 지표 딕셔너리 반환. 계산 불가 시 None."""
    try:
        # 기존 컬럼 보존을 위해 복사본 사용 (pandas-ta가 원본 df를 수정할 수 있음)
        working_df = df.copy()
        
        # pandas-ta를 사용한 지표 계산
        working_df.ta.sma(length=5, append=True)
        working_df.ta.sma(length=20, append=True)
        working_df.ta.sma(length=60, append=True)
        working_df.ta.sma(length=120, append=True)
        working_df.ta.rsi(length=14, append=True)
        working_df.ta.macd(fast=12, slow=26, signal=9, append=True)
        working_df.ta.bbands(length=20, std=2, append=True)
        working_df.ta.sma(close=working_df["Volume"], length=20, prefix="VOL", append=True)

        def last(col_pattern):
            cols = working_df.filter(like=col_pattern).columns
            if not cols.empty:
                v = working_df[cols[0]].iloc[-1]
                return float(v) if pd.notna(v) else None
            return None

        price = float(working_df["Close"].iloc[-1])
        ma5_val = last("SMA_5")
        ma20_val = last("SMA_20")
        ma60_val = last("SMA_60")
        ma120_val = last("SMA_120")
        rsi_val = last("RSI_14")
        vol_val = float(working_df["Volume"].iloc[-1])
        vol_ma_val = last("VOL_SMA_20")
        
        macd_val = last("MACD_12_26_9")
        signal_val = last("MACDs_12_26_9")
        hist_val = last("MACDh_12_26_9")
        
        bb_u = last("BBU_20_2.0")
        bb_m = last("BBM_20_2.0")
        bb_l = last("BBL_20_2.0")

        recent = df.tail(20)
        support = float(recent["Low"].min())
        resistance = float(recent["High"].max())

        mid = len(recent) // 2
        first_half = recent.iloc[:mid]
        second_half = recent.iloc[mid:]
        higher_high = float(second_half["High"].max()) > float(first_half["High"].max())
        higher_low = float(second_half["Low"].min()) > float(first_half["Low"].min())

        if any(v is None for v in [price, ma5_val, ma20_val, rsi_val, macd_val]):
            return None

        return {
            "price": price,
            "ma5": ma5_val,
            "ma20": ma20_val,
            "ma60": ma60_val,
            "ma120": ma120_val,
            "rsi": rsi_val,
            "volume": vol_val,
            "vol_ma20": vol_ma_val,
            "macd": macd_val,
            "macd_signal": signal_val,
            "macd_hist": hist_val,
            "bb_upper": bb_u,
            "bb_middle": bb_m,
            "bb_lower": bb_l,
            "support": support,
            "resistance": resistance,
            "higher_high": higher_high,
            "higher_low": higher_low,
        }

    except Exception as e:
        print(f"[Indicators] 계산 실패: {e}")
        return None

def calc_atr_zones(df: pd.DataFrame, period: int = 14) -> dict | None:
    """ATR(14) 기반 진입존·시그널 손절가.

    진입존 = MA60(추세 하단 지지) ~ MA20 + 0.5*ATR(상단 버퍼).
    MA20이 MA60 위에 있을 때 이 구간에 가격이 있으면 상승 추세 내 눌림 진입.
    """
    try:
        atr_s  = df.ta.atr(length=period)
        ma20_s = df.ta.sma(length=20)
        ma60_s = df.ta.sma(length=60)

        if atr_s is None or ma20_s is None or ma60_s is None:
            return None

        atr  = float(atr_s.iloc[-1])
        ma20 = float(ma20_s.iloc[-1])
        ma60 = float(ma60_s.iloc[-1])

        if any(pd.isna(v) for v in [atr, ma20, ma60]):
            return None

        return {
            "atr":         round(atr, 4),
            "entry_low":   round(ma60, 2),
            "entry_high":  round(ma20 + 0.5 * atr, 2),
            "signal_stop": round(ma60 - 1.0 * atr, 2),
        }
    except Exception:
        return None

def calc_stoch_rsi(
    df: pd.DataFrame,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> dict | None:
    """pandas-ta를 사용한 StochRSI 계산."""
    try:
        stoch_rsi = df.ta.stochrsi(length=rsi_period, rsi_length=stoch_period, k=k_smooth, d=d_smooth)
        
        if stoch_rsi is None:
            return None
            
        # pandas-ta StochRSI 컬럼명: STOCHRSIk_14_14_3_3, STOCHRSId_14_14_3_3
        k_col = f"STOCHRSIk_{rsi_period}_{stoch_period}_{k_smooth}_{d_smooth}"
        d_col = f"STOCHRSId_{rsi_period}_{stoch_period}_{k_smooth}_{d_smooth}"
        
        if k_col not in stoch_rsi.columns or d_col not in stoch_rsi.columns:
            return None

        k_cur = float(stoch_rsi[k_col].iloc[-1]) / 100.0  # 0~1 범위로 정규화
        d_cur = float(stoch_rsi[d_col].iloc[-1]) / 100.0
        k_prv = float(stoch_rsi[k_col].iloc[-2]) / 100.0
        d_prv = float(stoch_rsi[d_col].iloc[-2]) / 100.0
        
        if any(pd.isna(v) for v in [k_cur, d_cur, k_prv, d_prv]):
            return None

        if k_cur < 0.3 and k_prv <= d_prv and k_cur > d_cur:
            signal = "buy"
        elif k_cur > 0.7 and k_prv >= d_prv and k_cur < d_cur:
            signal = "sell"
        else:
            signal = "neutral"

        rsi_val = None
        rsi_s = df.ta.rsi(length=rsi_period)
        if rsi_s is not None and pd.notna(rsi_s.iloc[-1]):
            rsi_val = round(float(rsi_s.iloc[-1]), 2)

        return {
            "k": round(k_cur, 4), "d": round(d_cur, 4),
            "k_prev": round(k_prv, 4), "signal": signal,
            "rsi": rsi_val,
        }
    except Exception:
        return None

def calc_bb_advanced(df: pd.DataFrame) -> dict | None:
    """%B와 밴드폭 계산."""
    try:
        bb = df.ta.bbands(length=20, std=2)
        if bb is None or bb.empty:
            return None
            
        def get_val(pattern):
            cols = bb.filter(like=pattern).columns
            if not cols.empty:
                return float(bb[cols[0]].iloc[-1])
            return None

        def get_prev(pattern):
            cols = bb.filter(like=pattern).columns
            if not cols.empty and len(bb) >= 2:
                v = bb[cols[0]].iloc[-2]
                return float(v) if pd.notna(v) else None
            return None

        u = get_val("BBU")
        m = get_val("BBM")
        l = get_val("BBL")
        pct_b      = get_val("BBP")
        pct_b_prev = get_prev("BBP")
        bandwidth  = get_val("BBB")
        if bandwidth is not None:
            bandwidth /= 100.0

        if any(v is None or pd.isna(v) for v in [u, m, l, pct_b]):
            return None

        if pct_b < 0.20:
            signal = "buy"
        elif pct_b > 0.80:
            signal = "sell"
        else:
            signal = "neutral"

        return {
            "pct_b":      round(pct_b, 4),
            "pct_b_prev": round(pct_b_prev, 4) if pct_b_prev is not None else None,
            "bandwidth":  round(bandwidth, 4) if bandwidth is not None else None,
            "signal":     signal,
        }
    except Exception as e:
        print(f"[Indicators] calc_bb_advanced 실패: {e}")
        return None

def calc_obv_divergence(df: pd.DataFrame) -> dict | None:
    """OBV 추세 방향 감지 (OBV_MA10 vs OBV_MA30 정배열).

    단순 세그먼트 min/max 비교 → MA 정배열로 교체.
    일시적 급락/급등에 의한 오신호를 제거한다.
    """
    try:
        obv = df.ta.obv()
        if obv is None or len(df) < 30:
            return None

        obv_fast = float(obv.rolling(window=10).mean().iloc[-1])
        obv_slow = float(obv.rolling(window=30).mean().iloc[-1])

        if pd.isna(obv_fast) or pd.isna(obv_slow):
            return None

        if obv_fast > obv_slow:
            divergence = "bullish"
        elif obv_fast < obv_slow:
            divergence = "bearish"
        else:
            divergence = "none"

        return {"obv_last": round(float(obv.iloc[-1]), 0), "divergence": divergence}
    except Exception:
        return None

def calc_ma_alignment(
    df_daily: pd.DataFrame,
    df_hourly: pd.DataFrame | None = None,
) -> dict:
    """현재 MA 정배열/역배열 상태 반환.

    크로스 이벤트(언제 교차했는가)가 아닌 현재 상태(지금 어느 쪽인가)를 본다.
    "bullish" = MA20 > MA60, "bearish" = MA20 < MA60, "none" = 데이터 부족.
    """
    def _alignment(df: pd.DataFrame) -> tuple[str, float | None, float | None]:
        ma20_s = df.ta.sma(length=20)
        ma60_s = df.ta.sma(length=60)
        if ma20_s is None or ma60_s is None:
            return "none", None, None
        v20 = float(ma20_s.iloc[-1])
        v60 = float(ma60_s.iloc[-1])
        if pd.isna(v20) or pd.isna(v60):
            return "none", None, None
        if v20 > v60:
            return "bullish", v20, v60
        if v20 < v60:
            return "bearish", v20, v60
        return "none", v20, v60

    daily, ma20_val, ma60_val = _alignment(df_daily)

    hourly = None
    if df_hourly is not None and len(df_hourly) >= 60:
        hourly, _, _ = _alignment(df_hourly)

    return {"daily": daily, "hourly": hourly, "ma20": ma20_val, "ma60": ma60_val}


# 이전 이름 호환성 유지 (외부 호출 없음, 삭제 예정)
calc_ma_cross = calc_ma_alignment

def calc_value_spike(df: pd.DataFrame, window: int = 20, threshold: float = 2.0) -> dict | None:
    """거래대금 급증 감지."""
    try:
        if len(df) < window + 1:
            return None
        value = df["Close"] * df["Volume"]
        avg = float(value.iloc[-(window + 1):-1].mean())
        today = float(value.iloc[-1])
        if avg == 0 or pd.isna(avg) or pd.isna(today):
            return None
        ratio = today / avg
        return {
            "ratio": round(ratio, 2),
            "signal": "spike" if ratio >= threshold else "normal",
        }
    except Exception:
        return None


def calc_cmf(df: pd.DataFrame, length: int = 21) -> dict | None:
    """Chaikin Money Flow — 자금 유입/유출 방향과 강도.

    값 범위: -1.0 ~ +1.0
      +0.15 이상 → 강한 매수 압력
       0 ~ +0.15 → 완만한 매수
       음수       → 매도 압력
    """
    try:
        cmf_s = df.ta.cmf(length=length)
        if cmf_s is None or len(cmf_s) < 1:
            return None
        val = float(cmf_s.iloc[-1])
        if pd.isna(val):
            return None
        return {"cmf": round(val, 4)}
    except Exception:
        return None
