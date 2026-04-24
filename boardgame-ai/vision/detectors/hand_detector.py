"""MediaPipe HandLandmarker (Tasks API, mediapipe 0.10+) 기반 손 감지.

model_path: weights/hand_landmarker.task
wrist = landmark[0], 좌표는 0~1 정규화.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mediapipe as mp
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.core import base_options as mp_base

from vision.schemas import HandDet

_DEFAULT_MODEL = Path(__file__).parent.parent.parent / "weights" / "hand_landmarker.task"


class HandDetector:
    def __init__(
        self,
        model_path: str | Path = _DEFAULT_MODEL,
        max_num_hands: int = 8,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
    ) -> None:
        base_opts = mp_base.BaseOptions(model_asset_path=str(model_path))
        opts = mp_vision.HandLandmarkerOptions(
            base_options=base_opts,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=max_num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(opts)
        self._frame_ts_ms = 0  # VIDEO 모드는 단조 증가 타임스탬프 필요

    def detect(self, frame_rgb: Any) -> list[HandDet]:
        """RGB numpy 배열 → HandDet 리스트. gesture/player_id는 None."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        self._frame_ts_ms += 33  # ~30fps 가정, 단조 증가만 맞으면 됨
        result = self._landmarker.detect_for_video(mp_image, self._frame_ts_ms)

        if not result.hand_landmarks:
            return []

        dets: list[HandDet] = []
        for i, hand_lms in enumerate(result.hand_landmarks):
            # handedness
            if result.handedness and i < len(result.handedness):
                handedness = result.handedness[i][0].category_name  # "Left" | "Right"
            else:
                handedness = "Right"

            landmarks_21: list[tuple[float, float]] = [
                (float(lm.x), float(lm.y)) for lm in hand_lms
            ]
            wrist_xy = landmarks_21[0]

            dets.append(
                HandDet(
                    handedness=handedness,
                    wrist_xy=wrist_xy,
                    landmarks_21=landmarks_21,
                    gesture=None,
                    player_id=None,
                )
            )

        return dets

    def close(self) -> None:
        self._landmarker.close()
