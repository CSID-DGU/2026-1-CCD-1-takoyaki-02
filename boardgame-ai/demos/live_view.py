"""라이브 카메라 출력 창 — 시연 플레이 화면녹화용.

테이블을 비추는 카메라 영상을 큰 창으로 띄운다. 태블릿(UI)은 따로 녹화하고,
이 창은 컴퓨터에서 화면녹화하면 "카메라가 보는 장면"을 동시에 담을 수 있다.

  --overlay none     : 깨끗한 카메라 패스스루 (기본)
  --overlay hands    : 손 21관절 (+ 등록돼 있으면 플레이어 이름)
  --overlay objects  : 요트 YOLO 객체(tray/dice…) + 추적
  --overlay cards    : 늑대인간 역할 카드
  --overlay all      : 손 + 객체 + 카드 모두

⚠ macOS 카메라는 한 프로세스만 연다. 백엔드(비전 파이프라인)가 같은 카메라를
   쓰는 중이면 이 뷰어는 그 카메라를 못 연다. 같은 카메라라면 "백엔드 대신 이 뷰어를
   띄워 그게 곧 시연 화면"으로 쓰거나, 카메라를 2대 쓰면 동시 사용 가능.

실행 (boardgame-ai 디렉터리에서):
  python -m demos.live_view --mirror --fullscreen
  python -m demos.live_view --overlay all --mirror --record /tmp/play.mp4
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

import cv2
import numpy as np

from demos import common

_CLS_COLOR = {
    "tray": (0, 255, 0),
    "tray_inner": (0, 200, 100),
    "roll_tray": (255, 165, 0),
    "dice": (0, 100, 255),
}


def main() -> None:
    parser = common.base_arg_parser("라이브 카메라 출력 (시연 녹화용)")
    parser.add_argument("--overlay", default="none",
                        choices=["none", "hands", "objects", "cards", "all"],
                        help="표시할 인식 오버레이")
    parser.add_argument("--weights", default="weights/yacht_v4.pt", help="요트 YOLO 가중치")
    parser.add_argument("--card-weights", default="weights/werewolf_v8.pt", help="카드 YOLO 가중치")
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--fullscreen", action="store_true", help="전체화면")
    parser.add_argument("--fps-hud", action="store_true", help="FPS 표시(기본 숨김)")
    parser.add_argument("--clock", action="store_true", help="좌상단 경과시간 표시")
    parser.add_argument(
        "--http", nargs="?", const="http://127.0.0.1:8000/debug/vision/frame.jpg",
        default=None,
        help="카메라 대신 백엔드 프레임 엔드포인트를 폴링 (백엔드가 카메라를 쥐고 있을 때). "
             "값 없이 주면 기본 URL 사용.",
    )
    args = parser.parse_args()

    mode = args.overlay
    want_objects = mode in ("objects", "all")
    want_cards = mode in ("cards", "all")
    want_hands = mode in ("hands", "all")

    players = common.load_players(args.players)
    name_by_pid = {p.player_id: (p.playername or p.player_id) for p in players}
    color_by_pid = {p.player_id: common.player_color(i) for i, p in enumerate(players)}

    # 필요한 컴포넌트만 지연 로드
    yolo = bt = None
    if want_objects:
        from vision.detectors.yolo_detector import YoloDetector
        from vision.tracking.byte_tracker import ByteTracker
        yolo = YoloDetector(weights_path=args.weights, conf=args.conf)
        bt = ByteTracker(min_hits=1)
    card_det = card_trk = None
    if want_cards:
        from vision.detectors.card_detector import WerewolfCardDetector
        from vision.tracking.card_tracker import CardTracker
        card_det = WerewolfCardDetector(model_path=args.card_weights, conf=0.4)
        card_trk = CardTracker()
    hand_proc = None
    if want_hands:
        hand_proc = common.HandProcessor(players=players)

    trails: dict[int, deque] = defaultdict(lambda: deque(maxlen=24))
    text_r = common.TextRenderer()
    t0 = time.time()

    demo = common.Demo(
        "Live Camera View", args,
        show_fps=args.fps_hud, fullscreen=args.fullscreen,
    )

    def process(frame: np.ndarray, frame_id: int, ts: float) -> np.ndarray:
        h, w = frame.shape[:2]

        if want_objects:
            dets = yolo.detect(frame)
            dice = [d for d in dets if d.cls_name == "dice"]
            for d in [d for d in dets if d.cls_name != "dice"]:
                common.draw_bbox_norm(frame, d.bbox, _CLS_COLOR.get(d.cls_name, (200, 200, 200)), d.cls_name)
            tracked = bt.update(dice, frame_id)
            live = set()
            for tid, det in tracked:
                live.add(tid)
                cx, cy = int(det.bbox.cx * w), int(det.bbox.cy * h)
                trails[tid].append((cx, cy))
                common.draw_bbox_norm(frame, det.bbox, _CLS_COLOR["dice"], f"dice#{tid}")
                pts = list(trails[tid])
                for i in range(1, len(pts)):
                    cv2.line(frame, pts[i - 1], pts[i], (0, 200, 255), 2, cv2.LINE_AA)
            for tid in [t for t in trails if t not in live]:
                del trails[tid]

        if want_cards:
            from vision.werewolf.schemas import BACK_CLASS
            cards = card_trk.update(card_det.detect(frame), players, frame_id)
            for card in cards:
                if card.face_up:
                    col = common.GREEN
                    role = card.cls_name or "?"
                else:
                    col = common.GRAY
                    role = BACK_CLASS
                common.draw_bbox_norm(frame, card.bbox, col, thickness=3)
                x1, y1 = int(card.bbox.x1 * w), int(card.bbox.y1 * h)
                text_r.text(frame, (x1, max(y1 - 28, 2)), f"#{card.track_id} {role}",
                            color=col, size=22, bg=common.BLACK)

        if want_hands:
            for hd in hand_proc.process(frame):
                col = color_by_pid.get(hd.player_id, common.GREEN if hd.handedness == "Right" else (40, 160, 255))
                common.draw_hand(frame, hd.landmarks_21, col)
                if hd.player_id in name_by_pid:
                    wx, wy = common.to_px(hd.wrist_xy, w, h)
                    text_r.text(frame, (wx + 8, wy), name_by_pid[hd.player_id],
                                color=col, size=22, bg=common.BLACK)

        if args.clock:
            elapsed = int(time.time() - t0)
            text_r.text(frame, (12, 10), f"{elapsed // 60:02d}:{elapsed % 60:02d}",
                        color=common.WHITE, size=26, bg=common.BLACK)
        return frame

    print(f"[live_view] overlay={mode}  players={len(players)}명  'q'/ESC 종료")
    try:
        demo.run(process)
    finally:
        if hand_proc is not None:
            hand_proc.close()


if __name__ == "__main__":
    main()
