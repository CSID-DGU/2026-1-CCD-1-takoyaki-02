"""TTS 캐시 적중률 분석 (지표 D).

tts_synth_done hit=<0|1> layer=<static|session|dynamic> elapsed_ms=<f>
라인을 집계해 전체/layer별 hit rate + 절감 효과 계산.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.trace_collector import collect_to_list


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)

    by_layer: dict[str, dict] = {}
    miss_elapsed_ms: list[float] = []
    total_hits = 0
    total_misses = 0

    for e in events:
        if e["event"] != "tts_synth_done":
            continue
        kv = e["kv"]
        try:
            hit = kv.get("hit", "0") == "1"
            layer = kv.get("layer", "?")
            elapsed_ms = float(kv.get("elapsed_ms", 0))
        except ValueError:
            continue

        by_layer.setdefault(layer, {"hits": 0, "misses": 0})
        if hit:
            by_layer[layer]["hits"] += 1
            total_hits += 1
        else:
            by_layer[layer]["misses"] += 1
            total_misses += 1
            miss_elapsed_ms.append(elapsed_ms)

    total = total_hits + total_misses
    hit_rate = total_hits / total if total else 0.0

    # 절감 시간 = hit 횟수 × (miss 평균 합성 시간)
    avg_miss_ms = (sum(miss_elapsed_ms) / len(miss_elapsed_ms)) if miss_elapsed_ms else 0.0
    estimated_saved_sec = total_hits * avg_miss_ms / 1000

    return {
        "total": total,
        "hits": total_hits,
        "misses": total_misses,
        "hit_rate": round(hit_rate, 4),
        "by_layer": by_layer,
        "avg_miss_synth_ms": round(avg_miss_ms, 1),
        "estimated_api_time_saved_sec": round(estimated_saved_sec, 1),
    }


def run(session_dir: Path) -> dict:
    log_path = session_dir / "raw" / "app.log"
    if not log_path.exists():
        return {"error": "no log"}
    result = analyze(log_path)
    (session_dir / "cache_hit_rate.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    return result
