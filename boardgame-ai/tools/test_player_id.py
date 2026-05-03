"""등록된 플레이어 좌석 매칭 실시간 테스트 툴.

백엔드(http://localhost:8000)에서 등록된 플레이어 목록을 가져온 뒤,
카메라에서 손이 감지될 때마다 어느 플레이어 손인지 콘솔에 출력 + 화면 오버레이.

매칭은 트랙 첫 N프레임 정보(arm_angle + entry wrist + body 외삽)로 1회 결정.
이후 트랙이 유지되는 한 player_id 변경 없음.

실행:
    cd boardgame-ai
    python3 -m tools.test_player_id
    python3 -m tools.test_player_id --source 0 --backend http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request

import cv2

from core.models import Player, SeatZone
from vision.attribution.seat_matcher import (
    match_player_by_arm,
    players_with_both_hands_tracked,
)
from vision.config import VisionConfig
from vision.detectors.gesture_classifier import GestureClassifier
from vision.detectors.hand_detector import HandDetector
from vision.geometry.arm_vector import compute_arm_angle
from vision.tracking.hand_tracker import HandTracker

# 등록된 플레이어 색상(BGR) — 오버레이용
_COLORS = [
    (0, 255, 0),  # green
    (255, 128, 0),  # cyan-blue
    (0, 128, 255),  # orange
    (255, 0, 255),  # magenta
    (255, 255, 0),  # yellow
]


def fetch_players(backend_url: str) -> list[Player]:
    url = f"{backend_url}/players"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
        players = []
        for d in data:
            if d.get("seat_zone") is None:
                continue
            sz = SeatZone.from_dict(d["seat_zone"])
            players.append(
                Player(
                    player_id=d["player_id"],
                    playername=d.get("playername") or d["player_id"],
                    seat_zone=sz,
                )
            )
        return players
    except Exception as e:
        print(f"[test_player_id] 백엔드 연결 실패: {e}")
        return []


def _draw_arrow(frame, wrist_xy, angle, color, length_norm=0.1, thickness=2):
    h, w = frame.shape[:2]
    sx = int(wrist_xy[0] * w)
    sy = int(wrist_xy[1] * h)
    ex = int(sx + length_norm * w * math.cos(angle))
    ey = int(sy + length_norm * h * math.sin(angle))
    cv2.arrowedLine(frame, (sx, sy), (ex, ey), color, thickness, tipLength=0.3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=int, default=0)
    parser.add_argument("--backend", default="http://localhost:8000")
    args = parser.parse_args()

    players = fetch_players(args.backend)
    if not players:
        print("[test_player_id] 등록된 플레이어 없음. 먼저 좌석 등록을 완료하세요.")
        sys.exit(1)

    print(f"[test_player_id] 등록된 플레이어 {len(players)}명:")
    color_by_pid: dict[str, tuple[int, int, int]] = {}
    for i, p in enumerate(players):
        color_by_pid[p.player_id] = _COLORS[i % len(_COLORS)]
        sz = p.seat_zone
        print(
            f"  {p.playername} ({p.player_id})  "
            f"R wrist={sz.right_arm.wrist_xy} angle={math.degrees(sz.right_arm.arm_angle):.0f}°  "
            f"L wrist={sz.left_arm.wrist_xy} angle={math.degrees(sz.left_arm.arm_angle):.0f}°  "
            f"body={sz.body_xy} posture={sz.posture}"
        )
    print("\n손을 카메라에 보여주세요. q를 누르면 종료.\n")

    config = VisionConfig(source=args.source)
    hand_detector = HandDetector(
        max_num_hands=config.mp_max_num_hands,
        min_detection_confidence=config.mp_min_detection_confidence,
        min_tracking_confidence=config.mp_min_tracking_confidence,
    )
    gesture_clf = GestureClassifier()
    hand_tracker = HandTracker()

    cap = cv2.VideoCapture(args.source)
    prev_results: dict[int, str] = {}  # track_id → player_name

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            raw_hands = hand_detector.detect(frame_rgb)

            detections = [(h.wrist_xy, compute_arm_angle(h.landmarks_21)) for h in raw_hands]
            tracks = hand_tracker.update(detections)

            excluded = players_with_both_hands_tracked(hand_tracker.active_tracks())

            for raw, track in zip(raw_hands, tracks, strict=True):
                track.handedness_buf.append(raw.handedness)
                handedness = track.confirmed_handedness or raw.handedness
                gesture = gesture_clf.classify(raw)

                # 신규 트랙 매칭 (frames_since_entry >= 3 이후 1회)
                if track.pending_match and track.frames_since_entry >= 3 and players:
                    pid, score = match_player_by_arm(
                        handedness=handedness,
                        entry_wrist_xy=track.entry_wrist_xy,
                        entry_arm_angle=track.entry_arm_angle,
                        players=players,
                        excluded_player_ids=excluded,
                    )
                    track.player_id_buf.append(pid)
                    track.pending_match = False
                    pname = next((p.playername for p in players if p.player_id == pid), "?")
                    print(
                        f"  track#{track.track_id}  {handedness:5s}  {gesture:8s}  "
                        f"angle={math.degrees(track.entry_arm_angle):.0f}°  "
                        f"→ {pname}  score={score:.3f}"
                    )

                player_id = track.confirmed_player_id
                player_name = next((p.playername for p in players if p.player_id == player_id), "?")
                if prev_results.get(track.track_id) != player_name:
                    prev_results[track.track_id] = player_name

            # 등록된 player anchor의 wrist + arm_angle을 좌석별 색깔로 그리기
            for p in players:
                col = color_by_pid[p.player_id]
                for arm in (p.seat_zone.right_arm, p.seat_zone.left_arm):
                    h, w = frame.shape[:2]
                    cx, cy = int(arm.wrist_xy[0] * w), int(arm.wrist_xy[1] * h)
                    cv2.circle(frame, (cx, cy), 6, col, 2)
                    _draw_arrow(frame, arm.wrist_xy, arm.arm_angle, col, 0.07, 1)
                # body_xy도 점으로 (화면 안일 때만)
                bx, by = p.seat_zone.body_xy
                if 0 <= bx <= 1 and 0 <= by <= 1:
                    h, w = frame.shape[:2]
                    cv2.drawMarker(
                        frame,
                        (int(bx * w), int(by * h)),
                        col,
                        markerType=cv2.MARKER_CROSS,
                        markerSize=18,
                        thickness=2,
                    )

            # 활성 트랙 오버레이
            for raw, track in zip(raw_hands, tracks, strict=True):
                h, w = frame.shape[:2]
                wx = int(raw.wrist_xy[0] * w)
                wy = int(raw.wrist_xy[1] * h)
                pid = track.confirmed_player_id
                player_name = next((p.playername for p in players if p.player_id == pid), "?")
                col = color_by_pid.get(pid, (200, 200, 200))
                handedness = track.confirmed_handedness or raw.handedness
                gesture = gesture_clf.classify(raw)
                label = f"#{track.track_id} {player_name} [{handedness[0]}] {gesture}"
                cv2.circle(frame, (wx, wy), 8, col, -1)
                _draw_arrow(frame, raw.wrist_xy, track.arm_angle, col, 0.1, 2)
                cv2.putText(
                    frame,
                    label,
                    (wx + 12, wy),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    col,
                    2,
                )

            cv2.imshow("test_player_id", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hand_detector.close()


if __name__ == "__main__":
    main()
