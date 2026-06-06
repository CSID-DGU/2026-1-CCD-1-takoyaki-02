"""데모 공용 유틸 — 카메라 루프, 한글 텍스트, 손 그리기, 플레이어 매칭.

모든 데모가 import 해서 쓴다. 좌표는 정규화(0~1) 기준, 그릴 때 픽셀로 변환.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from core.models import ArmAnchor, Player, SeatZone
from vision.detectors.gesture_classifier import GestureClassifier
from vision.detectors.hand_detector import HandDetector
from vision.geometry.arm_vector import compute_arm_angle, estimate_body_xy
from vision.schemas import HandDet
from vision.attribution.seat_matcher import (
    MARGIN_THRESHOLD,
    match_player_by_arm,
    players_with_both_hands_tracked,
)
from vision.tracking.hand_tracker import MAX_MATCH_ATTEMPTS, HandTracker

# ── 기본 경로 ────────────────────────────────────────────────────────────────
DEMO_DIR = Path(__file__).parent
DEFAULT_PLAYERS_PATH = DEMO_DIR / "players.json"

# ── 색상 (BGR) ───────────────────────────────────────────────────────────────
PLAYER_COLORS: list[tuple[int, int, int]] = [
    (80, 220, 80),    # green
    (255, 160, 40),   # blue
    (40, 160, 255),   # orange
    (220, 80, 220),   # magenta
    (40, 220, 220),   # yellow
    (200, 200, 80),   # teal
]
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (60, 60, 235)
GREEN = (80, 220, 80)
GRAY = (160, 160, 160)

# MediaPipe 21-landmark 연결 (손 골격)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),         # 엄지
    (0, 5), (5, 6), (6, 7), (7, 8),         # 검지
    (5, 9), (9, 10), (10, 11), (11, 12),    # 중지
    (9, 13), (13, 14), (14, 15), (15, 16),  # 약지
    (13, 17), (17, 18), (18, 19), (19, 20), # 새끼
    (0, 17),                                # 손바닥 밑변
]


def player_color(idx: int) -> tuple[int, int, int]:
    return PLAYER_COLORS[idx % len(PLAYER_COLORS)]


# ── 한글 텍스트 렌더러 (PIL) ──────────────────────────────────────────────────
_FONT_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


class TextRenderer:
    """PIL 기반 한글 텍스트. PIL/폰트 없으면 cv2 영문 폴백."""

    def __init__(self) -> None:
        self._ok = False
        self._font_path: str | None = None
        try:
            from PIL import ImageFont  # noqa: F401

            for cand in _FONT_CANDIDATES:
                if Path(cand).exists():
                    self._font_path = cand
                    break
            self._ok = self._font_path is not None
            self._cache: dict[int, Any] = {}
        except Exception:
            self._ok = False

    def _font(self, size: int):
        from PIL import ImageFont

        if size not in self._cache:
            try:
                self._cache[size] = ImageFont.truetype(self._font_path, size)
            except Exception:
                self._cache[size] = ImageFont.truetype(self._font_path, size, index=0)
        return self._cache[size]

    def text(
        self,
        frame_bgr: np.ndarray,
        pos: tuple[int, int],
        text: str,
        color: tuple[int, int, int] = WHITE,
        size: int = 24,
        bg: tuple[int, int, int] | None = None,
    ) -> None:
        """frame 위에 text를 그린다 (pos = 좌상단)."""
        if not self._ok:
            cv2.putText(
                frame_bgr, text, (pos[0], pos[1] + size),
                cv2.FONT_HERSHEY_SIMPLEX, size / 32.0, color, 2, cv2.LINE_AA,
            )
            return
        from PIL import Image, ImageDraw

        img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        font = self._font(size)
        if bg is not None:
            l, t, r, b = draw.textbbox(pos, text, font=font)
            draw.rectangle([l - 6, t - 4, r + 6, b + 4], fill=(bg[2], bg[1], bg[0]))
        draw.text(pos, text, font=font, fill=(color[2], color[1], color[0]))
        frame_bgr[:] = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# ── 좌표 변환 + 그리기 ────────────────────────────────────────────────────────
def to_px(xy: tuple[float, float], w: int, h: int) -> tuple[int, int]:
    return (int(xy[0] * w), int(xy[1] * h))


def clamp_px(xy: tuple[float, float], w: int, h: int, margin: int = 8) -> tuple[int, int]:
    x = min(max(int(xy[0] * w), margin), w - margin)
    y = min(max(int(xy[1] * h), margin), h - margin)
    return (x, y)


def draw_hand(
    frame: np.ndarray,
    landmarks_21: list[tuple[float, float]],
    color: tuple[int, int, int],
    point_radius: int = 3,
    line_thickness: int = 2,
) -> None:
    """21 landmark + 골격 연결선."""
    h, w = frame.shape[:2]
    pts = [to_px(lm, w, h) for lm in landmarks_21]
    if len(pts) >= 21:
        for a, b in HAND_CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], color, line_thickness, cv2.LINE_AA)
    for i, p in enumerate(pts):
        r = point_radius + 2 if i == 0 else point_radius  # wrist 강조
        cv2.circle(frame, p, r, color, -1, cv2.LINE_AA)


def draw_bbox_norm(
    frame: np.ndarray,
    bbox,
    color: tuple[int, int, int],
    label: str | None = None,
    thickness: int = 2,
) -> None:
    h, w = frame.shape[:2]
    x1, y1 = int(bbox.x1 * w), int(bbox.y1 * h)
    x2, y2 = int(bbox.x2 * w), int(bbox.y2 * h)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    if label:
        cv2.rectangle(frame, (x1, y1 - 20), (x1 + 10 * len(label), y1), color, -1)
        cv2.putText(frame, label, (x1 + 3, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, BLACK, 1, cv2.LINE_AA)


# ── 플레이어 직렬화 ───────────────────────────────────────────────────────────
def load_players(path: str | Path = DEFAULT_PLAYERS_PATH) -> list[Player]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    players = [Player.from_dict(d) for d in data]
    return [pl for pl in players if pl.seat_zone is not None]


def save_players(players: list[Player], path: str | Path = DEFAULT_PLAYERS_PATH) -> None:
    p = Path(path)
    p.write_text(
        json.dumps([pl.to_dict() for pl in players], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_seat_zone(
    right_wrist: tuple[float, float],
    right_lms: list[tuple[float, float]],
    left_wrist: tuple[float, float],
    left_lms: list[tuple[float, float]],
) -> SeatZone:
    """양손 landmark에서 SeatZone 생성 (FusionEngine과 동일 로직)."""
    r_angle = compute_arm_angle(right_lms)
    l_angle = compute_arm_angle(left_lms)
    body_xy, posture = estimate_body_xy(right_wrist, r_angle, left_wrist, l_angle)
    return SeatZone(
        right_arm=ArmAnchor(handedness="Right", wrist_xy=right_wrist, arm_angle=r_angle),
        left_arm=ArmAnchor(handedness="Left", wrist_xy=left_wrist, arm_angle=l_angle),
        body_xy=body_xy,
        posture=posture,
    )


# ── 손 처리기 (감지 + 추적 + 제스처 + 플레이어 매칭) ──────────────────────────
class HandProcessor:
    """HandDetector + HandTracker + GestureClassifier + 플레이어 매칭.

    파이프라인 _stabilize_hands 와 동일한 로직. 데모 #2/#5 에서 재사용.
    players 가 비어 있으면 매칭 없이 손만 안정화.
    """

    def __init__(self, players: list[Player] | None = None, max_num_hands: int = 8) -> None:
        self._players = players or []
        self._detector = HandDetector(max_num_hands=max_num_hands)
        self._gesture = GestureClassifier()
        self._tracker = HandTracker()
        self._prev_gestures: dict[int, str | None] = {}

    def close(self) -> None:
        self._detector.close()

    def process(self, frame_bgr: np.ndarray) -> list[HandDet]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        raw_hands = self._detector.detect(frame_rgb)
        return self._stabilize(raw_hands)

    def _stabilize(self, raw_hands: list[HandDet]) -> list[HandDet]:
        detections = [(h.wrist_xy, compute_arm_angle(h.landmarks_21)) for h in raw_hands]
        tracks = self._tracker.update(detections)
        active = self._tracker.active_tracks()

        out: list[HandDet] = []
        for raw, track in zip(raw_hands, tracks, strict=True):
            track.handedness_buf.append(raw.handedness)
            confirmed_hd = track.confirmed_handedness
            stable_handedness = confirmed_hd or raw.handedness

            if (
                confirmed_hd is not None
                and track.last_match_handedness is not None
                and confirmed_hd != track.last_match_handedness
            ):
                track.pending_match = True
                track.match_attempts = 0

            should_match = (
                self._players
                and track.frames_since_entry >= 3
                and confirmed_hd is not None
                and (track.pending_match or track.last_match_handedness != confirmed_hd)
            )
            if should_match:
                self_pid = track.confirmed_player_id
                excluded = players_with_both_hands_tracked(
                    [t for t in active if t.track_id != track.track_id]
                )
                if self_pid is not None:
                    excluded.discard(self_pid)
                pid, _score, margin = match_player_by_arm(
                    handedness=confirmed_hd,
                    entry_wrist_xy=track.entry_wrist_xy,
                    entry_arm_angle=track.entry_arm_angle,
                    players=self._players,
                    excluded_player_ids=excluded,
                )
                track.player_id_buf.append(pid)
                track.match_attempts += 1
                track.last_match_handedness = confirmed_hd
                if margin >= MARGIN_THRESHOLD or track.match_attempts >= MAX_MATCH_ATTEMPTS:
                    track.pending_match = False

            player_id = track.confirmed_player_id or track.best_effort_player_id
            prev = self._prev_gestures.get(track.track_id)
            tmp = HandDet(
                handedness=stable_handedness,
                wrist_xy=raw.wrist_xy,
                landmarks_21=raw.landmarks_21,
            )
            gesture = self._gesture.classify_with_prev(tmp, prev)
            self._prev_gestures[track.track_id] = gesture

            out.append(
                HandDet(
                    handedness=stable_handedness,
                    wrist_xy=raw.wrist_xy,
                    landmarks_21=raw.landmarks_21,
                    gesture=gesture,
                    player_id=player_id,
                    arm_angle=track.arm_angle,
                )
            )

        live = {t.track_id for t in self._tracker.active_tracks()}
        for tid in [t for t in self._prev_gestures if t not in live]:
            del self._prev_gestures[tid]
        return out


# ── 인자 파서 + 카메라 루프 ───────────────────────────────────────────────────
def base_arg_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--source", default="0", help="카메라 인덱스(정수) 또는 동영상 경로")
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--mirror", action="store_true", help="좌우 반전(셀카 모드)")
    p.add_argument("--record", default=None, help="저장할 mp4 경로 (지정 시 녹화)")
    p.add_argument("--players", default=str(DEFAULT_PLAYERS_PATH), help="플레이어 JSON 경로")
    return p


def resolve_source(source: str) -> int | str:
    try:
        return int(source)
    except ValueError:
        return source


class Demo:
    """카메라 read → process(frame) → annotated → imshow/record 루프.

    process_fn(frame_bgr, frame_id, ts) -> annotated_bgr.
    'q' 또는 ESC 로 종료.
    """

    def __init__(
        self,
        title: str,
        args: argparse.Namespace,
        show_fps: bool = True,
        fullscreen: bool = False,
    ) -> None:
        self.title = title
        self.args = args
        self.show_fps = show_fps
        self.fullscreen = fullscreen
        self.text = TextRenderer()
        self._writer: cv2.VideoWriter | None = None

    def run(self, process_fn: Callable[[np.ndarray, int, float], np.ndarray]) -> None:
        http_url = getattr(self.args, "http", None)
        cap = None
        if http_url:
            read_frame = self._make_http_reader(http_url)
            print(f"[demo] HTTP 프레임 소스: {http_url} (카메라 직접 열지 않음)")
        else:
            src = resolve_source(self.args.source)
            cap = cv2.VideoCapture(src)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.args.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.args.height)
            if not cap.isOpened():
                print(f"[demo] 카메라/소스 열기 실패: {src}")
                return
            aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[demo] 요청 {self.args.width}x{self.args.height} → 실제 캡처 {aw}x{ah}")
            if (aw, ah) != (self.args.width, self.args.height):
                print("[demo]  ⚠ 카메라가 요청 해상도를 안 줌. 카메라 지원 해상도로 조정됐을 수 있음.")
            read_frame = lambda: cap.read()  # noqa: E731

        win = self.title
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        if self.fullscreen:
            cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        frame_id = 0
        t_prev = time.time()
        fps = 0.0
        miss = 0
        print(f"[{self.title}] 시작 — 'q' 또는 ESC 로 종료")
        try:
            while True:
                ret, frame = read_frame()
                if not ret or frame is None:
                    miss += 1
                    if http_url and miss < 200:
                        time.sleep(0.05)  # 백엔드 프레임 아직 — 잠깐 대기 후 재시도
                        cv2.waitKey(1)
                        continue
                    print("[demo] 프레임 없음 — 종료")
                    break
                miss = 0
                if self.args.mirror:
                    frame = cv2.flip(frame, 1)

                ts = time.time()
                annotated = process_fn(frame, frame_id, ts)

                now = time.time()
                dt = now - t_prev
                t_prev = now
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps else 1.0 / dt
                if self.show_fps:
                    cv2.putText(annotated, f"{fps:4.1f} FPS", (annotated.shape[1] - 130, 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2, cv2.LINE_AA)

                if self.args.record:
                    if self._writer is None:
                        h, w = annotated.shape[:2]
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        self._writer = cv2.VideoWriter(self.args.record, fourcc, 20.0, (w, h))
                        print(f"[demo] 녹화 시작 → {self.args.record}")
                    self._writer.write(annotated)

                cv2.imshow(win, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                frame_id += 1
        finally:
            if cap is not None:
                cap.release()
            if self._writer is not None:
                self._writer.release()
            cv2.destroyAllWindows()

    @staticmethod
    def _make_http_reader(url: str) -> Callable[[], tuple[bool, "np.ndarray | None"]]:
        """HTTP JPEG 엔드포인트를 폴링해 (ret, frame) 반환하는 reader."""
        import urllib.request

        def read() -> tuple[bool, "np.ndarray | None"]:
            try:
                with urllib.request.urlopen(url, timeout=2.0) as resp:
                    if resp.status != 200:
                        return False, None
                    buf = np.frombuffer(resp.read(), dtype=np.uint8)
                frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                return (frame is not None), frame
            except Exception:
                return False, None

        return read
