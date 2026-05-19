"""raw/app.log의 bench_log 라인들을 구조화된 JSONL로 변환.

입력 형식 (한 줄):
    2026-05-17T20:27:31.117 <event_name> <arg1> <arg2> ...

예:
    2026-05-17T20:27:31.117 event_emit ROLL_CONFIRMED p1 100 1779017251.117711
    2026-05-17T20:27:31.117 audio_enqueue tts_play pb_test123 1779017251.117945
    2026-05-17T20:27:31.117 tts_synth_done abc123 hit=1 layer=static elapsed_ms=0.0

출력 (JSONL, 한 줄당 한 이벤트):
    {"log_ts": "2026-05-17T20:27:31.117", "event": "event_emit",
     "args": ["ROLL_CONFIRMED", "p1", "100", "1779017251.117711"],
     "kv": {}}

kv는 "key=value" 형식 args를 dict로 분리 (예: tts_synth_done의 hit/layer/elapsed_ms).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\s+(\w+)\s*(.*)$")
_KV_RE = re.compile(r"^(\w+)=(.+)$")


def parse_line(line: str) -> dict | None:
    """한 라인 → dict (또는 매칭 실패 시 None)."""
    line = line.rstrip()
    m = _LINE_RE.match(line)
    if not m:
        return None
    log_ts, event, rest = m.group(1), m.group(2), m.group(3)
    tokens = rest.split() if rest else []
    args: list[str] = []
    kv: dict[str, str] = {}
    for tok in tokens:
        kv_m = _KV_RE.match(tok)
        if kv_m:
            kv[kv_m.group(1)] = kv_m.group(2)
        else:
            args.append(tok)
    return {"log_ts": log_ts, "event": event, "args": args, "kv": kv}


def collect(log_path: Path, out_path: Path) -> int:
    """log_path → out_path (JSONL). 반환: 작성된 이벤트 수."""
    count = 0
    with open(log_path, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
        for raw in f:
            parsed = parse_line(raw)
            if parsed is None:
                continue
            out.write(json.dumps(parsed, ensure_ascii=False) + "\n")
            count += 1
    return count


def collect_to_list(log_path: Path) -> list[dict]:
    """log_path 파싱해 리스트로 반환 (in-process 분석용)."""
    events: list[dict] = []
    with open(log_path, encoding="utf-8") as f:
        for raw in f:
            parsed = parse_line(raw)
            if parsed:
                events.append(parsed)
    return events
