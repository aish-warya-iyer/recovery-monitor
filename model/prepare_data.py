"""Unzip REHAB24-6, download pose models, and write the manifest + subject splits (#23).

    python -m model.prepare_data
"""

import csv
import json
import urllib.request
import zipfile
from collections import defaultdict

import cv2

from model.config import (CAMERAS, EXERCISES, JOINTS_2D, JOINTS_3D, MANIFEST, POSE_MODEL_URLS, POSE_MODELS, REHAB,
                          SEGMENTATION, SPLITS, VIDEOS)


def unzip(name, dest):
    if dest.exists() and any(dest.iterdir()):
        return
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(REHAB / name) as z:
        z.extractall(dest)
    print("unzipped", name)


def download_pose_models():
    POSE_MODELS.mkdir(parents=True, exist_ok=True)
    for variant, url in POSE_MODEL_URLS.items():
        path = POSE_MODELS / f"pose_landmarker_{variant}.task"
        if not path.exists():
            urllib.request.urlretrieve(url, path)
            print("downloaded", path.name)


def read_segmentation():
    with open(SEGMENTATION) as f:
        return list(csv.DictReader(f, delimiter=";"))


def video_path(ex, vid, cam):
    suffix = "-transposed" if cam == "c18" else ""
    return VIDEOS / f"Ex{ex}" / f"{vid}-{CAMERAS[cam]}-30fps{suffix}.mp4"


def build_manifest(reps):
    by_video = defaultdict(list)
    for r in reps:
        by_video[(int(r["exercise_id"]), r["video_id"])].append(r)
    rows = []
    for (ex, vid), rs in sorted(by_video.items()):
        r0 = rs[0]
        for cam in CAMERAS:
            path = video_path(ex, vid, cam)
            cap = cv2.VideoCapture(str(path))
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            orient17 = r0["cam17_orientation"]
            orientation = orient17 if cam == "c17" else {"front": "side", "side": "front"}.get(orient17, orient17)
            rows.append({
                "video_id": vid, "exercise_id": ex, "exercise": EXERCISES[ex], "subject": int(r0["person_id"]),
                "camera": cam, "orientation": orientation, "lights_on": int(r0["lights_on"]),
                "extra_person": int(r0[f"extra_person_in_cam{cam[1:]}"]), "n_reps": len(rs),
                "frames": frames, "width": w, "height": h, "exists": path.exists(),
                "video_path": str(path), "mocap_3d": str(JOINTS_3D / f"Ex{ex}" / f"{vid}-30fps.npy"),
            })
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def write_splits(reps):
    """Leave-one-subject-out folds per exercise. Every script reads the same file."""
    splits = {}
    for ex, name in EXERCISES.items():
        subjects = sorted({int(r["person_id"]) for r in reps if int(r["exercise_id"]) == ex})
        splits[name] = {"method": "leave-one-subject-out", "subjects": subjects,
                        "folds": [{"test_subject": s, "train_subjects": [t for t in subjects if t != s]} for s in subjects]}
    SPLITS.write_text(json.dumps(splits, indent=1))


def main():
    for name, dest in (("videos.zip", VIDEOS), ("3d_joints.zip", JOINTS_3D), ("2d_joints.zip", JOINTS_2D)):
        unzip(name, dest)
    download_pose_models()
    reps = read_segmentation()
    rows = build_manifest(reps)
    write_splits(reps)
    missing = [r["video_path"] for r in rows if not r["exists"]]
    print(f"manifest: {len(rows)} video files, {len(missing)} missing -> {MANIFEST}")
    print("splits ->", SPLITS)


if __name__ == "__main__":
    main()
