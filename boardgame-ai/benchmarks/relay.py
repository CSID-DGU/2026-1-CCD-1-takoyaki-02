"""frontend → backend bench_log 통합 라우터.

frontend useBenchBridge가 250ms 배치로 보낸 lines를 backend bench_log에
그대로 INFO 기록한다. BENCH_TRACE=1이 아니면 즉시 return.

보안: 외부(클라이언트)에서 들어온 임의 문자열을 서버 로그에 기록하므로
디스크/로그 폭주를 막기 위해 한 호출당 라인 수와 라인 길이에 상한을 둔다.
"""

from __future__ import annotations

from benchmarks.common.trace_setup import bench_log, is_bench

# 한 호출당 최대 라인 수 / 라인당 최대 길이. 정상 frontend 배치는 32라인 미만, 200자 미만.
_MAX_LINES_PER_CALL = 64
_MAX_LINE_LENGTH = 1024


def handle_bench_trace(data: dict) -> None:
    """frontend bench_trace input → bench_log."""
    # BENCH_TRACE=0이면 클라이언트가 어떤 데이터를 보내도 즉시 폐기.
    if not is_bench():
        return
    lines = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(lines, list):
        return
    log = bench_log()
    for line in lines[:_MAX_LINES_PER_CALL]:
        if isinstance(line, str) and line:
            log.info(line[:_MAX_LINE_LENGTH])
