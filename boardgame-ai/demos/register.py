"""플레이어 좌석 등록 도구 (데모 #2/#3/#5 의 선행 단계).

각 플레이어가 오른손 + 왼손을 카메라에 보이게 한 뒤 SPACE 를 누르면
그 시점의 양손 landmark 로 SeatZone(팔 방향·손목·몸 위치)을 만들어 저장한다.
실제 시스템의 좌석 등록(오른손 V사인 → 왼손 OK사인)과 동일한 SeatZone 구조를
만들지만, 데모 녹화 안정성을 위해 키 입력으로 캡처한다.

제스처는 보지 않는다(V/OK 안 해도 됨) — 손목 위치 + 팔 방향만 저장하므로
각자 자기 자리 방향으로 양손을 자연스럽게 뻗기만 하면 된다.

기본은 **새로 시작**(기존 등록 무시). 이전 등록에 이어붙이려면 --keep.

조작:
  SPACE : 현재 보이는 양손으로 한 명 등록 (오른손 1 + 왼손 1 필요)
  u     : 마지막 등록 취소
  s     : 저장 (demos/players.json)
  q/ESC : 저장 후 종료

실행 (boardgame-ai 디렉터리에서):
  python -m demos.register --mirror          # 새로 등록
  python -m demos.register --mirror --keep   # 기존에 이어서 추가
"""

from __future__ import annotations

import math
import time

import cv2

from core.models import Player
from demos import common
from vision.detectors.hand_detector import HandDetector


def _pick_hands(hands):
    """감지된 손에서 오른손 1 + 왼손 1 선택. 없으면 None."""
    right = next((h for h in hands if h.handedness == "Right"), None)
    left = next((h for h in hands if h.handedness == "Left"), None)
    return right, left


def main() -> None:
    parser = common.base_arg_parser("플레이어 좌석 등록")
    parser.add_argument("--keep", action="store_true",
                        help="기존 등록을 불러와 이어서 추가 (기본은 새로 시작)")
    args = parser.parse_args()

    text = common.TextRenderer()
    detector = HandDetector(max_num_hands=8)
    cap = cv2.VideoCapture(common.resolve_source(args.source))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(f"[register] 카메라 열기 실패: {args.source}")
        return

    if args.keep:
        players: list[Player] = common.load_players(args.players)
        if players:
            print(f"[register] 기존 등록 {len(players)}명 불러옴 (이어서 추가)")
    else:
        players = []
        print("[register] 새로 시작 (기존 등록은 저장 시 덮어씀)")

    win = "Player Registration"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    flash_until = 0.0
    flash_msg = ""

    print("[register] SPACE=등록  u=취소  s=저장  q=종료")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if args.mirror:
                frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands = detector.detect(frame_rgb)
            right, left = _pick_hands(hands)

            # 현재 손 그리기
            for hd in hands:
                col = common.GREEN if hd.handedness == "Right" else (40, 160, 255)
                common.draw_hand(frame, hd.landmarks_21, col)
                text.text(frame, common.to_px(hd.wrist_xy, w, h), hd.handedness,
                          color=col, size=22)

            # 이미 등록된 플레이어 좌석 앵커 표시
            for i, p in enumerate(players):
                col = common.player_color(i)
                sz = p.seat_zone
                for arm in (sz.right_arm, sz.left_arm):
                    cx, cy = common.to_px(arm.wrist_xy, w, h)
                    cv2.circle(frame, (cx, cy), 9, col, 2)
                    ex = int(cx + 0.08 * w * math.cos(arm.arm_angle))
                    ey = int(cy + 0.08 * h * math.sin(arm.arm_angle))
                    cv2.arrowedLine(frame, (cx, cy), (ex, ey), col, 2, tipLength=0.3)
                bx, by = common.clamp_px(sz.body_xy, w, h)
                cv2.drawMarker(frame, (bx, by), col, cv2.MARKER_CROSS, 22, 3)
                text.text(frame, (bx + 8, by - 10), p.playername or p.player_id,
                          color=col, size=22)

            # 상단 안내 패널
            cv2.rectangle(frame, (0, 0), (w, 80), (0, 0, 0), -1)
            ready = right is not None and left is not None
            status_col = common.GREEN if ready else common.RED
            status = "양손 인식됨 — SPACE 로 등록" if ready else "오른손+왼손을 모두 보여주세요"
            text.text(frame, (12, 8), f"등록된 플레이어: {len(players)}명", color=common.WHITE, size=26)
            text.text(frame, (12, 44), status, color=status_col, size=24)

            if time.time() < flash_until:
                text.text(frame, (w // 2 - 140, h // 2 - 20), flash_msg,
                          color=common.GREEN, size=44, bg=common.BLACK)

            cv2.imshow(win, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord(" "):
                if ready:
                    pid = f"p_{len(players) + 1}"
                    seat = common.build_seat_zone(
                        right.wrist_xy, right.landmarks_21,
                        left.wrist_xy, left.landmarks_21,
                    )
                    players.append(Player(
                        player_id=pid,
                        playername=f"Player {len(players) + 1}",
                        seat_zone=seat,
                        registered_at=time.time(),
                    ))
                    flash_msg = f"{pid} 등록!"
                    flash_until = time.time() + 1.0
                    print(f"[register] {pid} 등록  body={seat.body_xy}  posture={seat.posture}")
                else:
                    print("[register] 양손이 모두 보이지 않아 등록 실패")
            elif key == ord("u"):
                if players:
                    removed = players.pop()
                    print(f"[register] {removed.player_id} 취소")
            elif key == ord("s"):
                common.save_players(players, args.players)
                flash_msg = "저장됨"
                flash_until = time.time() + 1.0
                print(f"[register] 저장 완료 → {args.players} ({len(players)}명)")
            elif key in (ord("q"), 27):
                break
    finally:
        if players:
            common.save_players(players, args.players)
            print(f"[register] 종료 — {len(players)}명 저장 → {args.players}")
        cap.release()
        cv2.destroyAllWindows()
        detector.close()


if __name__ == "__main__":
    main()
