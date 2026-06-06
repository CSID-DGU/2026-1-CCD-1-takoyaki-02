"""데모 1 — 객체 인식 + 손 인식 시각화 (3분할).

위 두 칸 / 아래 한 칸 레이아웃:
  [ YOLO 객체 추적 ] [ MediaPipe 손 ]
        [ 혼합 (YOLO + MediaPipe) ]

YOLO 객체는 ByteTrack track_id 와 이동 궤적(trail)으로 프레임 간 변화를 보여주고,
MediaPipe 는 21 관절 골격을 그린다. 아래 칸은 둘을 겹쳐 보여준다.

실행 (boardgame-ai 디렉터리에서):
  python -m demos.demo1_detection
  python -m demos.demo1_detection --weights weights/yacht_v4.pt --mirror
  python -m demos.demo1_detection --record /tmp/demo1.mp4
"""

from __future__ import annotations

from collections import defaultdict, deque

import cv2
import numpy as np

from demos import common
from vision.detectors.hand_detector import HandDetector
from vision.detectors.yolo_detector import YoloDetector
from vision.tracking.byte_tracker import ByteTracker

# 클래스별 색상 (BGR)
_CLS_COLOR = {
    "tray": (0, 255, 0),
    "tray_inner": (0, 200, 100),
    "roll_tray": (255, 165, 0),
    "dice": (0, 100, 255),
}
_PANEL_W, _PANEL_H = 960, 540


def _label_panel(text_r: common.TextRenderer, panel: np.ndarray, title: str,
                 color: tuple[int, int, int]) -> None:
    h, w = panel.shape[:2]
    cv2.rectangle(panel, (0, 0), (w, 34), (0, 0, 0), -1)
    cv2.rectangle(panel, (0, 0), (w, 34), color, 2)
    text_r.text(panel, (10, 4), title, color=color, size=24)


def main() -> None:
    parser = common.base_arg_parser("객체+손 인식 3분할 시각화")
    parser.add_argument("--weights", default="weights/yacht_v4.pt", help="YOLO 가중치")
    parser.add_argument("--conf", type=float, default=0.35)
    args = parser.parse_args()

    yolo = YoloDetector(weights_path=args.weights, conf=args.conf)
    tracker = ByteTracker(min_hits=1)
    detector = HandDetector(max_num_hands=8)
    text_r = common.TextRenderer()

    trails: dict[int, deque] = defaultdict(lambda: deque(maxlen=24))

    demo = common.Demo("Demo1 - Detection (3-split)", args)

    def process(frame: np.ndarray, frame_id: int, ts: float) -> np.ndarray:
        h, w = frame.shape[:2]

        # ── 감지 ──
        yolo_dets = yolo.detect(frame)
        dice_dets = [d for d in yolo_dets if d.cls_name == "dice"]
        other_dets = [d for d in yolo_dets if d.cls_name != "dice"]
        tracked = tracker.update(dice_dets, frame_id)

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hands = detector.detect(frame_rgb)

        # 궤적 업데이트
        live_ids = set()
        for tid, det in tracked:
            cx, cy = int(det.bbox.cx * w), int(det.bbox.cy * h)
            trails[tid].append((cx, cy))
            live_ids.add(tid)
        for tid in [t for t in trails if t not in live_ids]:
            del trails[tid]

        # ── 패널 A: YOLO 객체 추적 ──
        panel_a = frame.copy()
        for det in other_dets:
            col = _CLS_COLOR.get(det.cls_name, (200, 200, 200))
            common.draw_bbox_norm(panel_a, det.bbox, col, det.cls_name)
        for tid, det in tracked:
            col = _CLS_COLOR["dice"]
            common.draw_bbox_norm(panel_a, det.bbox, col, f"dice#{tid}")
            pts = list(trails[tid])
            for i in range(1, len(pts)):
                cv2.line(panel_a, pts[i - 1], pts[i], (0, 200, 255), 2, cv2.LINE_AA)

        # ── 패널 B: MediaPipe 손 ──
        panel_b = frame.copy()
        for hd in hands:
            col = common.GREEN if hd.handedness == "Right" else (40, 160, 255)
            common.draw_hand(panel_b, hd.landmarks_21, col)

        # ── 패널 C: 혼합 ──
        panel_c = frame.copy()
        for det in other_dets:
            col = _CLS_COLOR.get(det.cls_name, (200, 200, 200))
            common.draw_bbox_norm(panel_c, det.bbox, col, det.cls_name)
        for tid, det in tracked:
            common.draw_bbox_norm(panel_c, det.bbox, _CLS_COLOR["dice"], f"dice#{tid}")
        for hd in hands:
            col = common.GREEN if hd.handedness == "Right" else (40, 160, 255)
            common.draw_hand(panel_c, hd.landmarks_21, col)

        # ── 패널 합성 ──
        a = cv2.resize(panel_a, (_PANEL_W, _PANEL_H))
        b = cv2.resize(panel_b, (_PANEL_W, _PANEL_H))
        c = cv2.resize(panel_c, (_PANEL_W, _PANEL_H))
        _label_panel(text_r, a, "YOLO 객체 추적", _CLS_COLOR["dice"])
        _label_panel(text_r, b, "MediaPipe 손 관절", common.GREEN)
        _label_panel(text_r, c, "혼합 (YOLO + MediaPipe)", (255, 255, 0))

        canvas = np.zeros((_PANEL_H * 2, _PANEL_W * 2, 3), dtype=np.uint8)
        canvas[0:_PANEL_H, 0:_PANEL_W] = a
        canvas[0:_PANEL_H, _PANEL_W:_PANEL_W * 2] = b
        x0 = _PANEL_W // 2
        canvas[_PANEL_H:_PANEL_H * 2, x0:x0 + _PANEL_W] = c
        return canvas

    try:
        demo.run(process)
    finally:
        detector.close()


if __name__ == "__main__":
    main()
