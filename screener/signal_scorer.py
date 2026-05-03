"""
4-카테고리 가중 매매시점 시그널 스코어링.
기존 7 boolean 합산 → 추세·모멘텀·수급·패턴 카테고리별 가중 평균(0~1 float).

기존 S/A/B/SKIP 체크리스트와 완전 독립 — 기존 필드에 영향 없음.
"""
import logging
import pandas as pd

from screener.indicators import (
    calc_atr_zones,
    calc_stoch_rsi,
    calc_obv_divergence,
    calc_ma_alignment,
    calc_cmf,
)

logger = logging.getLogger(__name__)


def _detect_recent_bullish(df: pd.DataFrame, lookback: int = 3) -> list[str]:
    """최근 lookback봉 내 강세 캔들 패턴 감지 (순수 pandas 구현)."""
    try:
        if len(df) < 4:
            return []

        o = df["Open"].values
        h = df["High"].values
        l = df["Low"].values
        c = df["Close"].values

        detected = []

        # 최근 lookback 봉 각각 검사
        for i in range(max(1, len(df) - lookback), len(df)):
            body     = abs(c[i] - o[i])
            rng      = h[i] - l[i]
            if rng == 0:
                continue
            upper_sh = h[i] - max(c[i], o[i])
            lower_sh = min(c[i], o[i]) - l[i]
            is_bull  = c[i] > o[i]

            # Hammer: 아래 꼬리 ≥ 2×몸통, 위 꼬리 ≤ 몸통, 몸통 < 전체 30%
            if body > 0 and lower_sh >= 2 * body and upper_sh <= body and body / rng < 0.30:
                detected.append("Hammer")

            # Bullish Engulfing: 이전 봉 음봉, 현봉 양봉이 이전 몸통 완전 포함
            if i >= 1:
                prev_bear = c[i-1] < o[i-1]
                curr_bull = c[i] > o[i]
                if prev_bear and curr_bull and o[i] <= c[i-1] and c[i] >= o[i-1]:
                    detected.append("BullishEngulfing")

            # Piercing Line: 이전 봉 음봉, 현봉 양봉, 이전 중간선 위로 마감
            if i >= 1:
                prev_mid = (o[i-1] + c[i-1]) / 2
                prev_bear = c[i-1] < o[i-1]
                if prev_bear and is_bull and c[i] > prev_mid and o[i] < c[i-1]:
                    detected.append("PiercingLine")

        # Morning Star (3봉): [-3] 음봉 | [-2] 소체 | [-1] 양봉이 [-3] 중간 이상
        if len(df) >= 3:
            i = len(df) - 1
            b1 = abs(c[i-2] - o[i-2])   # 첫 봉 몸통
            b2 = abs(c[i-1] - o[i-1])   # 중간 봉 몸통
            b3 = abs(c[i]   - o[i])      # 마지막 봉 몸통
            mid_of_first = (o[i-2] + c[i-2]) / 2
            if (c[i-2] < o[i-2] and b2 < b1 * 0.5
                    and c[i] > o[i] and c[i] >= mid_of_first and b3 > b1 * 0.5):
                detected.append("MorningStar")

        # Three White Soldiers (3봉): 연속 3 양봉, 각 봉 전봉 몸통 내에서 시가
        if len(df) >= 3:
            i = len(df) - 1
            all_bull = all(c[i-k] > o[i-k] for k in range(3))
            rising   = c[i] > c[i-1] > c[i-2]
            open_in_body = (o[i-1] >= o[i-2] and o[i] >= o[i-1])
            if all_bull and rising and open_in_body:
                detected.append("ThreeWhiteSoldiers")

        # Liquidity Sweep: 최근 lookback봉 내에서 20봉 저점을 장중 이탈 후 종가 회복
        # 기관이 개인의 손절 물량을 빼앗은 후 급반등 — 가장 강한 매집 신호
        if len(df) >= 21:
            for ls_i in range(max(21, len(df) - lookback), len(df)):
                pool = min(l[ls_i - 20:ls_i])   # 직전 20봉 최저가 (현봉 제외)
                if l[ls_i] < pool and c[ls_i] > pool:
                    detected.append("LiquiditySweep")
                    break   # 중복 방지

        # 중복 제거 후 반환
        result = list(dict.fromkeys(detected))
        if result:
            logger.info(f"[Signal] 패턴 발견: {result}")
        return result
    except Exception as e:
        logger.debug(f"[Signal] 패턴 감지 실패: {e}")
        return []


def _cat_score(a: float, b: float) -> float:
    """두 [0,1] 강도값 평균 → 카테고리 점수."""
    return (a + b) / 2


