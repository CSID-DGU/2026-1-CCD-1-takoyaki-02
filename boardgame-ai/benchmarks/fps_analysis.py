"""비전 처리 FPS 분석 (지표 J).

pipeline_enter <frame_id> <ts> 라인을 모아 1초당 처리 frame 수 계산.
30fps 목표 대비 drop rate, 30분 시계열 segmented (5분 단위).
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.common.stats import summarize
from benchmarks.trace_collector import collect_to_list

TARGET_FPS = 30
SEGMENT_SEC = 300  # 5분


def analyze(log_path: Path, target_fps: int = TARGET_FPS) -> dict:
    events = collect_to_list(log_path)

    # 각 pipeline_enter의 (frame_id, ts) 수집
    timeline: list[tuple[int, float]] = []
    for e in events:
        if e["event"] == "pipeline_enter" and len(e["args"]) >= 2:
            try:
                fid = int(e["args"][0])
                ts = float(e["args"][1])
                timeline.append((fid, ts))
            except ValueError:
                pass

    if len(timeline) < 2:
        return {"error": "not enough samples", "samples": len(timeline)}

    timeline.sort(key=lambda x: x[1])
    start_ts = timeline[0][1]
    end_ts = timeline[-1][1]
    total_sec = end_ts - start_ts

    # 1초 bucket으로 FPS 계산
    buckets: dict[int, int] = {}
    for _, ts in timeline:
        bucket = int(ts - start_ts)
        buckets[bucket] = buckets.get(bucket, 0) + 1

    fps_per_sec = list(buckets.values())

    # Segmented (5분 단위)
    segments: list[dict] = []
    for seg_start in range(0, int(total_sec), SEGMENT_SEC):
        seg_fps = [
            fps for s, fps in buckets.items()
            if seg_start <= s < seg_start + SEGMENT_SEC
        ]
        if seg_fps:
            segments.append({
                "minute_range": f"{seg_start // 60}-{(seg_start + SEGMENT_SEC) // 60}",
                "mean_fps": sum(seg_fps) / len(seg_fps),
                "min_fps": min(seg_fps),
            })

    drop_rate = max(0.0, 1.0 - (len(timeline) / (total_sec * target_fps)))

    return {
        "target_fps": target_fps,
        "total_frames": len(timeline),
        "duration_sec": round(total_sec, 1),
        "fps_summary": summarize([float(v) for v in fps_per_sec]),
        "drop_rate": round(drop_rate, 4),
        "by_segment": segments,
    }


def run(session_dir: Path) -> dict:
    log_path = session_dir / "raw" / "app.log"
    if not log_path.exists():
        return {"error": "no log"}
    result = analyze(log_path)
    (session_dir / "fps_analysis.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    return result
