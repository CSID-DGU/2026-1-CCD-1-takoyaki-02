"""데모 2 — 플레이어 매칭 시각화.

MediaPipe 손 결과(손목·팔 방향)를 등록된 좌석과 비교해, 각 손이 어느
플레이어인지 결정하고 그 좌석까지 선을 그어 매칭을 보여준다.

선행: `python -m demos.register` 로 플레이어 등록 필요.

실행 (boardgame-ai 디렉터리에서):
  python -m demos.demo2_matching
  python -m demos.demo2_matching --mirror --record /tmp/demo2.mp4
"""

from __future__ import annotations

import sys

import cv2
import numpy as np

from demos import common


def main() -> None:
    parser = common.base_arg_parser("플레이어 매칭 시각화")
    args = parser.parse_args()

    players = common.load_players(args.players)
    if len(players) < 1:
        print(f"[demo2] 등록된 플레이어가 없습니다. 먼저 실행: python -m demos.register")
        sys.exit(1)
    print(f"[demo2] 플레이어 {len(players)}명 로드")

    color_by_pid = {p.player_id: common.player_color(i) for i, p in enumerate(players)}
    name_by_pid = {p.player_id: (p.playername or p.player_id) for p in players}
    body_by_pid = {p.player_id: p.seat_zone.body_xy for p in players}

    proc = common.HandProcessor(players=players)
    text_r = common.TextRenderer()
    demo = common.Demo("Demo2 - Player Matching", args)

    def process(frame: np.ndarray, frame_id: int, ts: float) -> np.ndarray:
        h, w = frame.shape[:2]
        hands = proc.process(frame)

        # 등록 좌석 앵커 (옅게)
        for p in players:
            col = color_by_pid[p.player_id]
            sz = p.seat_zone
            for arm in (sz.right_arm, sz.left_arm):
                cx, cy = common.to_px(arm.wrist_xy, w, h)
                cv2.circle(frame, (cx, cy), 8, col, 2)
            bx, by = common.clamp_px(sz.body_xy, w, h)
            cv2.drawMarker(frame, (bx, by), col, cv2.MARKER_CROSS, 26, 3)
            text_r.text(frame, (bx + 8, by - 12), name_by_pid[p.player_id], color=col, size=24)

        # 손 + 매칭 선
        for hd in hands:
            pid = hd.player_id
            col = color_by_pid.get(pid, common.GRAY)
            common.draw_hand(frame, hd.landmarks_21, col)
            wx, wy = common.to_px(hd.wrist_xy, w, h)

            if pid in body_by_pid:
                bx, by = common.clamp_px(body_by_pid[pid], w, h)
                cv2.line(frame, (wx, wy), (bx, by), col, 3, cv2.LINE_AA)
                label = f"{name_by_pid[pid]} [{hd.handedness[0]}]"
            else:
                label = f"? [{hd.handedness[0]}]"
            text_r.text(frame, (wx + 10, wy + 6), label, color=col, size=24, bg=common.BLACK)

        # 헤더
        cv2.rectangle(frame, (0, 0), (w, 46), (0, 0, 0), -1)
        text_r.text(frame, (12, 6), "플레이어 매칭: 손 → 가장 가까운 좌석",
                    color=common.WHITE, size=28)
        return frame

    try:
        demo.run(process)
    finally:
        proc.close()


if __name__ == "__main__":
    main()