def score_signals(
    df_daily: pd.DataFrame,
    df_hourly: pd.DataFrame | None = None,
) -> dict:
    """
    4-카테고리 가중 평균 시그널 스코어링.
    ... (중략) ...
    Returns:
        signal_grade:     "STRONG BUY" | "BUY" | "WATCH" | "NO SIGNAL"
        signal_score:     float  0.0 ~ 1.0 (가중 평균)
        signal_breakdown: dict[category, float]  각 카테고리 점수
        detected_patterns: list[str]  감지된 캔들 패턴명
        entry_low, entry_high, signal_stop
    """
    try:
        atr      = calc_atr_zones(df_daily)
        stoch    = calc_stoch_rsi(df_daily)
        obv      = calc_obv_divergence(df_daily)
        ma       = calc_ma_alignment(df_daily, df_hourly)
        cmf_data = calc_cmf(df_daily)
        patterns = _detect_recent_bullish(df_daily)

        price = float(df_daily["Close"].iloc[-1])

        # ── 카테고리별 점수 계산 ──────────────────────────────
        # Trend: MA 정배열 폭(%) + 진입존 위치 연속값
        ma20_val = ma.get("ma20")
        ma60_val = ma.get("ma60")
        if ma20_val and ma60_val and ma60_val > 0:
            spread_pct = (ma20_val - ma60_val) / ma60_val
            ma_intensity = min(max(spread_pct / 0.05, 0.0), 1.0)  # 5% 이상 = 만점
        else:
            ma_intensity = 0.0

        if atr:
            if atr["entry_low"] <= price <= atr["entry_high"]:
                atr_ok = 1.0   # 진입존 안 — 이상적 타이밍
            elif price > atr["entry_high"]:
                atr_ok = 0.5   # 이미 위에 있음 — 늦은 진입
            else:
                atr_ok = 0.0   # 진입존 아래
        else:
            atr_ok = 0.0
        trend_score = _cat_score(ma_intensity, atr_ok)

        # Momentum: RSI 위치 기반 (주) + StochRSI 방향 보정 (부)
        #
        # RSI 구간별 점수:
        #   45~65  → 건강한 상승 모멘텀 구간, 55에서 만점
        #   35~45  → 눌림목 회복 중, 선형 증가
        #   65~75  → 과매수 진입, 선형 감소
        #   <35 / >75 → 극단 구간, 0점
        rsi_score = 0.0
        if stoch:
            rsi = stoch.get("rsi")
            if rsi is not None:
                if 45 <= rsi <= 65:
                    rsi_score = 1.0 - abs(rsi - 55) / 10   # 55 → 1.0, 45/65 → 0.0
                elif 35 <= rsi < 45:
                    rsi_score = (rsi - 35) / 10 * 0.6       # 35 → 0.0, 45 → 0.6
                elif 65 < rsi <= 75:
                    rsi_score = (75 - rsi) / 10 * 0.4       # 65 → 0.4, 75 → 0.0

        # StochRSI 방향: 과매도권 탈출 중이면 보너스
        stoch_bonus = 0.0
        if stoch:
            k   = stoch["k"]
            k_p = stoch.get("k_prev", k)
            if k > k_p and k_p < 0.35:
                stoch_bonus = min((k - k_p) / 0.05, 0.3)

        # Z-Score: (종가 - 20일 평균) / 20일 표준편차
        # 통계적 과매도 확인 — StochRSI 보너스와 상호 교차 검증
        z_bonus = 0.0
        close_tail = df_daily["Close"].tail(20).values
        if len(close_tail) >= 20:
            _std = close_tail.std(ddof=1)
            if _std > 0:
                z = (float(close_tail[-1]) - close_tail.mean()) / _std
                if z < -2.0:
                    z_bonus = 0.30   # 극단적 과매도 (2σ 이하)
                elif z < -1.0:
                    z_bonus = 0.15   # 보통 과매도 (1~2σ 사이)

        # 두 보너스 중 강한 쪽 채택 (동일 현상을 이중 계산 방지)
        momentum_score = min(rsi_score + max(stoch_bonus, z_bonus), 1.0)

        # Volume: CMF 자금 유입 강도 + OBV 정배열
        # CMF > 0 → 매수 압력 (0.15 이상 = 만점), CMF ≤ 0 → 0점
        cmf_intensity = 0.0
        if cmf_data:
            cmf_val = cmf_data["cmf"]
            if cmf_val > 0:
                cmf_intensity = min(cmf_val / 0.15, 1.0)

        obv_intensity = 1.0 if (obv and obv["divergence"] == "bullish") else 0.0
        volume_score = _cat_score(cmf_intensity, obv_intensity)

        # Pattern: LiquiditySweep = 1.5단위(최강 신호), 나머지 = 1단위
        # 2단위 이상 = 1.0  (LiquiditySweep 단독 → 0.75)
        if patterns:
            units = sum(1.5 if p == "LiquiditySweep" else 1.0 for p in patterns)
            pattern_score = min(units / 2.0, 1.0)
        else:
            pattern_score = 0.0

        # ── 가중 합산 ─────────────────────────────────────────
        total = (
            trend_score    * 0.35 +
            momentum_score * 0.25 +
            volume_score   * 0.25 +
            pattern_score  * 0.15
        )

        # ── 확인 게이트: 최소 2개 카테고리 활성 ──────────────
        active = sum(
            1 for s in [trend_score, momentum_score, volume_score, pattern_score]
            if s > 0
        )

        # trend(0.35)+momentum(0.25) = 0.60 → STRONG BUY 도달 가능하도록 조정
        if active < 2:
            grade = "NO SIGNAL"
        elif total >= 0.60:
            grade = "STRONG BUY"
        elif total >= 0.40:
            grade = "BUY"
        elif total >= 0.20:
            grade = "WATCH"
        else:
            grade = "NO SIGNAL"

        return {
            "signal_grade":    grade,
            "signal_score":    round(total, 3),
            "signal_breakdown": {
                "trend":    trend_score,
                "momentum": momentum_score,
                "volume":   volume_score,
                "pattern":  pattern_score,
            },
            "detected_patterns": patterns,
            "entry_low":   atr["entry_low"]   if atr else None,
            "entry_high":  atr["entry_high"]  if atr else None,
            "signal_stop": atr["signal_stop"] if atr else None,
        }

    except Exception as e:
        logger.debug(f"[Signal] 채점 실패: {e}")
        return {
            "signal_grade":    "NO SIGNAL",
            "signal_score":    0.0,
            "signal_breakdown": {
                "trend": 0.0, "momentum": 0.0,
                "volume": 0.0, "pattern": 0.0,
            },
            "entry_low":   None,
            "entry_high":  None,
            "signal_stop": None,
        }
