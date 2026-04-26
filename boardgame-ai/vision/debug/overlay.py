"""디버그 오버레이 렌더러.

config.debug_overlay=True 일 때만 사용.
FramePerception의 감지 결과를 BGR 프레임 위에 시각화.
"""

from __future__ import annotations

from typing import Any

import cv2

from vision.schemas import BBox, FramePerception

# 색상 (BGR)
_COLOR_TRAY = (0, 255, 0)
_COLOR_TRAY_INNER = (0, 200, 100)
_COLOR_ROLL_TRAY = (255, 165, 0)
_COLOR_DICE = (0, 100, 255)
_COLOR_HAND_R = (255, 0, 0)
_COLOR_HAND_L = (0, 0, 255)
_COLOR_TEXT = (255, 255, 255)
_FONT = cv2.FONT_HERSHEY_SIMPLEX


def draw_overlay(
    frame_bgr: Any,
    perception: FramePerception,
    recent_event: dict | None = None,
    event_ttl_frames: int = 0,
    warmup_remaining: int = 0,
) -> Any:
    """FramePerception을 frame_bgr 위에 그려서 반환 (원본 수정).

    recent_event : 최근 발생한 GameEvent.data (dice_rolled 등)
    event_ttl_frames : 남은 표시 프레임 수 (>0이면 배너 표시)
    warmup_remaining : 워밍업 중 남은 프레임 수 (>0이면 WARMUP 배지 표시)
    """
    h, w = frame_bgr.shape[:2]

    def _draw_bbox(bbox: BBox, color: tuple, label: str) -> None:
        x1 = int(bbox.x1 * w)
        y1 = int(bbox.y1 * h)
        x2 = int(bbox.x2 * w)
        y2 = int(bbox.y2 * h)
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame_bgr, label, (x1, max(y1 - 6, 10)), _FONT, 0.5, color, 1, cv2.LINE_AA)

    # tray 계열
    if perception.tray:
        _draw_bbox(perception.tray, _COLOR_TRAY, f"tray {perception.tray.conf:.2f}")
    if perception.tray_inner:
        _draw_bbox(
            perception.tray_inner, _COLOR_TRAY_INNER, f"inner {perception.tray_inner.conf:.2f}"
        )
    if perception.roll_tray:
        _draw_bbox(
            perception.roll_tray, _COLOR_ROLL_TRAY, f"roll_tray {perception.roll_tray.conf:.2f}"
        )

    # 주사위
    for ds in perception.dice:
        pip_str = str(ds.pip_count) if ds.pip_count is not None else "?"
        label = f"d{ds.track_id}:{pip_str} s{ds.stable_frames}"
        _draw_bbox(ds.bbox, _COLOR_DICE, label)

    # 손 landmark + 정보
    for hand in perception.hands:
        color = _COLOR_HAND_R if hand.handedness == "Right" else _COLOR_HAND_L
        # wrist 점
        wx = int(hand.wrist_xy[0] * w)
        wy = int(hand.wrist_xy[1] * h)
        cv2.circle(frame_bgr, (wx, wy), 6, color, -1)
        # 21 landmarks
        for lx, ly in hand.landmarks_21:
            cv2.circle(frame_bgr, (int(lx * w), int(ly * h)), 2, color, -1)
        # 라벨
        pid = hand.player_id or "?"
        gest = hand.gesture or "neutral"
        cv2.putText(
            frame_bgr,
            f"{hand.handedness[0]}:{pid}:{gest}",
            (wx + 8, wy),
            _FONT,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )

    # roll_state — 좌상단에 큼지막하게 (디버그 시 한눈에 보이게)
    roll_state = perception.phase_hints.get("roll_state", "")
    actor = perception.roll_actor_id or "-"
    cv2.putText(
        frame_bgr, f"STATE: {roll_state}", (10, 36), _FONT, 0.9, (0, 255, 255), 2, cv2.LINE_AA
    )
    info = f"actor:{actor}  f{perception.frame_id}"
    cv2.putText(frame_bgr, info, (10, 60), _FONT, 0.55, _COLOR_TEXT, 1, cv2.LINE_AA)

    # warmup 배지 — 우상단
    if warmup_remaining > 0:
        warm = f"WARMUP {warmup_remaining}"
        (tw, th), _ = cv2.getTextSize(warm, _FONT, 0.7, 2)
        bx = w - tw - 16
        by = 36
        cv2.rectangle(frame_bgr, (bx - 8, by - th - 6), (bx + tw + 8, by + 6), (0, 0, 0), -1)
        cv2.putText(frame_bgr, warm, (bx, by), _FONT, 0.7, (0, 200, 255), 2, cv2.LINE_AA)

    # dice_rolled 이벤트 배너 (화면 중앙 상단)
    if event_ttl_frames > 0 and recent_event is not None:
        values = recent_event.get("dice_values", [])
        evt_actor = recent_event.get("actor_id", "?")
        banner = f"ROLLED  {values}  by {evt_actor}"
        (tw, th), _ = cv2.getTextSize(banner, _FONT, 1.0, 2)
        bx = (w - tw) // 2
        by = 70
        # 반투명 배경
        cv2.rectangle(frame_bgr, (bx - 8, by - th - 8), (bx + tw + 8, by + 8), (0, 0, 0), -1)
        cv2.putText(frame_bgr, banner, (bx, by), _FONT, 1.0, (0, 255, 128), 2, cv2.LINE_AA)

    return frame_bgr
