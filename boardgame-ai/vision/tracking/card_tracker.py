"""한밤의 늑대인간 카드 ByteTrack 추적 + 역할/플레이어 매핑.

핵심 불변 조건:
  - track_id 는 물리 카드에 귀속된다. 카드를 뒤집거나 위치가 바뀌어도 유지.
  - cls_name(역할)은 앞면 감지 시에만 갱신된다. card_back 이 감지돼도 덮어쓰지 않음.
  - player_id 는 seat_zone.body_xy 기반 거리 비교로 1회 배정되며, 이후 변경 안 함.
  - player_id=None 인 카드는 센터 카드. card_index 는 매 프레임 bbox.cx 기준 좌→우 재배정.
"""

from __future__ import annotations

import math

from core.models import Player
from vision.schemas import YoloDet
from vision.tracking.byte_tracker import ByteTracker
from vision.werewolf.schemas import (
    BACK_CLASS,
    ROLE_CLASSES,
    CardDetRaw,
    TrackedCard,
)

# 카드-플레이어 매칭 거리 임계 (정규화). 이 값 이하면 해당 플레이어의 카드로 배정.
_PLAYER_MATCH_THRESHOLD = 0.25


class CardTracker:
    """카드 위치 추적 + 역할/플레이어 매핑 관리자.

    Parameters
    ----------
    max_age : int
        ByteTrack 트랙 유지 최대 미매칭 프레임 수. 카드가 느리게 이동하므로 기본값 30.
    min_hits : int
        트랙 확정까지 필요한 최소 연속 매칭 프레임 수.
    iou_threshold : float
        ByteTrack 매칭 IoU 임계값. 카드는 다이스보다 커서 0.4 로 완화.
    player_match_threshold : float
        card bbox 중심 ↔ player body_xy 거리 임계 (정규화).
    """

    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 2,
        iou_threshold: float = 0.4,
        player_match_threshold: float = _PLAYER_MATCH_THRESHOLD,
    ) -> None:
        self._max_age = max_age
        self._min_hits = min_hits
        self._iou_threshold = iou_threshold
        self._player_match_threshold = player_match_threshold

        self._byte_tracker = ByteTracker(
            max_age=max_age,
            min_hits=min_hits,
            iou_threshold=iou_threshold,
        )
        # track_id → TrackedCard
        self._card_states: dict[int, TrackedCard] = {}
        # track_id → 직전 프레임 face_up (just_flipped_up 감지용)
        self._prev_face_up: dict[int, bool] = {}

    # ── 공개 인터페이스 ────────────────────────────────────────────────────────

    def update(
        self,
        card_dets: list[CardDetRaw],
        players: list[Player],
        frame_id: int,
    ) -> list[TrackedCard]:
        """프레임 단위 업데이트. ByteTrack 적용 후 TrackedCard 리스트 반환."""
        # CardDetRaw → YoloDet 변환 (ByteTracker 입력 포맷)
        yolo_dets = [
            YoloDet(cls_name=d.cls_name, bbox=d.bbox)
            for d in card_dets
        ]

        tracked = self._byte_tracker.update(yolo_dets, frame_id)

        # 플레이어 body_xy 맵 구성
        player_positions: dict[str, tuple[float, float]] = {}
        for p in players:
            if p.seat_zone is not None:
                player_positions[p.player_id] = p.seat_zone.body_xy

        active_ids: set[int] = set()

        for track_id, yolo_det in tracked:
            active_ids.add(track_id)
            cls_name = yolo_det.cls_name
            bbox = yolo_det.bbox
            face_up = cls_name in ROLE_CLASSES

            prev_face_up = self._prev_face_up.get(track_id, False)
            just_flipped_up = face_up and not prev_face_up
            self._prev_face_up[track_id] = face_up

            if track_id in self._card_states:
                existing = self._card_states[track_id]
                # 뒷면 감지 시 역할 보존 (덮어쓰지 않음)
                role = cls_name if face_up else existing.cls_name
                player_id = existing.player_id
                card_index = existing.card_index
                stable_frames = existing.stable_frames + 1
            else:
                role = cls_name if face_up else None
                player_id = None
                card_index = 0
                stable_frames = 1

            # player_id 미배정이고 플레이어 위치 정보가 있으면 근접 매칭 시도
            if player_id is None and player_positions:
                player_id = _match_nearest_player(
                    bbox, player_positions, self._player_match_threshold
                )

            self._card_states[track_id] = TrackedCard(
                track_id=track_id,
                bbox=bbox,
                cls_name=role,
                face_up=face_up,
                player_id=player_id,
                card_index=card_index,
                stable_frames=stable_frames,
                just_flipped_up=just_flipped_up,
            )

        # 소멸된 트랙 정리
        for tid in list(self._card_states.keys()):
            if tid not in active_ids:
                del self._card_states[tid]
                self._prev_face_up.pop(tid, None)

        # 센터 카드(player_id=None) card_index 를 좌→우 순으로 재배정
        _assign_center_indices(self._card_states)

        return list(self._card_states.values())

    def get_tracked_cards(self) -> list[TrackedCard]:
        """현재 추적 중인 모든 카드 반환. WerewolfRules 가 직접 호출."""
        return list(self._card_states.values())

    def reset(self) -> None:
        """파이프라인 재시작 시 호출."""
        self._byte_tracker = ByteTracker(
            max_age=self._max_age,
            min_hits=self._min_hits,
            iou_threshold=self._iou_threshold,
        )
        self._card_states.clear()
        self._prev_face_up.clear()


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _match_nearest_player(
    bbox: "BBox",  # noqa: F821 — forward ref 회피
    player_positions: dict[str, tuple[float, float]],
    threshold: float,
) -> str | None:
    """카드 bbox 중심에서 가장 가까운 플레이어를 반환.

    가장 가까운 플레이어까지의 거리가 threshold 를 초과하면 None (센터 카드).
    """
    cx, cy = bbox.cx, bbox.cy
    best_pid: str | None = None
    best_dist = threshold

    for pid, (bx, by) in player_positions.items():
        dist = math.hypot(cx - bx, cy - by)
        if dist < best_dist:
            best_dist = dist
            best_pid = pid

    return best_pid


def _assign_center_indices(card_states: dict[int, "TrackedCard"]) -> None:  # noqa: F821
    """player_id=None 인 카드들을 bbox.cx 기준 좌→우 정렬해 card_index 0/1/2 배정."""
    center_cards = [c for c in card_states.values() if c.player_id is None]
    center_cards.sort(key=lambda c: c.bbox.cx)
    for i, card in enumerate(center_cards):
        card.card_index = i
