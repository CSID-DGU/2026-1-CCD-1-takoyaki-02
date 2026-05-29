"""실전 라운드 정확도 — 인식 실패 비율 (지표 B).

hook:
  roll_confirmed -         (요트 굴림 실제로 카운트된 경우)
  undo_round -             (사용자가 되돌리기 누른 경우)
  manual_dice_correction - (사용자가 눈 수를 직접 정정한 경우)

인식 실패 = 되돌리기 + 눈수정. 정확도 추정 = 1 - 인식실패 / roll_confirmed.
- manual_dice_correction: 사용자가 틀린 눈을 직접 고친 것 → 순수 인식 실패 신호.
- undo_round: 전략적 사유로 누른 경우도 포함 → 상한 해석.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.trace_collector import collect_to_list


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)
    rolls = sum(1 for e in events if e["event"] == "roll_confirmed")
    undos = sum(1 for e in events if e["event"] == "undo_round")
    corrections = sum(1 for e in events if e["event"] == "manual_dice_correction")
    failures = undos + corrections

    if rolls == 0:
        return {
            "rolls": 0,
            "undos": undos,
            "manual_corrections": corrections,
            "recognition_failures": failures,
            "undo_rate": 0.0,
            "failure_rate": 0.0,
            "estimated_accuracy": None,
        }

    failure_rate = failures / rolls
    return {
        "rolls": rolls,
        "undos": undos,
        "manual_corrections": corrections,
        "recognition_failures": failures,
        "undo_rate": round(undos / rolls, 4),
        "failure_rate": round(failure_rate, 4),
        "estimated_accuracy": round(1 - failure_rate, 4),
        "note": (
            "인식 실패 = 되돌리기 + 눈수정. 눈수정은 순수 인식 정정, "
            "되돌리기는 전략적 사유 포함이라 상한값으로 해석."
        ),
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
