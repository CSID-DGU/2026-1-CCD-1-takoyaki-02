"""음성 채널별 응답 시간 분석 (지표 A).

채널 정의:
- **sfx**: SFX 효과음. audio_broadcast args[0] == 'sfx_play'
- **tts_cached**: 캐시 hit으로 즉시 broadcast된 TTS
- **tts_synth**: 캐시 miss로 합성 후 broadcast된 TTS
- **llm**: LLM 멘트 (현재 없음, 후속)

각 channel의 측정 구간:
- **queue_wait_ms**: backend 큐 입장 → dequeue. 이전 발화가 끝나길 기다린 시간.
- **backend_prepare_ms**: dequeue → backend broadcast. 캐시 조회/합성/송신 준비 시간.
- **frontend_receive_to_play_start_ms**: frontend가 해당 playback_id 메시지를 받은 뒤
  Audio.play()를 호출하기까지의 시간. 발화 하나 단위의 시작 지연이며 큐 대기를
  포함하지 않는다.
- **playback_duration_ms**: 해당 playback_id의 실제 재생 시간.
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

    # 2. dequeue/broadcast로 backend 내부 대기/준비 시간 분해.
    dequeue: dict[str, float] = {}
    for e in events:
        if e["event"] == "audio_dequeue" and len(e["args"]) >= 3:
            _, pbid, ts = e["args"][0], e["args"][1], e["args"][2]
            try:
                dequeue[pbid] = float(ts)
            except ValueError:
                pass

    # 3. audio_broadcast로 backend 송신 ts + 직전 tts_synth_done 매칭.
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

    # 4. frontend playback_id별 수신/시작/종료 매칭. 모두 performance.now() 기준.
    received: dict[str, float] = {}
    play_start: dict[str, dict] = {}
    play_end: dict[str, dict] = {}
    for e in events:
        if e["event"] == "audio_msg_received" and len(e["args"]) >= 3:
            _, pbid, perf_ms = e["args"][0], e["args"][1], e["args"][2]
            try:
                received[pbid] = float(perf_ms)
            except ValueError:
                pass
        elif e["event"] == "audio_play_start" and len(e["args"]) >= 4:
            msg_type, pbid, perf_ms = e["args"][0], e["args"][1], e["args"][2]
            try:
                receive_to_start_ms = (
                    float(e["args"][3])
                    if len(e["args"]) >= 4
                    else float(perf_ms) - received[pbid]
                )
                play_start[pbid] = {
                    "msg_type": msg_type,
                    "perf_ms": float(perf_ms),
                    "receive_to_start_ms": receive_to_start_ms,
                }
            except (KeyError, ValueError):
                pass
        elif e["event"] == "audio_play_end" and len(e["args"]) >= 5:
            msg_type, pbid, status, perf_ms, duration_ms = (
                e["args"][0],
                e["args"][1],
                e["args"][2],
                e["args"][3],
                e["args"][4],
            )
            try:
                play_end[pbid] = {
                    "msg_type": msg_type,
                    "status": status,
                    "perf_ms": float(perf_ms),
                    "duration_ms": float(duration_ms),
                }
            except ValueError:
                pass

    # 5. 채널별 분류 + latency 집계.
    by_channel: dict[str, dict] = {
        "sfx": {
            "count": 0,
            "queue_wait_ms": [],
            "backend_prepare_ms": [],
            "frontend_receive_to_play_start_ms": [],
            "playback_duration_ms": [],
        },
        "tts_cached": {
            "count": 0,
            "queue_wait_ms": [],
            "backend_prepare_ms": [],
            "frontend_receive_to_play_start_ms": [],
            "playback_duration_ms": [],
            "synth_ms": [],
        },
        "tts_synth": {
            "count": 0,
            "queue_wait_ms": [],
            "backend_prepare_ms": [],
            "frontend_receive_to_play_start_ms": [],
            "playback_duration_ms": [],
            "synth_ms": [],
        },
    }
    per_playback: list[dict] = []

    for pbid, info in enqueue.items():
        msg_type = info["msg_type"]
        enq_ts = info["enqueue_ts"]
        deq_ts = dequeue.get(pbid)
        bcast_ts = broadcast.get(pbid)

        if msg_type == "sfx_play":
            channel = "sfx"
        elif msg_type == "tts_play":
            synth = broadcast_synth.get(pbid)
            if synth and synth["hit"]:
                channel = "tts_cached"
            elif synth:
                channel = "tts_synth"
            else:
                channel = "tts_cached"
                synth = None
        else:
            continue

        data = by_channel[channel]
        data["count"] += 1
        sample = {"playback_id": pbid, "channel": channel, "msg_type": msg_type}

        if deq_ts is not None:
            queue_wait_ms = (deq_ts - enq_ts) * 1000
            data["queue_wait_ms"].append(queue_wait_ms)
            sample["queue_wait_ms"] = queue_wait_ms
        if deq_ts is not None and bcast_ts is not None:
            backend_prepare_ms = (bcast_ts - deq_ts) * 1000
            data["backend_prepare_ms"].append(backend_prepare_ms)
            sample["backend_prepare_ms"] = backend_prepare_ms
        start = play_start.get(pbid)
        if start is not None:
            data["frontend_receive_to_play_start_ms"].append(start["receive_to_start_ms"])
            sample["frontend_receive_to_play_start_ms"] = start["receive_to_start_ms"]
        end = play_end.get(pbid)
        if end is not None:
            data["playback_duration_ms"].append(end["duration_ms"])
            sample["playback_duration_ms"] = end["duration_ms"]
            sample["status"] = end["status"]
        if msg_type == "tts_play" and synth:
            data["synth_ms"].append(synth["elapsed_ms"])
            sample["cache_hit"] = synth["hit"]
            sample["cache_layer"] = synth["layer"]
            sample["synth_ms"] = synth["elapsed_ms"]

        per_playback.append(sample)

    # 6. 결과 정리
    result: dict = {
        "by_channel": {},
        "per_playback": per_playback,
        "note": (
            "queue_wait_ms는 누적 큐 대기 시간이고, "
            "frontend_receive_to_play_start_ms가 발화 하나마다의 시작 지연입니다."
        ),
    }
    for ch, data in by_channel.items():
        result["by_channel"][ch] = {
            "count": data["count"],
            "queue_wait_ms": summarize(data["queue_wait_ms"]),
            "backend_prepare_ms": summarize(data["backend_prepare_ms"]),
            "frontend_receive_to_play_start_ms": summarize(
                data["frontend_receive_to_play_start_ms"]
            ),
            "playback_duration_ms": summarize(data["playback_duration_ms"]),
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
