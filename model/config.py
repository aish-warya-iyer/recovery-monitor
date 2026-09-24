"""Paths and constants shared by the model scripts. Data lives outside the repo."""

import os
from pathlib import Path

DATA = Path(os.getenv("RM_DATA", Path.home() / "rm-data"))
REHAB = DATA / "rehab24"
VIDEOS = REHAB / "videos"
JOINTS_3D = REHAB / "3d_joints"
JOINTS_2D = REHAB / "2d_joints"
LANDMARKS = DATA / "landmarks"
POSE_MODELS = DATA / "pose_models"
MANIFEST = DATA / "manifest.csv"
SEGMENTATION = REHAB / "Segmentation.csv"

MODEL_DIR = Path(__file__).resolve().parent
RESULTS = MODEL_DIR / "results"
ARTIFACTS = MODEL_DIR / "artifacts"
SPLITS = MODEL_DIR / "splits.json"

FPS = 30
EXERCISES = {1: "arm_abduction", 2: "arm_vw", 3: "push_ups", 4: "leg_abduction", 5: "leg_lunge", 6: "squat"}
CAMERAS = {"c17": "Camera17", "c18": "Camera18"}

# REHAB24-6 mocap skeleton (joints_names.txt)
MOCAP = {"left_hip": 16, "left_knee": 17, "left_ankle": 18, "right_hip": 21, "right_knee": 22, "right_ankle": 23,
         "left_shoulder": 6, "right_shoulder": 11, "hips": 0, "neck": 3}

POSE_MODEL_URLS = {
    v: f"https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_{v}/float16/latest/pose_landmarker_{v}.task"
    for v in ("lite", "full", "heavy")
}
