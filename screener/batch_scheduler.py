"""
백그라운드 배치 스케줄러 (FastAPI Native 버젼)
"""
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

async def start_background_scheduler() -> asyncio.Task:
    """FastAPI lifespan 시작 시 호출. Task 객체를 반환해 종료 시 취소 가능하게 함."""
    logger.info("[Scheduler] 비동기 배치 스케줄러 엔진 가동")
    return asyncio.create_task(_loop())

async def _loop() -> None:
    """24시간 주기로 _run_all을 비동기 실행. CancelledError로 graceful shutdown."""
    try:
        while True:
            await _run_all()
            await asyncio.sleep(86400)
    except asyncio.CancelledError:
        logger.info("[Scheduler] 스케줄러 루프가 종료 신호를 받고 멈춥니다.")
        raise

async def _run_all() -> None:
    logger.info("=" * 50)
    logger.info("📦 [배치] 데이터 로드 파이프라인 시작")

    start_time = time.perf_counter()

    try:
        await asyncio.to_thread(_refresh_macro)
        elapsed = time.perf_counter() - start_time
        logger.info(f"✔ [매크로(FRED)] 수집 완료 ({elapsed:.1f}초)")
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error(f"✗ [매크로(FRED)] 수집 실패 ({elapsed:.1f}초): {e}")

    try:
        t = time.perf_counter()
        await asyncio.to_thread(_refresh_sidebar)
        logger.info(f"✔ [사이드바 Live] 수집 완료 ({time.perf_counter()-t:.1f}초)")
    except Exception as e:
        logger.error(f"✗ [사이드바 Live] 수집 실패: {e}")

    logger.info("=" * 50)

def _refresh_macro() -> None:
    from screener.macro_fetcher import refresh_macro
    refresh_macro()

def _refresh_sidebar() -> None:
    from screener.macro_fetcher import refresh_sidebar
    refresh_sidebar()