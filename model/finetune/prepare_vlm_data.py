"""Build the vision-language fine-tuning dataset from REHAB24-6 (all 6 exercises, both cameras).

    ~/rm-venv/bin/python -m model.finetune.prepare_vlm_data

For every annotated rep: 8 frames spread evenly through the rep, cropped around the person, tiled
into one 4x2 image (time runs left-to-right, top-to-bottom). Labels come straight from
Segmentation.csv: exercise, correct/incorrect, camera view of that rep, and exercise side.

Split by PERSON (never the same person in train and test):
  test = people 3 and 7, val = person 5, train = everyone else.
Output: ~/rm-data/vlm/{images/*.jpg, train.jsonl, val.jsonl, test.jsonl}
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from model.config import EXERCISES, JOINTS_2D, REHAB, SEGMENTATION
from model.data import rep_view

OUT = REHAB.parent / "vlm"
FRAMES_PER_REP = 8
TILE = 224
GRID = (4, 2)  # columns, rows
TEST_PEOPLE = {3, 7}
VAL_PEOPLE = {5}
CAMERAS = {"c17": ("Camera17", ""), "c18": ("Camera18", "-transposed")}


def split_of(person: int) -> str:
    return "test" if person in TEST_PEOPLE else "val" if person in VAL_PEOPLE else "train"


def crop_box(joints: np.ndarray, frames: list[int], w: int, h: int, pad: float = 0.18):
    """Square box around the person over the given frames, padded, clipped to the image."""
    pts = joints[frames].reshape(-1, 2)
    pts = pts[np.isfinite(pts).all(1)]
    x0, y0 = pts.min(0)
    x1, y1 = pts.max(0)
    side = max(x1 - x0, y1 - y0) * (1 + 2 * pad)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = min(side, max(w, h))
    bx0 = int(np.clip(cx - side / 2, 0, max(0, w - side)))
    by0 = int(np.clip(cy - side / 2, 0, max(0, h - side)))
    return bx0, by0, int(min(side, w - bx0)), int(min(side, h - by0))


def letterbox(img: np.ndarray, size: int) -> np.ndarray:
    h, w = img.shape[:2]
    s = size / max(h, w)
    img = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    out = np.zeros((size, size, 3), np.uint8)
    y, x = (size - img.shape[0]) // 2, (size - img.shape[1]) // 2
    out[y:y + img.shape[0], x:x + img.shape[1]] = img
    return out


def tile(frames: list[np.ndarray]) -> np.ndarray:
    cols, rows = GRID
    canvas = np.zeros((rows * TILE, cols * TILE, 3), np.uint8)
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        canvas[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = f
    return canvas


def main():
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    reps = list(csv.DictReader(open(SEGMENTATION), delimiter=";"))
    by_video = defaultdict(list)
    for r in reps:
        by_video[(int(r["exercise_id"]), r["video_id"])].append(r)

    records = {"train": [], "val": [], "test": []}
    for (ex, vid), rs in sorted(by_video.items()):
        for cam, (cam_name, suffix) in CAMERAS.items():
            path = REHAB / "videos" / f"Ex{ex}" / f"{vid}-{cam_name}-30fps{suffix}.mp4"
            joints = np.load(JOINTS_2D / f"Ex{ex}" / f"{vid}-{cam}-30fps.npy")
            wanted = {}
            plans = []
            for r in rs:
                a, b = int(r["first_frame"]), int(r["last_frame"])
                idx = [int(round(x)) for x in np.linspace(a, b, FRAMES_PER_REP)]
                plans.append((r, idx))
                for i in idx:
                    wanted[i] = None
            cap = cv2.VideoCapture(str(path))
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            last = max(wanted)
            i = 0
            while i <= last:
                ok = cap.grab()
                if not ok:
                    break
                if i in wanted:
                    wanted[i] = cap.retrieve()[1]
                i += 1
            cap.release()
            for r, idx in plans:
                idx = [min(j, len(joints) - 1) for j in idx]
                if any(wanted.get(j) is None for j in idx):
                    continue
                x, y, bw, bh = crop_box(joints, idx, w, h)
                crops = [letterbox(wanted[j][y:y + bh, x:x + bw], TILE) for j in idx]
                name = f"Ex{ex}_{vid}_{cam}_rep{int(r['repetition_number']):02d}.jpg"
                cv2.imwrite(str(OUT / "images" / name), tile(crops), [cv2.IMWRITE_JPEG_QUALITY, 90])
                person = int(r["person_id"])
                records[split_of(person)].append({
                    "image": f"images/{name}",
                    "exercise": EXERCISES[ex],
                    "correct": r["correctness"] == "1",
                    "view": rep_view(cam, r["cam17_orientation"]),
                    "side": r["exercise_subtype"] or None,
                    "person": person, "video": vid, "camera": cam, "rep": int(r["repetition_number"]),
                })
        print(f"Ex{ex} {vid} done", flush=True)

    for split, rows in records.items():
        with open(OUT / f"{split}.jsonl", "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        n_bad = sum(not r["correct"] for r in rows)
        print(f"{split}: {len(rows)} examples ({n_bad} incorrect), people {sorted({r['person'] for r in rows})}")


if __name__ == "__main__":
    main()
