"""mp4 → 프레임 이미지 추출 도구.

Usage:
    python -m tools.frame_extractor --src /tmp/session.mp4 --out /tmp/frames/
    python -m tools.frame_extractor --src /tmp/session.mp4 --out /tmp/frames/ --step 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="mp4 프레임 추출")
    p.add_argument("--src", required=True, help="입력 mp4 경로")
    p.add_argument("--out", required=True, help="출력 디렉토리")
    p.add_argument("--step", type=int, default=1, help="추출 간격 (1=전체, 5=5프레임마다 1장)")
    p.add_argument("--fmt", default="jpg", choices=["jpg", "png"], help="출력 이미지 포맷")
    p.add_argument("--start", type=int, default=0, help="시작 프레임 인덱스")
    p.add_argument("--end", type=int, default=None, help="종료 프레임 인덱스")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.src)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[frame_extractor] {args.src}  total={total}  step={args.step}")

    idx = 0
    saved = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx < args.start:
            idx += 1
            continue
        if args.end is not None and idx >= args.end:
            break
        if (idx - args.start) % args.step == 0:
            fname = out_dir / f"frame_{idx:06d}.{args.fmt}"
            cv2.imwrite(str(fname), frame)
            saved += 1
        idx += 1

    cap.release()
    print(f"[frame_extractor] Saved {saved} frames → {out_dir}")


if __name__ == "__main__":
    main()
