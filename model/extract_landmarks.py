"""Run MediaPipe Pose Landmarker over REHAB24-6 videos and save per-frame landmarks (#4).

    python -m model.extract_landmarks --exercise squat --variant full --workers 6

Output: ~/rm-data/landmarks/<variant>/<exercise>/<video_id>-<camera>.npz with
  image  (T, 33, 4)  normalized x, y, z, visibility  (NaN where no person was detected)
  world  (T, 33, 3)  metric world coordinates from MediaPipe (hip-centred)
  fps, width, height, seconds (processing time)
Re-runnable: videos that already have an output file are skipped.
"""

import argparse
import csv
import time
from multiprocessing import Pool

import numpy as np

from model.config import LANDMARKS, MANIFEST, POSE_MODELS

N_LANDMARKS = 33


def pose_video(video_path: str, model_path: str, max_frames: int | None = None) -> dict:
    """Pose landmarks for every frame of one video. Shared with the live analysis path."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    image = np.full((n, N_LANDMARKS, 4), np.nan, dtype=np.float32)
    world = np.full((n, N_LANDMARKS, 3), np.nan, dtype=np.float32)
    brightness = np.full(n, np.nan, dtype=np.float32)

    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    t0 = time.perf_counter()
    i = 0
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok or (max_frames and i >= max_frames):
                break
            if i >= len(image):  # frame count in the header can be short
                image = np.concatenate([image, np.full((256, N_LANDMARKS, 4), np.nan, np.float32)])
                world = np.concatenate([world, np.full((256, N_LANDMARKS, 3), np.nan, np.float32)])
                brightness = np.concatenate([brightness, np.full(256, np.nan, np.float32)])
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            brightness[i] = float(rgb.mean()) / 255.0
            res = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(i * 1000 / fps))
            if res.pose_landmarks:
                image[i] = [(p.x, p.y, p.z, p.visibility) for p in res.pose_landmarks[0]]
                world[i] = [(p.x, p.y, p.z) for p in res.pose_world_landmarks[0]]
            i += 1
    cap.release()
    return {"image": image[:i], "world": world[:i], "brightness": brightness[:i], "fps": fps,
            "width": width, "height": height, "seconds": time.perf_counter() - t0}


def _job(args):
    row, variant = args
    out = LANDMARKS / variant / row["exercise"] / f"{row['video_id']}-{row['camera']}.npz"
    if out.exists():
        return out.name, "skip", 0.0, 0
    out.parent.mkdir(parents=True, exist_ok=True)
    r = pose_video(row["video_path"], str(POSE_MODELS / f"pose_landmarker_{variant}.task"))
    np.savez_compressed(out, **r)
    detected = float(np.mean(~np.isnan(r["image"][:, 0, 0]))) if len(r["image"]) else 0.0
    return out.name, f"{detected:.0%} frames with a person", r["seconds"], len(r["image"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", default="squat")
    ap.add_argument("--variant", default="full", choices=["lite", "full", "heavy"])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--videos", nargs="*", help="limit to these video_ids")
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(MANIFEST)) if r["exercise"] == args.exercise]
    if args.videos:
        rows = [r for r in rows if r["video_id"] in args.videos]
    print(f"{len(rows)} videos, variant={args.variant}, workers={args.workers}", flush=True)
    t0 = time.perf_counter()
    with Pool(args.workers) as pool:
        for name, status, secs, frames in pool.imap_unordered(_job, [(r, args.variant) for r in rows]):
            rate = f"{frames / secs:.1f} fps" if secs else ""
            print(f"{name:32} {status:26} {rate}", flush=True)
    print(f"done in {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
