"""주사위 눈 수 파라미터 실시간 튜닝 도구.

트랙바로 HoughCircles/Blob 파라미터를 조절하면서
실제 카메라 또는 저장된 영상에서 인식 결과를 실시간 확인.

Usage:
    python3 -m tools.tune_dot_counter --source 0 --weights weights/yacht_v4.pt
    python3 -m tools.tune_dot_counter --source /tmp/session.mp4 --weights weights/yacht_v4.pt

조작:
    트랙바: 각 파라미터 조절
    's': 현재 파라미터 출력 (복사해서 DotCounterParams에 붙여넣기)
    'q': 종료
"""

from __future__ import annotations

import argparse

import cv2
import numpy as np

from vision.detectors.dot_counter import DotCounter, DotCounterParams
from vision.detectors.yolo_detector import YoloDetector


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="0")
    p.add_argument("--weights", default="weights/yacht_v4.pt")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        source: int | str = int(args.source)
    except ValueError:
        source = args.source

    yolo = YoloDetector(args.weights, conf=0.35, iou=0.5, imgsz=640)
    params = DotCounterParams()
    counter = DotCounter(params)

    WIN = "tune_dot_counter"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, 1280, 720)

    # 트랙바 초기화 (정수 스케일 사용)
    def _tb(name: str, val: int, maxv: int) -> None:
        cv2.createTrackbar(name, WIN, val, maxv, lambda _: None)

    _tb("dp x10",        int(params.dp * 10),              30)
    _tb("min_dist%",     int(params.min_dist_ratio * 100), 80)
    _tb("canny_upper",   params.canny_upper,               200)
    _tb("accum_thresh",  params.accum_thresh,               50)
    _tb("r_min%",        int(params.radius_min_ratio * 100), 20)
    _tb("r_max%",        int(params.radius_max_ratio * 100), 40)
    _tb("clahe_clip x10", int(params.clahe_clip * 10),     80)
    _tb("stable_frames", 15,                               60)

    cap = cv2.VideoCapture(source)
    print(f"[tune] source={source}  Press 's' to print params, 'q' to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # 트랙바 값 읽기
        params.dp               = max(0.1, cv2.getTrackbarPos("dp x10", WIN) / 10)
        params.min_dist_ratio   = max(0.01, cv2.getTrackbarPos("min_dist%", WIN) / 100)
        params.canny_upper      = max(1, cv2.getTrackbarPos("canny_upper", WIN))
        params.accum_thresh     = max(1, cv2.getTrackbarPos("accum_thresh", WIN))
        params.radius_min_ratio = max(0.01, cv2.getTrackbarPos("r_min%", WIN) / 100)
        params.radius_max_ratio = max(0.02, cv2.getTrackbarPos("r_max%", WIN) / 100)
        params.clahe_clip       = max(0.1, cv2.getTrackbarPos("clahe_clip x10", WIN) / 10)
        stable_frames           = cv2.getTrackbarPos("stable_frames", WIN)

        # YOLO 감지
        dets = yolo.detect(frame)
        dice_dets = [d for d in dets if d.cls_name == "dice"]

        h, w = frame.shape[:2]
        vis = frame.copy()

        # 각 주사위별 크롭 + 인식 결과 표시
        crops: list[np.ndarray] = []
        for det in dice_dets:
            result, crop_vis = counter.count_with_debug(frame, det.bbox)
            crops.append(cv2.resize(crop_vis, (120, 120)))

            # 원본 프레임에 bbox + 결과 표시
            x1 = int(det.bbox.x1 * w)
            y1 = int(det.bbox.y1 * h)
            x2 = int(det.bbox.x2 * w)
            y2 = int(det.bbox.y2 * h)
            color = (0, 255, 0) if result is not None else (0, 0, 255)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            label = str(result) if result is not None else "?"
            cv2.putText(vis, label, (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

        # 파라미터 정보 표시
        info = (f"dp={params.dp:.1f} dist={params.min_dist_ratio:.2f} "
                f"canny={params.canny_upper} acc={params.accum_thresh} "
                f"r={params.radius_min_ratio:.2f}-{params.radius_max_ratio:.2f} "
                f"stable={stable_frames}f")
        cv2.putText(vis, info, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # 크롭 이미지 우측에 타일로 표시
        if crops:
            tile_h = 120
            tile_col = np.vstack(crops) if len(crops) <= 6 else np.vstack(crops[:6])
            # 높이 맞추기
            pad_h = max(0, vis.shape[0] - tile_col.shape[0])
            if pad_h > 0:
                tile_col = np.vstack([tile_col,
                    np.zeros((pad_h, 120, 3), dtype=np.uint8)])
            else:
                tile_col = tile_col[:vis.shape[0]]
            vis = np.hstack([vis, tile_col])

        cv2.imshow(WIN, vis)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            print("\n=== DotCounterParams (copy to dot_counter.py) ===")
            print(f"DotCounterParams(")
            print(f"    dp={params.dp},")
            print(f"    min_dist_ratio={params.min_dist_ratio},")
            print(f"    canny_upper={params.canny_upper},")
            print(f"    accum_thresh={params.accum_thresh},")
            print(f"    radius_min_ratio={params.radius_min_ratio},")
            print(f"    radius_max_ratio={params.radius_max_ratio},")
            print(f"    clahe_clip={params.clahe_clip},")
            print(f")")
            print(f"stable_frames = {stable_frames}")
            print("=================================================\n")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
