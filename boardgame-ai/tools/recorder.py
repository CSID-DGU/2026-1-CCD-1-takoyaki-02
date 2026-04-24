"""카메라 영상 녹화 도구.

Usage:
    python -m tools.recorder --out /tmp/session.mp4 --duration 120
    python -m tools.recorder --out /tmp/session.mp4  # Ctrl+C로 종료
"""

from __future__ import annotations

import argparse
import time

import cv2


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="카메라 영상 녹화")
    p.add_argument("--out", required=True, help="출력 mp4 경로")
    p.add_argument("--source", default="0", help="카메라 인덱스 또는 mp4 경로")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument(
        "--duration", type=float, default=None, help="녹화 시간(초). 미지정시 Ctrl+C까지"
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    try:
        source: int | str = int(args.source)
    except ValueError:
        source = args.source

    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(args.out, fourcc, args.fps, (args.width, args.height))

    print(f"[recorder] Recording → {args.out}  (Ctrl+C to stop)")
    start = time.time()
    frames = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)
            frames += 1
            if args.duration and (time.time() - start) >= args.duration:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        writer.release()
        elapsed = time.time() - start
        print(f"[recorder] Saved {frames} frames ({elapsed:.1f}s) → {args.out}")


if __name__ == "__main__":
    main()
