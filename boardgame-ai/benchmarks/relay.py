"""frontend → backend bench_log 통합 라우터.

frontend useBenchBridge가 250ms 배치로 보낸 lines를 backend bench_log에
그대로 INFO 기록한다. BENCH_TRACE=1이 아니면 bench_log 자체가 NullHandler라
실제 출력은 없음 (safe no-op).
"""

from __future__ import annotations

from benchmarks.common.trace_setup import bench_log


def handle_bench_trace(data: dict) -> None:
    """frontend bench_trace input → bench_log."""
    lines = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(lines, list):
        return
    log = bench_log()
    for line in lines:
        if isinstance(line, str) and line:
            log.info(line)
