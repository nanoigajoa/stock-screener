from config import (
    RSI_HARD_GATE, RSI_IDEAL_MIN, RSI_IDEAL_MAX,
    MIN_VOLUME_ABSOLUTE, MIN_RELATIVE_VOLUME,
)

_ALL_CHECKS = ["ma_alignment", "rsi", "volume", "macd", "support", "bollinger", "trend"]
_WEIGHTS = {"ma_alignment": 1, "rsi": 1, "volume": 1, "macd": 1, "support": 1, "bollinger": 1, "trend": 1}


def score_ticker(
    ind: dict,
    rsi_min: int = RSI_IDEAL_MIN,
    rsi_max: int = RSI_IDEAL_MAX,
    enabled_checks: list[str] | None = None,
) -> dict:
    """
    7개 체크리스트 채점.
    Returns: {items, total_score, max_score, hard_skip}
    """
    enabled = set(enabled_checks) if enabled_checks else set(_ALL_CHECKS)
    rsi = ind["rsi"]

    # RSI 하드게이트 — 나머지 채점 불필요
    if rsi >= RSI_HARD_GATE:
        max_score = sum(_WEIGHTS[k] for k in _ALL_CHECKS if k in enabled)
        return {
            "items": {},
            "total_score": 0,
            "max_score": max_score,
            "hard_skip": True,
            "hard_skip_reason": f"RSI {rsi:.1f} ≥ {RSI_HARD_GATE} (과매수)",
        }

    items = {}

    # 1. MA 정배열 — 완전 정배열만 통과
    p, m5, m20, m60, m120 = ind["price"], ind["ma5"], ind["ma20"], ind["ma60"], ind["ma120"]
    ma_vals_ok = all(v is not None for v in [m5, m20, m60, m120])

    if ma_vals_ok and p > m5 > m20 > m60 > m120:
        ma_pass = True
        ma_detail = f"완전 정배열: {p:.2f} > {m5:.2f} > {m20:.2f} > {m60:.2f} > {m120:.2f}"
    elif ma_vals_ok and p > m5 > m20:
        ma_pass = False
        ma_detail = f"단기 정배열만: {p:.2f} > {m5:.2f} > {m20:.2f} (60/120MA 미충족)"
    else:
        ma_pass = False
        ma_detail = "정배열 미충족" if ma_vals_ok else "MA 데이터 부족"

    items["ma_alignment"] = {
        "name": "이동평균선 정배열",
        "pass": ma_pass,
        "score": 1 if ma_pass else 0,
        "weight": 1,
        "detail": ma_detail,
    }

    # 2. RSI
    rsi_ok = rsi_min <= rsi <= rsi_max
    if rsi_ok:
        rsi_detail = f"RSI {rsi:.1f} (이상적 구간 {rsi_min}~{rsi_max})"
    elif rsi < rsi_min:
        rsi_detail = f"RSI {rsi:.1f} (과매도 구간)"
    else:
        rsi_detail = f"RSI {rsi:.1f} (주의 구간)"
    items["rsi"] = {"name": "RSI(14)", "pass": rsi_ok, "score": 1 if rsi_ok else 0, "weight": 1, "detail": rsi_detail}

    # 3. 거래량 — 상대 거래량 + 절대 거래량 이중 조건 (Task 3)
    vol_ma = ind["vol_ma20"]
    today_vol = ind["volume"]
    vol_ratio = (today_vol / vol_ma) if vol_ma and vol_ma > 0 else 0
    abs_ok = today_vol >= MIN_VOLUME_ABSOLUTE          # 절대량 200만 이상
    rel_ok = vol_ratio >= MIN_RELATIVE_VOLUME          # 상대량 1.5배 이상
    vol_ok = abs_ok and rel_ok

    if vol_ok:
        vol_detail = f"평균 대비 {vol_ratio:.1f}배 ({int(today_vol):,})"
    elif rel_ok and not abs_ok:
        vol_detail = f"상대량 OK({vol_ratio:.1f}배)지만 절대량 부족 ({int(today_vol):,} < {MIN_VOLUME_ABSOLUTE:,})"
    else:
        vol_detail = f"거래량 미충족 ({vol_ratio:.1f}배, {int(today_vol):,})"

    items["volume"] = {
        "name": "거래량",
        "pass": vol_ok,
        "score": 1 if vol_ok else 0,
        "weight": 1,
        "detail": vol_detail,
    }

    # 4. MACD 골든크로스
    macd_ok = (
        ind["macd"] is not None and ind["macd_signal"] is not None and
        ind["macd"] > ind["macd_signal"]
    )
    items["macd"] = {
        "name": "MACD",
        "pass": macd_ok,
        "score": 1 if macd_ok else 0,
        "weight": 1,
        "detail": f"MACD {ind['macd']:.3f} / Signal {ind['macd_signal']:.3f}" if ind["macd"] else "데이터 없음",
    }

    # 5. 동적 지지선 (MA60) — 중기 이평선 위 0~8% 이내 눌림목 타점
    ma60 = ind.get("ma60")
    if ma60 and ma60 > 0:
        support_ok = ma60 <= p <= ma60 * 1.08
        pct = (p / ma60 - 1) * 100
        detail = (
            f"MA60 지지 ${ma60:.2f} 근방 +{pct:.1f}%"
            if support_ok else
            f"MA60 ${ma60:.2f} 대비 {pct:+.1f}% (범위 초과)"
        )
    else:
        support_ok = False
        detail = "MA60 데이터 없음"
    items["support"] = {
        "name": "지지/저항",
        "pass": support_ok,
        "score": 1 if support_ok else 0,
        "weight": 1,
        "detail": detail,
    }

    # 6. 볼린저밴드 중간선 위 (weight 1)
    bb_ok = ind["bb_middle"] is not None and ind["price"] > ind["bb_middle"]
    items["bollinger"] = {
        "name": "볼린저밴드",
        "pass": bb_ok,
        "score": 1 if bb_ok else 0,
        "weight": 1,
        "detail": f"중간선 ${ind['bb_middle']:.2f} {'위 (강세)' if bb_ok else '아래 (약세)'}",
    }

    # 7. 추세 지속성 (weight 1)
    trend_ok = ind["higher_high"] and ind["higher_low"]
    items["trend"] = {
        "name": "추세 지속성",
        "pass": trend_ok,
        "score": 1 if trend_ok else 0,
        "weight": 1,
        "detail": "Higher High + Higher Low 구조" if trend_ok else "추세 미확인",
    }

    # enabled_checks 필터 적용 — 비활성 항목 제거
    if enabled_checks:
        items = {k: v for k, v in items.items() if k in enabled}

    total_score = sum(v["score"] for v in items.values())
    max_score = sum(_WEIGHTS[k] for k in _ALL_CHECKS if k in enabled)

    return {"items": items, "total_score": total_score, "max_score": max_score, "hard_skip": False}
