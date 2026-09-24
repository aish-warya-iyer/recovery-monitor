"""Loading helpers: landmarks, ground-truth reps and mocap for one REHAB24-6 video."""

import csv
from functools import lru_cache

import numpy as np

from model.config import LANDMARKS, MANIFEST, SEGMENTATION
from model.features import Series, compute_series


@lru_cache
def manifest(exercise: str) -> list[dict]:
    return [r for r in csv.DictReader(open(MANIFEST)) if r["exercise"] == exercise]


@lru_cache
def _segmentation() -> list[dict]:
    return list(csv.DictReader(open(SEGMENTATION), delimiter=";"))


def gt_reps(video_id: str) -> list[dict]:
    return [
        {"rep": int(r["repetition_number"]), "start": int(r["first_frame"]), "end": int(r["last_frame"]),
         "correct": int(r["correctness"]), "subject": int(r["person_id"]), "orientation17": r["cam17_orientation"],
         "lights_on": int(r["lights_on"])}
        for r in _segmentation() if r["video_id"] == video_id
    ]


def load_landmarks(row: dict, variant: str = "full") -> dict:
    return dict(np.load(LANDMARKS / variant / row["exercise"] / f"{row['video_id']}-{row['camera']}.npz"))


def load_series(row: dict, variant: str = "full") -> Series:
    d = load_landmarks(row, variant)
    return compute_series(d["image"], int(d["width"]), int(d["height"]), float(d["fps"]))
