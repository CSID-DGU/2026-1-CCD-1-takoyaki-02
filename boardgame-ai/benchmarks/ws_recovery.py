"""WebSocket 끊김 복구 분석 (지표 E).

이미 박힌 hook:
  ws_attach <path> <ts>
  ws_disconnect <path> <ts>

매칭 규칙: 같은 path의 disconnect 직후 첫 attach까지를 1회 복구로 묶음.
경로별 + 전체 복구 시간 p50/p95/p99, 복구율(=모든 disconnect가 복구됐는지) 계산.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.common.stats import summarize
from benchmarks.trace_collector import collect_to_list


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)

    # path별 (event, ts) 시퀀스 수집
    by_path: dict[str, list[tuple[str, float]]] = {}
    for e in events:
        ev = e["event"]
        if ev not in ("ws_attach", "ws_disconnect"):
            continue
        if len(e["args"]) < 2:
            continue
        path = e["args"][0]
        try:
            ts = float(e["args"][1])
        except ValueError:
            continue
        by_path.setdefault(path, []).append(("attach" if ev == "ws_attach" else "disconnect", ts))

    # disconnect → 다음 attach 매칭
    recoveries: list[float] = []
    total_disconnects = 0
    auto_recoveries = 0
    by_path_summary: dict[str, dict] = {}
    for path, seq in by_path.items():
        seq.sort(key=lambda x: x[1])
        path_disc = 0
        path_rec = 0
        path_times: list[float] = []
        pending_disc_ts: float | None = None
        for ev, ts in seq:
            if ev == "disconnect":
                pending_disc_ts = ts
                path_disc += 1
                total_disconnects += 1
            else:  # attach
                if pending_disc_ts is not None:
                    delta_ms = (ts - pending_disc_ts) * 1000
                    if delta_ms >= 0:
                        recoveries.append(delta_ms)
                        path_times.append(delta_ms)
                        path_rec += 1
                        auto_recoveries += 1
                    pending_disc_ts = None
        by_path_summary[path] = {
            "disconnects": path_disc,
            "recoveries": path_rec,
            "recovery_time_ms": summarize(path_times),
        }

    return {
        "total_disconnects": total_disconnects,
        "auto_recoveries": auto_recoveries,
        "recovery_rate": (auto_recoveries / total_disconnects) if total_disconnects else 1.0,
        "recovery_time_ms": summarize(recoveries),
        "by_path": by_path_summary,
    }


def run(session_dir: Path) -> dict:
    log_path = session_dir / "raw" / "app.log"
    if not log_path.exists():
        return {"error": "no log"}
    result = analyze(log_path)
    (session_dir / "ws_recovery.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    return result
