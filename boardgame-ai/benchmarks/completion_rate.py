"""게임 진행 성공률 (지표 K).

hook:
  game_start <type> <ts>       — 게임 시작
  game_end <type> normal <ts>  — 정상 종료 (요트 finish_game / 늑대 RESULT 진입)

start 다음 end가 오기 전에 또 다른 start나 disconnect 미복구로 끊기면 비정상.
v1: start-end 페어 단순 카운트 (시간순), 정상 종료된 비율 보고.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.trace_collector import collect_to_list


def analyze(log_path: Path) -> dict:
    events = collect_to_list(log_path)

    by_type: dict[str, dict] = {}
    pending_start: dict[str, float] = {}  # type → start_ts

    for e in events:
        if e["event"] == "game_start" and len(e["args"]) >= 2:
            game_type = e["args"][0]
            try:
                ts = float(e["args"][1])
            except ValueError:
                continue
            by_type.setdefault(game_type, {"started": 0, "completed": 0, "abandoned": 0})
            # 이미 pending start가 있으면 = 도중에 새 게임 시작 = 이전은 abandoned
            if game_type in pending_start:
                by_type[game_type]["abandoned"] += 1
            pending_start[game_type] = ts
            by_type[game_type]["started"] += 1
        elif e["event"] == "game_end" and len(e["args"]) >= 2:
            game_type = e["args"][0]
            # status = e["args"][1]  # "normal" 외 케이스는 현재 없음
            by_type.setdefault(game_type, {"started": 0, "completed": 0, "abandoned": 0})
            if game_type in pending_start:
                by_type[game_type]["completed"] += 1
                del pending_start[game_type]

    # 분석 끝났는데 남은 pending = 비정상 종료
    for game_type in pending_start:
        by_type.setdefault(game_type, {"started": 0, "completed": 0, "abandoned": 0})
        by_type[game_type]["abandoned"] += 1

    overall = {"started": 0, "completed": 0, "abandoned": 0}
    for stats in by_type.values():
        for k in overall:
            overall[k] += stats[k]
    overall_rate = overall["completed"] / overall["started"] if overall["started"] else 0.0

    return {
        "by_type": {
            gt: {**s, "completion_rate": round(s["completed"] / s["started"], 4) if s["started"] else 0.0}
            for gt, s in by_type.items()
        },
        "overall": {**overall, "completion_rate": round(overall_rate, 4)},
    }


def run(session_dir: Path) -> dict:
    log_path = session_dir / "raw" / "app.log"
    if not log_path.exists():
        return {"error": "no log"}
    result = analyze(log_path)
    (session_dir / "completion_rate.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    return result
