from colorama import init, Fore, Style

init(autoreset=True)

_GRADE_COLOR = {
    "S": Fore.GREEN,
    "A": Fore.YELLOW,
    "B": Fore.CYAN,
    "SKIP": Fore.RED,
}

_GRADE_LABEL = {
    "S": "⭐ S급 — 즉시 진입 가능",
    "A": "🟡 A급 — 분할 진입 검토",
    "B": "🔵 B급 — 대기",
    "SKIP": "❌ SKIP — 진입 금지",
}


def _check_icon(passed: bool) -> str:
    return Fore.GREEN + "✅" if passed else Fore.RED + "❌"


def print_result(result: dict) -> None:
    grade = result["grade"]
    color = _GRADE_COLOR.get(grade, "")
    line = "=" * 45

    print(color + line)
    print(color + f"📊 {result['ticker']} — ${result['price']:.2f} | {_GRADE_LABEL[grade]}")
    print(color + line)

    if grade == "SKIP" and not result.get("checklist"):
        print(Fore.RED + f"  사유: {result.get('reason', '')}")
    else:
        for key, item in result["checklist"].items():
            icon = _check_icon(item["pass"])
            print(f"  {icon}{Style.RESET_ALL} {item['name']}: {item['detail']}")

    if grade != "SKIP":
        print(Style.RESET_ALL + f"\n  판단: {result['action']}")
        print(f"  1차 목표가: ${result['target_1']} (+8%)")
        print(f"  2차 목표가: ${result['target_2']} (+15%)")
        print(f"  손절선:     ${result['stop_loss']} (-15%)")

    print(Style.RESET_ALL + color + line + Style.RESET_ALL)
    print()


def print_summary_header(grade: str, count: int) -> None:
    color = _GRADE_COLOR.get(grade, "")
    print(color + f"\n{'=' * 45}")
    print(color + f"  {_GRADE_LABEL[grade]} — {count}종목")
    print(color + f"{'=' * 45}" + Style.RESET_ALL)


def print_no_results() -> None:
    print(Fore.YELLOW + "\n조건에 맞는 종목이 없습니다." + Style.RESET_ALL)
