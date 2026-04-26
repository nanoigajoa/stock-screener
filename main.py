import argparse
import schedule
import time

from config import SHOW_GRADES, SCHEDULE_TIME
from services.screener_service import run_analysis
from notifier.terminal import print_result, print_summary_header, print_no_results
from utils.logger import save_to_csv


def run(tickers_override: list[str] | None = None, grade_filter: str | None = None, save: bool = False) -> None:
    print("\n🔍 스크리닝 시작...\n", flush=True)

    data = run_analysis(tickers_override, grade_filter)
    displayable = data["displayable"]
    results = data["results"]

    if not displayable:
        print_no_results()
    else:
        show_grades = [grade_filter.upper()] if grade_filter else SHOW_GRADES
        for g in show_grades:
            group = [r for r in displayable if r["grade"] == g]
            if group:
                print_summary_header(g, len(group))
                for r in group:
                    print_result(r)

    if save:
        save_to_csv(results)

    s = data["summary"]
    print(f"\n[완료] 총 {s['total']}개 분석 | SKIP {s['skipped']}개 | 표시 {s['displayed']}개\n", flush=True)


def _prompt_tickers() -> list[str] | None:
    """대화형 티커 입력. 빈 입력이면 None(전체 스캔) 반환."""
    from colorama import Fore, Style
    print(Fore.CYAN + "\n" + "=" * 45)
    print("  📈 미국 주식 자동 스크리너")
    print("=" * 45 + Style.RESET_ALL)
    print("  [1] 전체 Finviz 스캔 (필터 자동 적용)")
    print("  [2] 종목 직접 입력")
    print()

    while True:
        choice = input("  선택 (1/2): ").strip()
        if choice == "1":
            return None
        if choice == "2":
            raw = input("  티커 입력 (예: AAPL MSFT NVDA): ").strip().upper()
            tickers = [t for t in raw.split() if t]
            if tickers:
                return tickers
            print("  ⚠️  티커를 하나 이상 입력해주세요.")
        else:
            print("  ⚠️  1 또는 2를 입력해주세요.")


def _prompt_options() -> dict:
    """등급 필터 / CSV 저장 여부 묻기."""
    from colorama import Fore, Style

    print()
    grade_input = input("  등급 필터 (S/A/B/전체, 기본=전체): ").strip().upper()
    grade_filter = grade_input if grade_input in ("S", "A", "B") else None

    save_input = input("  결과 CSV 저장? (y/n, 기본=n): ").strip().lower()
    save = save_input == "y"

    print(Fore.CYAN + "=" * 45 + Style.RESET_ALL + "\n")
    return {"grade_filter": grade_filter, "save": save}


def main() -> None:
    parser = argparse.ArgumentParser(description="미국 주식 자동 스크리너")
    parser.add_argument("--schedule", action="store_true", help=f"매일 {SCHEDULE_TIME} 자동 실행")
    parser.add_argument("--ticker", nargs="+", metavar="TICKER", help="특정 종목만 분석")
    parser.add_argument("--grade", choices=["S", "A", "B", "SKIP"], help="특정 등급만 출력")
    parser.add_argument("--save", action="store_true", help="결과를 CSV로 저장")
    args = parser.parse_args()

    # --schedule은 대화형 없이 바로 실행
    if args.schedule:
        kwargs = {"tickers_override": args.ticker, "grade_filter": args.grade, "save": args.save}
        print(f"스케줄 모드: 매일 {SCHEDULE_TIME} 실행", flush=True)
        schedule.every().day.at(SCHEDULE_TIME).do(run, **kwargs)
        run(**kwargs)
        while True:
            schedule.run_pending()
            time.sleep(30)
        return

    # CLI 인수가 있으면 대화형 스킵
    if args.ticker or args.grade or args.save:
        run(tickers_override=args.ticker, grade_filter=args.grade, save=args.save)
        return

    # 대화형 모드
    while True:
        tickers = _prompt_tickers()
        opts = _prompt_options()
        run(tickers_override=tickers, **opts)

        print()
        again = input("  다시 실행하시겠습니까? (y/n): ").strip().lower()
        if again != "y":
            print("\n  종료합니다. 👋\n")
            break


if __name__ == "__main__":
    main()
