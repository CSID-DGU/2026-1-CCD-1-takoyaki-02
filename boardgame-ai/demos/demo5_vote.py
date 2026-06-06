"""데모 5 — 손가락 지목(투표) 시각화.

손목(landmark 0) → 검지끝(landmark 8) 방향 벡터를 연장해, 그 ray 가 가장 잘
향하는 좌석(플레이어 몸 위치)을 지목 대상으로 판정한다. 지목 선을 긋고 대상
플레이어를 강조하며 누적 득표 수를 표시한다. (werewolf_rules VOTE_POINT 와 동일 로직)

선행: `python -m demos.register` 로 2명 이상 등록.

실행 (boardgame-ai 디렉터리에서):
  python -m demos.demo5_vote
  python -m demos.demo5_vote --mirror --record /tmp/demo5.mp4
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict

import cv2
import numpy as np

from demos import common

_MIN_POINT_LENGTH = 0.03   # 검지 펴짐 최소 길이
_RAY_MAX_T = 1.5           # ray 최대 거리(정규화)
_SEAT_PERP_DIST = 0.18     # ray-좌석 허용 수직거리


def main() -> None:
    parser = common.base_arg_parser("손가락 지목/투표 시각화")
    args = parser.parse_args()

    players = common.load_players(args.players)
    if len(players) < 2:
        print("[demo5] 2명 이상 등록 필요. 먼저: python -m demos.register")
        sys.exit(1)

    color_by_pid = {p.player_id: common.player_color(i) for i, p in enumerate(players)}
    name_by_pid = {p.player_id: (p.playername or p.player_id) for p in players}
    body_by_pid = {p.player_id: p.seat_zone.body_xy for p in players}

    proc = common.HandProcessor(players=players)
    text_r = common.TextRenderer()
    demo = common.Demo("Demo5 - Vote Pointing", args)

    vote_tally: dict[str, int] = defaultdict(int)
    last_vote: dict[str, str] = {}  # voter -> target (중복 카운트 방지)

    def find_target(wrist, nx, ny, voter_id):
        best, best_perp = None, _SEAT_PERP_DIST
        for pid, (sx, sy) in body_by_pid.items():
            if pid == voter_id:
                continue
            t = (sx - wrist[0]) * nx + (sy - wrist[1]) * ny
            if t <= 0 or t > _RAY_MAX_T:
                continue
            px, py = wrist[0] + t * nx, wrist[1] + t * ny
            perp = math.hypot(sx - px, sy - py)
            if perp < best_perp:
                best_perp, best = perp, pid
        return best

    def process(frame: np.ndarray, frame_id: int, ts: float) -> np.ndarray:
        h, w = frame.shape[:2]
        hands = proc.process(frame)

        # 좌석 마커
        targeted_now: set[str] = set()
        for p in players:
            col = color_by_pid[p.player_id]
            bx, by = common.clamp_px(p.seat_zone.body_xy, w, h)
            cv2.drawMarker(frame, (bx, by), col, cv2.MARKER_CROSS, 24, 2)

        for hd in hands:
            lms = hd.landmarks_21
            if len(lms) < 9:
                continue
            wrist, tip = lms[0], lms[8]
            dx, dy = tip[0] - wrist[0], tip[1] - wrist[1]
            length = math.hypot(dx, dy)
            voter_id = hd.player_id
            vcol = color_by_pid.get(voter_id, common.GRAY)
            common.draw_hand(frame, lms, vcol)
            if length < _MIN_POINT_LENGTH:
                continue
            nx, ny = dx / length, dy / length

            target = find_target(wrist, nx, ny, voter_id)
            wx, wy = common.to_px(wrist, w, h)
            if target is None:
                # 지목 대상 없음: 방향만 옅게 표시
                ex = int(wx + nx * 0.3 * w)
                ey = int(wy + ny * 0.3 * h)
                cv2.arrowedLine(frame, (wx, wy), (ex, ey), common.GRAY, 2, tipLength=0.2)
                continue

            tcol = color_by_pid[target]
            bx, by = common.clamp_px(body_by_pid[target], w, h)
            cv2.arrowedLine(frame, (wx, wy), (bx, by), tcol, 4, tipLength=0.15)
            cv2.circle(frame, (bx, by), 34, tcol, 4, cv2.LINE_AA)
            text_r.text(frame, (bx + 12, by - 16), f"← {name_by_pid[target]} 지목됨",
                        color=tcol, size=26, bg=common.BLACK)
            targeted_now.add(target)

            if voter_id and last_vote.get(voter_id) != target:
                last_vote[voter_id] = target
                vote_tally[target] += 1

        # 헤더 + 득표 현황
        cv2.rectangle(frame, (0, 0), (w, 44), (0, 0, 0), -1)
        text_r.text(frame, (12, 6), "손가락 지목 → 투표 대상 판정", color=common.WHITE, size=26)
        y = 56
        for p in players:
            cnt = vote_tally.get(p.player_id, 0)
            col = color_by_pid[p.player_id]
            mark = "  ◀ 지목중" if p.player_id in targeted_now else ""
            text_r.text(frame, (12, y), f"{name_by_pid[p.player_id]}: {cnt}표{mark}",
                        color=col, size=24, bg=common.BLACK)
            y += 34
        return frame

    try:
        demo.run(process)
    finally:
        proc.close()


if __name__ == "__main__":
    main()
