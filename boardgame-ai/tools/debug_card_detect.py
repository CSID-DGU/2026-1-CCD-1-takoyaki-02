"""늑대인간 카드 실시간 감지 디버그 뷰어.

사용법:
    python tools/debug_card_detect.py [--camera 0] [--weights weights/werewolf_v6.pt]

조작:
    s  현재 프레임 스크린샷 저장 (debug_screenshots/ 폴더)
    q  종료
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# boardgame-ai 루트를 경로에 추가 (tools/ 안에서 실행될 때)
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2

from vision.detectors.card_detector import WerewolfCardDetector

# 역할별 색상 (BGR)
_ROLE_COLORS: dict[str, tuple[int, int, int]] = {
    "Werewolf":      (0,   0,   220),
    "Minion":        (0,   60,  200),
    "Seer":          (200, 180, 0  ),
    "Robber":        (0,   180, 220),
    "Troublemaker":  (200, 100, 0  ),
    "Drunk":         (180, 0,   180),
    "Insomniac":     (0,   200, 200),
    "Villager":      (60,  200, 60 ),
    "Hunter":        (0,   140, 200),
    "Tanner":        (30,  30,  180),
    "Mason":         (180, 140, 0  ),
    "Doppelganger":  (140, 0,   200),
    "Card_Back":     (120, 120, 120),
}
_DEFAULT_COLOR = (200, 200, 200)


def draw_detections(frame: "cv2.Mat", dets: list, conf_threshold: float = 0.3) -> "cv2.Mat":
    h, w = frame.shape[:2]
    for det in dets:
        if det.conf < conf_threshold:
            continue
        b = det.bbox
        x1 = int(b.x1 * w)
        y1 = int(b.y1 * h)
        x2 = int(b.x2 * w)
        y2 = int(b.y2 * h)

        color = _ROLE_COLORS.get(det.cls_name, _DEFAULT_COLOR)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label = f"{det.cls_name}  {det.conf:.0%}"
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(frame, (x1, y1 - th - baseline - 4), (x1 + tw + 4, y1), color, -1)
        cv2.putText(
            frame, label,
            (x1 + 2, y1 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            (255, 255, 255), 1, cv2.LINE_AA,
        )

    # 좌상단 감지 개수
    cv2.putText(
        frame, f"detected: {len(dets)}",
        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
        (0, 255, 0), 2, cv2.LINE_AA,
    )
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0, help="카메라 인덱스 (기본 0)")
    parser.add_argument(
        "--weights",
        default="weights/werewolf_v6.pt",
        help="YOLO 모델 경로",
    )
    parser.add_argument("--conf", type=float, default=0.3, help="신뢰도 임계값 (기본 0.3)")
    args = parser.parse_args()

    detector = WerewolfCardDetector(model_path=args.weights, conf=args.conf)
    if not detector.is_loaded:
        print(f"[경고] 모델 로드 실패: {args.weights}")
        print("       weights/ 폴더에 werewolf_v6.pt 파일이 있는지 확인하세요.")
        print("       모델 없이 계속 실행합니다 (감지 없음).")

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"[오류] 카메라 {args.camera}를 열 수 없습니다.")
        return

    save_dir = Path("debug_screenshots")
    save_dir.mkdir(exist_ok=True)

    print(f"[info] 카메라 {args.camera} 열림  |  모델: {'로드됨' if detector.is_loaded else 'fallback'}")
    print("       s: 스크린샷 저장   q: 종료")

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[오류] 프레임 읽기 실패")
            break

        dets = detector.detect(frame)
        # 30프레임마다 raw 감지 결과 콘솔 출력
        if frame_count % 30 == 0:
            if dets:
                for d in dets:
                    print(f"  [{frame_count}] {d.cls_name}  conf={d.conf:.2f}")
            else:
                print(f"  [{frame_count}] 감지 없음")
        frame_count += 1
        vis = draw_detections(frame.copy(), dets, conf_threshold=args.conf)

        cv2.imshow("Werewolf Card Detector  [s: save  q: quit]", vis)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s"):
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = save_dir / f"card_{ts}.png"
            cv2.imwrite(str(path), vis)
            print(f"[저장] {path}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # boardgame-ai/ 디렉터리에서 실행해야 함
    os.chdir(Path(__file__).parent.parent)
    main()
