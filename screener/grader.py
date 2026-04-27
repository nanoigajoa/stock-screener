from config import TARGET_1_PCT, TARGET_2_PCT, STOP_LOSS_PCT

# 비율 기반 임계값 — 6/9≈0.67, 4/9≈0.44, 2/9≈0.22 (기존 기준 그대로)
_GRADE_RATIOS = [("S", 0.67), ("A", 0.44), ("B", 0.22)]


def grade(score_result: dict, ticker: str, price: float) -> dict:
    """채점 결과 → 등급 + 목표가/손절 계산."""
    if score_result["hard_skip"]:
        return {
            "ticker": ticker,
            "price": price,
            "grade": "SKIP",
            "score": 0,
            "reason": score_result["hard_skip_reason"],
            "checklist": {},
            "target_1": None,
            "target_2": None,
            "stop_loss": None,
        }

    score = score_result["total_score"]
    max_score = score_result.get("max_score", 9)
    ratio = score / max_score if max_score > 0 else 0
    assigned_grade = "SKIP"
    for g, threshold in _GRADE_RATIOS:
        if ratio >= threshold:
            assigned_grade = g
            break

    action_map = {
        "S": "즉시 전량 진입 가능",
        "A": "분할 진입 검토 (1차 50% → 조건 확인 후 2차 50%)",
        "B": "대기 — 조건 미충족",
        "SKIP": "진입 금지",
    }

    return {
        "ticker": ticker,
        "price": price,
        "grade": assigned_grade,
        "score": score,
        "action": action_map[assigned_grade],
        "checklist": score_result["items"],
        "target_1": round(price * (1 + TARGET_1_PCT), 2),
        "target_2": round(price * (1 + TARGET_2_PCT), 2),
        "stop_loss": round(price * (1 - STOP_LOSS_PCT), 2),
    }
