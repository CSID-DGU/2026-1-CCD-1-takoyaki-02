"""음성 채널별 응답 시간 분석 (지표 A).

채널 정의:
- **sfx**: SFX 효과음. audio_broadcast args[0] == 'sfx_play'
- **tts_cached**: 캐시 hit으로 즉시 broadcast된 TTS
- **tts_synth**: 캐시 miss로 합성 후 broadcast된 TTS
- **llm**: LLM 멘트 (현재 없음, 후속)

각 channel의 측정 구간:
- **enqueue→play_start**: backend가 큐에 넣은 시점 → frontend 첫 음
  (가장 신뢰 가능한 측정. 모든 채널 공통)
- **synth_ms** (TTS만): 합성 자체 소요 (tts_synth_done elapsed_ms)

사용자 체감은 별도(consumer_perceived.py 또는 channel_latency 결과에서 도출).
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.common.stats import summarize
from benchmarks.trace_collector import collect_to_list


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)

    # 1. playback_id → 채널 + enqueue ts
    enqueue: dict[str, dict] = {}
    for e in events:
        if e["event"] == "audio_enqueue" and len(e["args"]) >= 3:
            msg_type, pbid, ts = e["args"][0], e["args"][1], e["args"][2]
            try:
                enqueue[pbid] = {"msg_type": msg_type, "enqueue_ts": float(ts)}
            except ValueError:
                pass

    # 2. audio_broadcast로 backend 송신 ts + 직전 tts_synth_done 매칭.
    # tts_synth_done은 playback_id가 없지만(캐시 key 기준), _broadcast_item에서
    # cache_hit/synthesize(→ tts_synth_done 로깅) 직후 곧바로 audio_broadcast를
    # 로깅한다. 따라서 로그 순서상 각 tts_play broadcast 직전의 synth_done이
    # 바로 그 broadcast의 것 — 이 인접성으로 1:1 매칭(순차 pop 드리프트 제거).
    broadcast: dict[str, float] = {}
    broadcast_synth: dict[str, dict] = {}
    last_synth: dict | None = None
    for e in events:
        if e["event"] == "tts_synth_done":
            kv = e["kv"]
            try:
                last_synth = {
                    "hit": kv.get("hit", "0") == "1",
                    "layer": kv.get("layer", "?"),
                    "elapsed_ms": float(kv.get("elapsed_ms", 0)),
                }
            except ValueError:
                last_synth = None
        elif e["event"] == "audio_broadcast" and len(e["args"]) >= 3:
            # msg_type pbid ts
            msg_type, pbid, ts = e["args"][0], e["args"][1], e["args"][2]
            try:
                broadcast[pbid] = float(ts)
            except ValueError:
                continue
            if msg_type == "tts_play" and last_synth is not None:
                broadcast_synth[pbid] = last_synth
            # 매칭 후 소비 — 다음 broadcast가 같은 synth를 재사용하지 않도록.
            last_synth = None

    # 3. 채널별 분류 + latency 집계.
    # 주의: enqueue→broadcast는 큐 직렬화 대기를 포함한다. 이전 오디오 재생이
    # 끝나야(_maybe_push_next) 다음 항목이 broadcast되므로, cached 항목도 큐가
    # 밀려 있으면 latency가 커진다 — 순수 합성/조회 비용은 synth_ms를 참고.
    by_channel: dict[str, dict] = {
        "sfx": {"latencies_ms": [], "count": 0},
        "tts_cached": {"latencies_ms": [], "count": 0, "synth_ms": []},
        "tts_synth": {"latencies_ms": [], "count": 0, "synth_ms": []},
    }

    for pbid, info in enqueue.items():
        msg_type = info["msg_type"]
        enq_ts = info["enqueue_ts"]
        bcast_ts = broadcast.get(pbid)
        if bcast_ts is None:
            continue
        latency_ms = (bcast_ts - enq_ts) * 1000

        if msg_type == "sfx_play":
            by_channel["sfx"]["latencies_ms"].append(latency_ms)
            by_channel["sfx"]["count"] += 1
        elif msg_type == "tts_play":
            synth = broadcast_synth.get(pbid)
            if synth and synth["hit"]:
                by_channel["tts_cached"]["latencies_ms"].append(latency_ms)
                by_channel["tts_cached"]["synth_ms"].append(synth["elapsed_ms"])
                by_channel["tts_cached"]["count"] += 1
            elif synth:
                by_channel["tts_synth"]["latencies_ms"].append(latency_ms)
                by_channel["tts_synth"]["synth_ms"].append(synth["elapsed_ms"])
                by_channel["tts_synth"]["count"] += 1
            else:
                # synth 매칭 실패 — cached로 가정 (보수적)
                by_channel["tts_cached"]["latencies_ms"].append(latency_ms)
                by_channel["tts_cached"]["count"] += 1

    # 5. 결과 정리
    result: dict = {"by_channel": {}}
    for ch, data in by_channel.items():
        result["by_channel"][ch] = {
            "count": data["count"],
            "enqueue_to_broadcast_ms": summarize(data["latencies_ms"]),
        }
        if "synth_ms" in data:
            result["by_channel"][ch]["synth_ms"] = summarize(data["synth_ms"])
    return result


def run(session_dir: Path) -> dict:
    """BenchmarkSession.finalize에서 호출. JSON 저장 + 결과 반환."""
    log_path = session_dir / "raw" / "app.log"
    if not log_path.exists():
        return {"error": "no log"}
    result = analyze(log_path)
    out_path = session_dir / "channel_latency.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result
