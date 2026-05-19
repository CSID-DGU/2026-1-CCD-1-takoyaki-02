"""실전 라운드 정확도 — 되돌리기 비율 (지표 B).

hook:
  roll_confirmed - (요트 굴림 실제로 카운트된 경우)
  undo_round -    (사용자가 되돌리기 누른 경우)

정확도 추정 = 1 - undo / roll_confirmed.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.trace_collector import collect_to_list


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)
    rolls = sum(1 for e in events if e["event"] == "roll_confirmed")
    undos = sum(1 for e in events if e["event"] == "undo_round")

    if rolls == 0:
        return {"rolls": 0, "undos": undos, "undo_rate": 0.0, "estimated_accuracy": None}

    undo_rate = undos / rolls
    return {
        "rolls": rolls,
        "undos": undos,
        "undo_rate": round(undo_rate, 4),
        "estimated_accuracy": round(1 - undo_rate, 4),
        "note": "되돌리기 = 인식 실패의 proxy. 전략적 사유로 누른 경우 포함되므로 상한값으로 해석.",
    }


def run(session_dir: Path) -> dict:
    log_path = session_dir / "raw" / "app.log"
    if not log_path.exists():
        return {"error": "no log"}
    result = analyze(log_path)
    (session_dir / "undo_rate.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    return result
