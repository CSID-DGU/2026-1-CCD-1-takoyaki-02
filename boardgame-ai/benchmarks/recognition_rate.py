"""웨어울프 비전 인식 정확도 (지표 W).

웨어울프의 핵심 비전 태스크 — 역할 카드 인식과 투표 지목 인식 — 의 정확도를
사용자의 수동 개입 신호로 측정한다.

hook:
  role_recognition reg match=0/1    — 역할 등록 시 (match=1: 감지값 그대로 확정)
  role_recognition reveal match=0/1 — 최종 공개 시 (match=1: 비전이 카드 감지)
  vote_cast -                       — 비전이 인식한 투표 (분모)
  vote_correction -                 — 사용자가 투표 오인식을 수동 정정 (인식 실패 proxy)

역할: 백엔드가 감지값 vs 확정값을 직접 비교 → 진짜 인식 정확도.
투표: 비전 인식 투표 수 대비 수동 정정 비율 → 정확도 추정 (상한 해석).
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.trace_collector import collect_to_list


def _role_stats(items: list[dict]) -> dict:
    total = len(items)
    matched = sum(1 for e in items if e["kv"].get("match") == "1")
    return {
        "total": total,
        "matched": matched,
        "accuracy": round(matched / total, 4) if total else None,
    }


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)

    reg = [
        e for e in events
        if e["event"] == "role_recognition" and e["args"][:1] == ["reg"]
    ]
    reveal = [
        e for e in events
        if e["event"] == "role_recognition" and e["args"][:1] == ["reveal"]
    ]

    role_registration = _role_stats(reg)
    role_reveal = _role_stats(reveal)
    role_overall = _role_stats(reg + reveal)

    casts = sum(1 for e in events if e["event"] == "vote_cast")
    corrections = sum(1 for e in events if e["event"] == "vote_correction")
    vote = {
        "vision_casts": casts,
        "manual_corrections": corrections,
        "correction_rate": round(corrections / casts, 4) if casts else 0.0,
        "estimated_accuracy": round(1 - corrections / casts, 4) if casts else None,
        "note": (
            "수동 정정 = 투표 오인식 proxy. 비전 인식 투표 수 대비 정정 비율. "
            "전략적 변심으로 누른 경우 포함되므로 상한값으로 해석."
        ),
    }

    return {
        "role_registration": role_registration,
        "role_reveal": role_reveal,
        "role_overall": role_overall,
        "vote": vote,
    }


def run(session_dir: Path) -> dict:
    log_path = session_dir / "raw" / "app.log"
    if not log_path.exists():
        return {"error": "no log"}
    result = analyze(log_path)
    (session_dir / "recognition_rate.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    return result
