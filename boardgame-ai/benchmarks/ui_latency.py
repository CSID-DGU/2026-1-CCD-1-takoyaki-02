"""UI 화면 갱신 응답성 분석 (지표 I).

WebSocket state_update 수신부터 paint 완료까지.

Frontend hook이 `ui_update_latency <state_version> <seq> <received_ms>
<painted_ms> <latency_ms>` 형식으로 기록.

측정 구간:
- state_update WebSocket 메시지를 브라우저가 받은 시점
- React setState 호출 후 다음 requestAnimationFrame paint 시점

프론트 내부 같은 performance.now() 타임라인만 사용하므로 backend time.time()과
브라우저 performance.now()를 섞어서 생기는 시계 오차가 없다.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.common.stats import summarize
from benchmarks.trace_collector import collect_to_list


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)

    update_latencies_ms: list[float] = []
    receive_times_ms: list[float] = []
    paint_times_ms: list[float] = []
    state_versions_seen: list[int] = []
    for e in events:
        if e["event"] == "ui_update_latency" and len(e["args"]) >= 5:
            try:
                state_version = int(e["args"][0])
                received_ms = float(e["args"][2])
                painted_ms = float(e["args"][3])
                latency_ms = float(e["args"][4])
                if 0 <= latency_ms < 60000:
                    update_latencies_ms.append(latency_ms)
                    receive_times_ms.append(received_ms)
                    paint_times_ms.append(painted_ms)
                    state_versions_seen.append(state_version)
            except ValueError:
                pass
        elif e["event"] == "ui_painted" and len(e["args"]) >= 2:
            try:
                state_version = int(e["args"][0])
                perf_ms = float(e["args"][1])
                # 구버전 로그 호환: ui_update_latency가 없을 때만 paint interval에 사용.
                if not update_latencies_ms:
                    paint_times_ms.append(perf_ms)
                    state_versions_seen.append(state_version)
            except ValueError:
                pass

    intervals_source = receive_times_ms if update_latencies_ms else paint_times_ms

    # 연속 state_update 수신 또는 구버전 paint 사이 간격 (frontend frame jitter 지표)
    intervals_ms: list[float] = []
    for i in range(1, len(intervals_source)):
        diff = intervals_source[i] - intervals_source[i - 1]
        if 0 < diff < 60000:  # 60s 이상 갭은 idle 구간 제외
            intervals_ms.append(diff)

    return {
        "paint_count": len(paint_times_ms),
        "unique_state_versions": len(set(state_versions_seen)),
        "ws_receive_to_paint_ms": summarize(update_latencies_ms),
        "paint_interval_ms": summarize(intervals_ms),
        "note": (
            "ws_receive_to_paint_ms는 브라우저가 state_update를 받은 뒤 다음 paint까지의 "
            "프론트 내부 화면 갱신 시간입니다."
        ),
    }


def run(session_dir: Path) -> dict:
    log_path = session_dir / "raw" / "app.log"
    if not log_path.exists():
        return {"error": "no log"}
    result = analyze(log_path)
    (session_dir / "ui_latency.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    return result
