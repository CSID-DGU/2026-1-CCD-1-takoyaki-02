"""데모 4 — 한밤의 늑대인간 역할 카드 인식.

WerewolfCardDetector(YOLO) + CardTracker 로 카드를 추적한다. 앞면이면 역할명,
뒷면이면 Card_Back 으로 표시하고 track_id·안정 프레임을 함께 보여준다. 카드가
일정 프레임 이상 안정적으로 앞면 인식되면 "인식 완료"로 강조한다.

플레이어 등록(선택): 등록돼 있으면 카드가 어느 플레이어 것인지 함께 표시.

실행 (boardgame-ai 디렉터리에서):
  python -m demos.demo4_rolecard
  python -m demos.demo4_rolecard --weights weights/werewolf_v8.pt --record /tmp/demo4.mp4
"""

from __future__ import annotations

import sys

import cv2
import numpy as np

from demos import common
from vision.detectors.card_detector import WerewolfCardDetector
from vision.tracking.card_tracker import CardTracker
from vision.werewolf.schemas import BACK_CLASS

_CONFIRM_FRAMES = 8  # 이 이상 안정 앞면이면 "인식 완료"


def main() -> None:
    parser = common.base_arg_parser("늑대인간 역할 카드 인식")
    parser.add_argument("--weights", default="weights/werewolf_v8.pt")
    parser.add_argument("--conf", type=float, default=0.4)
    args = parser.parse_args()

    detector = WerewolfCardDetector(model_path=args.weights, conf=args.conf)
    if not detector.is_loaded:
        print(f"[demo4] 카드 모델 로드 실패: {args.weights}")
        sys.exit(1)
    tracker = CardTracker()
    players = common.load_players(args.players)
    name_by_pid = {p.player_id: (p.playername or p.player_id) for p in players}

    text_r = common.TextRenderer()
    demo = common.Demo("Demo4 - Role Card", args)

    def process(frame: np.ndarray, frame_id: int, ts: float) -> np.ndarray:
        h, w = frame.shape[:2]
        dets = detector.detect(frame)
        cards = tracker.update(dets, players, frame_id)

        n_confirmed = 0
        for card in cards:
            face_up = card.face_up
            confirmed = face_up and card.stable_frames >= _CONFIRM_FRAMES
            if confirmed:
                n_confirmed += 1
            if face_up:
                col = common.GREEN if confirmed else (40, 200, 255)
                role = card.cls_name or "?"
            else:
                col = common.GRAY
                role = BACK_CLASS

            common.draw_bbox_norm(frame, card.bbox, col, thickness=3)
            x1, y1 = int(card.bbox.x1 * w), int(card.bbox.y1 * h)
            owner = name_by_pid.get(card.player_id, "")
            tag = f"#{card.track_id} {role}"
            if owner:
                tag += f" · {owner}"
            text_r.text(frame, (x1, max(y1 - 30, 2)), tag, color=col, size=24, bg=common.BLACK)
            if confirmed:
                text_r.text(frame, (x1, int(card.bbox.y2 * h) + 4), "✓ 인식 완료",
                            color=common.GREEN, size=22)

        cv2.rectangle(frame, (0, 0), (w, 44), (0, 0, 0), -1)
        text_r.text(frame, (12, 6),
                    f"역할 카드 인식  |  추적 {len(cards)}장  확정 {n_confirmed}장",
                    color=common.WHITE, size=26)
        return frame

    demo.run(process)


if __name__ == "__main__":
    main()
