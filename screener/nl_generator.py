"""
기술적 지표와 매매 시그널을 결합하여 한국어 자연어 브리핑 생성.
"""

def generate_summary(foundation: dict, timing: dict) -> str:
    """
    기초 체력(foundation)과 매매 타이밍(timing) 데이터를 바탕으로
    한 문장 내외의 요약 브리핑 생성.
    """
    try:
        # 1. 기초 체력 요약
        grade = foundation.get("grade", "SKIP")
        score = foundation.get("score", 0)
        max_sc = foundation.get("max_score", 7)
        
        checks = foundation.get("checklist", {})
        ma_pass = checks.get("ma_alignment", {}).get("pass", False)
        
        # 2. 타이밍 요약
        sig_grade = timing.get("signal_grade", "NO SIGNAL")
        breakdown = timing.get("signal_breakdown", {})
        patterns = timing.get("detected_patterns", [])
        
        entry_score    = breakdown.get("entry", 0)
        momentum_score = breakdown.get("momentum", 0)
        volume_score   = breakdown.get("volume", 0)
        
        # ── 문장 조합 로직 ──────────────────────────────
        parts = []
        
        # 기초 체력(추세)
        if ma_pass:
            parts.append("이동평균선 정배열로 탄탄한 우상향 궤도에 있으며")
        elif grade != "SKIP" and score >= max_sc * 0.5:
            parts.append("기술적 기초 체력은 양호한 편이나")
        else:
            parts.append("현재 전반적인 추세는 정체되거나 약세 흐름이지만")
            
        # 캔들 패턴 (차트 모양) 추가
        if patterns:
            pattern_str = ", ".join(patterns)
            parts.append(f"최근 차트에서 '{pattern_str}' 패턴이 포착되어")

        # 타이밍(수급/모멘텀)
        if sig_grade == "STRONG BUY":
            parts.append("지금 당장 수급과 모멘텀이 동시에 폭발하는 골든 타임입니다.")
        elif sig_grade == "BUY":
            if entry_score >= 0.5 and momentum_score >= 0.5:
                parts.append("상승 추세 속에서 매수세가 붙기 시작한 좋은 진입 시점입니다.")
            elif volume_score >= 0.5:
                parts.append("강한 거래량이 동반되며 단기 반등을 준비하는 모습입니다.")
            else:
                parts.append("점진적으로 매수 매력도가 높아지는 구간입니다.")
        elif sig_grade == "WATCH":
            parts.append("조금 더 확실한 반등 신호를 기다리며 관망할 필요가 있습니다.")
        else:
            parts.append("아직은 뚜렷한 매수 신호가 포착되지 않고 있습니다.")

        return " ".join(parts)

    except Exception:
        return "기술적 데이터 분석을 통해 매매 전략을 검토 중입니다."
