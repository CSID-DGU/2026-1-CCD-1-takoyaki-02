"""MediaPipe 21 landmarks 기반 손 제스처 분류.

지원 제스처:
  v_sign    : 검지+중지 펴짐, 약지+새끼 굽힘
  ok_sign   : 엄지 tip ↔ 검지 tip 거리 < 손 길이 X%, 나머지 손가락 펴짐
  grab      : 다섯 손가락 모두 굽힘 (tip이 wrist보다 가까움)
  release   : 이전 grab → 현재 손가락 펴짐 (호출자가 이전 상태 추적)
  neutral   : 그 외
"""

from __future__ import annotations

import math

from vision.schemas import HandDet

# MediaPipe landmark 인덱스
_WRIST = 0
_THUMB_CMC, _THUMB_MCP, _THUMB_IP, _THUMB_TIP = 1, 2, 3, 4
_INDEX_MCP, _INDEX_PIP, _INDEX_DIP, _INDEX_TIP = 5, 6, 7, 8
_MIDDLE_MCP, _MIDDLE_PIP, _MIDDLE_DIP, _MIDDLE_TIP = 9, 10, 11, 12
_RING_MCP, _RING_PIP, _RING_DIP, _RING_TIP = 13, 14, 15, 16
_PINKY_MCP, _PINKY_PIP, _PINKY_DIP, _PINKY_TIP = 17, 18, 19, 20


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _finger_extended(
    lms: list[tuple[float, float]],
    tip: int,
    pip: int,
    mcp: int,
) -> bool:
    """tip이 pip보다 wrist에서 더 멀면 펴진 것으로 판정."""
    wrist = lms[_WRIST]
    return _dist(lms[tip], wrist) > _dist(lms[pip], wrist)


def _finger_curled(
    lms: list[tuple[float, float]],
    tip: int,
    mcp: int,
) -> bool:
    """tip이 mcp보다 wrist에 가까우면 굽힌 것."""
    wrist = lms[_WRIST]
    return _dist(lms[tip], wrist) < _dist(lms[mcp], wrist)


class GestureClassifier:
    """
    ok_ratio  : ok_sign 판정 엄지-검지 거리 / 손 길이 임계값 (기본 0.15)
    grab_ratio: grab 판정 tip-wrist 거리 / 손 길이 임계값 (기본 0.55)
    """

    def __init__(
        self,
        ok_ratio: float = 0.15,
        grab_ratio: float = 0.55,
    ) -> None:
        self._ok_ratio = ok_ratio
        self._grab_ratio = grab_ratio

    def classify(self, hand: HandDet) -> str:
        lms = hand.landmarks_21
        if len(lms) != 21:
            return "neutral"

        hand_length = _dist(lms[_WRIST], lms[_MIDDLE_MCP]) or 1e-6

        # ── grab: 모든 손가락 굽힘 ──────────────────────────────────────
        tips = [_THUMB_TIP, _INDEX_TIP, _MIDDLE_TIP, _RING_TIP, _PINKY_TIP]
        mcps = [_THUMB_MCP, _INDEX_MCP, _MIDDLE_MCP, _RING_MCP, _PINKY_MCP]
        all_curled = all(
            _dist(lms[tip], lms[_WRIST]) < hand_length * self._grab_ratio
            for tip in tips
        )
        if all_curled:
            return "grab"

        # ── v_sign: 검지+중지 펴짐, 약지+새끼 굽힘 ────────────────────
        index_ext = _finger_extended(lms, _INDEX_TIP, _INDEX_PIP, _INDEX_MCP)
        middle_ext = _finger_extended(lms, _MIDDLE_TIP, _MIDDLE_PIP, _MIDDLE_MCP)
        ring_curl = _finger_curled(lms, _RING_TIP, _RING_MCP)
        pinky_curl = _finger_curled(lms, _PINKY_TIP, _PINKY_MCP)
        if index_ext and middle_ext and ring_curl and pinky_curl:
            return "v_sign"

        # ── ok_sign: 엄지-검지 터치, 나머지 세 손가락 펴짐 ────────────
        thumb_index_dist = _dist(lms[_THUMB_TIP], lms[_INDEX_TIP])
        ring_ext = _finger_extended(lms, _RING_TIP, _RING_PIP, _RING_MCP)
        pinky_ext = _finger_extended(lms, _PINKY_TIP, _PINKY_PIP, _PINKY_MCP)
        if (
            thumb_index_dist < hand_length * self._ok_ratio
            and middle_ext
            and ring_ext
            and pinky_ext
        ):
            return "ok_sign"

        return "neutral"

    def classify_with_prev(self, hand: HandDet, prev_gesture: str | None) -> str:
        """release 감지: 직전 grab → 현재 non-grab."""
        current = self.classify(hand)
        if prev_gesture == "grab" and current != "grab":
            return "release"
        return current
