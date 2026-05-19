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

    # 2. tts_synth_done은 cache key 기준이라 직접 playback_id 매칭 어려움.
    # 시간순으로 가장 가까운 audio_enqueue tts_play에 attach.
    synth_events: list[dict] = []
    for e in events:
        if e["event"] == "tts_synth_done":
            kv = e["kv"]
            try:
                synth_events.append({
                    "log_ts": e["log_ts"],
                    "hit": kv.get("hit", "0") == "1",
                    "layer": kv.get("layer", "?"),
                    "elapsed_ms": float(kv.get("elapsed_ms", 0)),
                })
            except ValueError:
                pass

    # 3. audio_play_start로 frontend 첫 음 ts.
    # Frontend는 performance.now() ms 단위라 backend time.time() s와 직접 비교 불가.
    # 차선책: audio_broadcast→audio_play_start 간 elapsed를 frontend timeline에서 계산.
    # 일단 enqueue→broadcast (백엔드 내부 latency)만 v1으로 측정.
    broadcast: dict[str, float] = {}
    for e in events:
        if e["event"] == "audio_broadcast" and len(e["args"]) >= 3:
            # msg_type pbid ts
            pbid, ts = e["args"][1], e["args"][2]
            try:
                broadcast[pbid] = float(ts)
            except ValueError:
                pass

    # 4. 채널별 분류 + latency 집계
    by_channel: dict[str, dict] = {
        "sfx": {"latencies_ms": [], "count": 0},
        "tts_cached": {"latencies_ms": [], "count": 0, "synth_ms": []},
        "tts_synth": {"latencies_ms": [], "count": 0, "synth_ms": []},
    }

    # 시간순 합성 이벤트 stream — 매 tts_play enqueue에 가장 가까운 직후 synth를 매칭
    synth_iter = iter(synth_events)
    pending_synth: dict | None = None
    def next_synth():
        nonlocal pending_synth
        if pending_synth:
            s = pending_synth
            pending_synth = None
            return s
        try:
            return next(synth_iter)
        except StopIteration:
            return None

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
            synth = next_synth()
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
