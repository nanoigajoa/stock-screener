"""
백그라운드 배치 스케줄러.
FastAPI startup에서 호출 → 데몬 스레드로 24h 주기 실행.
"""
import sys
import threading
import time
import logging

logger = logging.getLogger(__name__)

# 각 태스크 예상 소요 시간 (초)
_ESTIMATES = {
    "매크로(FRED)": 8,
    "공포탐욕지수": 15,
}

_BAR_WIDTH = 22


def start() -> None:
    """앱 시작 시 1회 호출. 즉시 첫 배치 실행 후 24h 주기 반복."""
    t = threading.Thread(target=_loop, daemon=True, name="batch-scheduler")
    t.start()
    logger.info("[Scheduler] 배치 스케줄러 시작")


def _loop() -> None:
    _run_all()
    while True:
        time.sleep(86400)  # 24h
        _run_all()


def _run_all() -> None:
    total_est = sum(_ESTIMATES.values())
    _print(f"")
    _print(f"┌{'─' * 44}┐")
    _print(f"│  📦 배치 데이터 로드 시작  (예상 {total_est}초)          │")
    _print(f"└{'─' * 44}┘")

    batch_start = time.perf_counter()
    _safe_run("매크로(FRED)", _refresh_macro)
    _safe_run("공포탐욕지수", _refresh_fear_greed)
    elapsed = time.perf_counter() - batch_start

    _print(f"")
    _print(f"✅ 배치 완료 — 총 {elapsed:.1f}초 (예상 {total_est}초)")
    _print(f"")


def _safe_run(name: str, fn) -> None:
    est = _ESTIMATES.get(name, 10)
    _print(f"")
    _print(f"  ▶ [{name}]  예상 ~{est}초")

    stop_evt = threading.Event()
    prog_thread = threading.Thread(
        target=_progress_loop,
        args=(name, est, stop_evt),
        daemon=True,
    )
    prog_thread.start()

    t0 = time.perf_counter()
    error = None
    try:
        fn()
    except Exception as e:
        error = e
    finally:
        elapsed = time.perf_counter() - t0
        stop_evt.set()
        prog_thread.join()

    # 게이지 라인 지우고 최종 결과 출력
    _clear_line()
    if error:
        _print(f"  ✗ [{name}]  실패 {elapsed:.1f}s — {error}")
        logger.error(f"[Scheduler] [{name}] 실패 ({elapsed:.1f}초): {error}")
    else:
        bar = "█" * _BAR_WIDTH
        _print(f"  ✔ [{name}]  {bar}  {elapsed:.1f}s / ~{est}s (완료)")
        logger.info(f"[Scheduler] [{name}] 완료 ({elapsed:.1f}초)")


def _progress_loop(name: str, est: float, stop: threading.Event) -> None:
    """0.25초마다 같은 줄을 \r로 덮어써서 실시간 게이지 표시."""
    start = time.perf_counter()
    while not stop.is_set():
        elapsed = time.perf_counter() - start
        ratio = min(elapsed / est, 1.0)
        filled = int(_BAR_WIDTH * ratio)
        bar = "█" * filled + "░" * (_BAR_WIDTH - filled)
        pct = int(ratio * 100)
        line = f"  ○ [{name}]  {bar}  {elapsed:.1f}s / ~{est}s  ({pct}%)"
        sys.stdout.write(f"\r{line}   ")
        sys.stdout.flush()
        stop.wait(0.25)


def _clear_line() -> None:
    sys.stdout.write("\r" + " " * 72 + "\r")
    sys.stdout.flush()


def _print(msg: str) -> None:
    print(msg, flush=True)


def _refresh_macro() -> None:
    from screener.macro_fetcher import refresh_macro
    refresh_macro()


def _refresh_fear_greed() -> None:
    from screener.fear_greed_fetcher import get_fear_greed
    get_fear_greed()
