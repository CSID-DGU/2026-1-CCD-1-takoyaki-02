"""측정 모드 활성화 + bench 전용 logger 설정.

BENCH_TRACE=1 환경변수가 켜졌을 때만 동작. 그 외엔 모든 함수가 no-op.
다른 모듈에서 hook을 박을 때 다음 패턴을 사용:

    from benchmarks.common.trace_setup import is_bench, bench_log

    if is_bench():
        bench_log().info("frame_capture %d %.6f", frame_id, time.time())

또는 더 짧게 (조건 체크가 logger 내부에서 됨):

    from benchmarks.common.trace_setup import bench_log
    bench_log().info("frame_capture %d %.6f", frame_id, time.time())

bench_log()는 BENCH_TRACE=0이면 NullHandler만 달린 logger를 반환하므로
실제 출력은 없지만 호출 자체는 안전. 다만 % formatting 비용은 약간 발생.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_BENCH_LOGGER_NAME = "bench"
_initialized = False
_session_dir: Path | None = None


def is_bench() -> bool:
    """BENCH_TRACE=1 환경변수가 켜졌는지 확인."""
    return os.environ.get("BENCH_TRACE") == "1"


def bench_log() -> logging.Logger:
    """bench 전용 logger 반환. is_bench()가 False면 NullHandler만 달림.

    호출 비용이 작아 hook 박을 때마다 if 체크 없이 그냥 호출해도 OK.
    """
    return logging.getLogger(_BENCH_LOGGER_NAME)


def setup_bench_logger(session_dir: Path) -> None:
    """BenchmarkSession.start()에서 1회 호출. session_dir/raw/app.log로 라우팅.

    이후 bench_log().info(...) 호출은 모두 그 파일에 쌓임.
    """
    global _initialized, _session_dir

    if _initialized:
        return

    logger = logging.getLogger(_BENCH_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # root로 새지 않도록

    raw_dir = session_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    log_path = raw_dir / "app.log"

    # 10MB × 3 rotation. 측정 1회 분량은 충분히 담김.
    handler = RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(message)s",
                                            datefmt="%Y-%m-%dT%H:%M:%S"))
    logger.addHandler(handler)

    _session_dir = session_dir
    _initialized = True


def teardown_bench_logger() -> None:
    """BenchmarkSession.finalize()에서 호출. 핸들러 정리."""
    global _initialized, _session_dir
    logger = logging.getLogger(_BENCH_LOGGER_NAME)
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)
    _initialized = False
    _session_dir = None


def session_dir() -> Path | None:
    """현재 측정 세션 디렉토리 반환. start 전이면 None."""
    return _session_dir
