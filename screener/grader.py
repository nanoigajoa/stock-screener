from config import TARGET_1_PCT, TARGET_2_PCT, STOP_LOSS_PCT


_GRADE_THRESHOLDS = [("S", 6), ("A", 4), ("B", 2)]


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
    assigned_grade = "SKIP"
    for g, threshold in _GRADE_THRESHOLDS:
        if score >= threshold:
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
