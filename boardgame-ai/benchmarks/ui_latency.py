"""UI 화면 갱신 응답성 분석 (지표 I).

WebSocket state_update 수신부터 paint 완료까지.

Frontend hook이 `ui_painted <state_version> <performance.now_ms>` 형식으로 기록.
같은 state_version에 대해:
- backend의 어떤 ws_send 시점부터 paint됐는지는 직접 매칭 어려움
  (state_version은 백엔드/프론트가 다른 타임라인 사용)

V1 측정: paint 사이 간격 + frontend 내부 setState→paint 지연.

향후 개선: backend에도 state_version별 ws_send ts hook 추가 → 양쪽 매칭.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.common.stats import summarize
from benchmarks.trace_collector import collect_to_list


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)

    paint_times_ms: list[float] = []
    state_versions_seen: list[int] = []
    for e in events:
        if e["event"] == "ui_painted" and len(e["args"]) >= 2:
            try:
                state_version = int(e["args"][0])
                perf_ms = float(e["args"][1])
                paint_times_ms.append(perf_ms)
                state_versions_seen.append(state_version)
            except ValueError:
                pass

    # 연속된 paint 사이 간격 (frontend frame jitter 지표)
    intervals_ms: list[float] = []
    for i in range(1, len(paint_times_ms)):
        diff = paint_times_ms[i] - paint_times_ms[i - 1]
        if 0 < diff < 60000:  # 60s 이상 갭은 idle 구간 제외
            intervals_ms.append(diff)

    return {
        "paint_count": len(paint_times_ms),
        "unique_state_versions": len(set(state_versions_seen)),
        "paint_interval_ms": summarize(intervals_ms),
        "note": "WS→paint matching 측정은 backend state_version hook 추가 필요 (M1 후속)",
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
