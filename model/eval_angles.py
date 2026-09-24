"""Knee-angle accuracy against motion capture (#7): how precise is the video measurement?

    python -m model.eval_angles --exercise squat

Ground truth: the knee angle (hip-knee-ankle) from REHAB24-6's 3D mocap skeleton, which is
measured with 16 optical cameras and is independent of the video.
Compared, frame by frame inside annotated reps, for the same leg:
  - image_2d:  our app's angle (MediaPipe image landmarks, pixel space, smoothed)
  - world_3d:  MediaPipe's own 3D world landmarks (for reference)
Also the error in each rep's deepest point (the number a physio reads as "depth").
Errors are split by the camera view of each rep.
"""

import argparse
import json
from collections import defaultdict

import numpy as np

from model.config import MOCAP, RESULTS
from model.data import gt_reps, load_landmarks, manifest, rep_view
from model.features import SIDES, angle_at, compute_series, fill_and_smooth


def angle3(a, b, c):
    v1, v2 = a - b, c - b
    cos = np.einsum("ij,ij->i", v1, v2) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1))
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def best_offset(pred, truth, max_lag=3):
    """Frame offset between video and mocap that minimises the error (they differ by one frame)."""
    best = (np.inf, 0)
    for lag in range(-max_lag, max_lag + 1):
        a = pred[max(0, lag): len(pred) + min(0, lag)]
        b = truth[max(0, -lag): len(truth) + min(0, -lag)][: len(a)]
        a = a[: len(b)]
        ok = ~np.isnan(a) & ~np.isnan(b)
        if ok.sum() > 100:
            best = min(best, (float(np.mean(np.abs(a[ok] - b[ok]))), lag))
    return best[1]


def shift(x, lag, n):
    out = np.full(n, np.nan)
    src = x[max(0, lag):]
    dst0 = max(0, -lag)
    k = min(len(src), n - dst0)
    out[dst0: dst0 + k] = src[:k]
    return out


def summarize(err):
    e = np.abs(np.asarray(err, dtype=float))
    e = e[~np.isnan(e)]
    if not len(e):
        return None
    return {"n": int(len(e)), "mae_deg": round(float(e.mean()), 1), "median_deg": round(float(np.median(e)), 1),
            "p95_deg": round(float(np.percentile(e, 95)), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", default="squat")
    ap.add_argument("--variant", default="full")
    args = ap.parse_args()

    frame_err = defaultdict(lambda: defaultdict(list))   # method -> view -> errors
    depth_err = defaultdict(lambda: defaultdict(list))
    example = None
    for row in manifest(args.exercise):
        lm = load_landmarks(row, args.variant)
        fps = float(lm["fps"])
        s = compute_series(lm["image"], int(lm["width"]), int(lm["height"]), fps)
        side = s.side
        mocap = np.load(row["mocap_3d"])[:, :, :3]
        truth = angle3(mocap[:, MOCAP[f"{side}_hip"]], mocap[:, MOCAP[f"{side}_knee"]], mocap[:, MOCAP[f"{side}_ankle"]])
        _, hp, kn, an, _ = SIDES[side]
        world = lm["world"]
        w3 = fill_and_smooth(angle3(world[:, hp], world[:, kn], world[:, an]), fps)
        n = len(s.knee)
        lag = best_offset(s.knee, truth)
        truth = shift(truth, lag, n)
        methods = {"image_2d": s.knee, "world_3d": w3}
        for g in gt_reps(row["video_id"]):
            view = rep_view(row["camera"], g["orientation17"])
            sl = slice(g["start"], min(g["end"] + 1, n))
            t = truth[sl]
            for name, pred in methods.items():
                p = pred[sl]
                frame_err[name][view].extend((p - t).tolist())
                frame_err[name]["all"].extend((p - t).tolist())
                if np.isfinite(p).any() and np.isfinite(t).any():
                    d = float(np.nanmin(p) - np.nanmin(t))
                    depth_err[name][view].append(d)
                    depth_err[name]["all"].append(d)
        if example is None and row["camera"] == "c18":
            g = gt_reps(row["video_id"])[5]
            sl = slice(g["start"], g["end"] + 1)
            example = {"video": f"{row['video_id']}-{row['camera']}", "rep": g["rep"], "fps": fps,
                       "mocap": np.round(truth[sl], 1).tolist(), "image_2d": np.round(s.knee[sl], 1).tolist(),
                       "world_3d": np.round(w3[sl], 1).tolist()}
        print(f"{row['video_id']}-{row['camera']} side={side} lag={lag:+d} "
              f"MAE 2D={summarize([x for x in (s.knee - truth) if np.isfinite(x)])['mae_deg']}")

    views = ("all", "side", "half_profile", "front")
    out = {
        "exercise": args.exercise,
        "ground_truth": "REHAB24-6 3D motion capture (OptiTrack, 16 cameras), knee angle hip-knee-ankle",
        "frames": "all frames inside annotated reps; video and mocap aligned by the best offset (±3 frames)",
        "per_frame_error": {m: {v: summarize(frame_err[m][v]) for v in views} for m in frame_err},
        "rep_depth_error": {m: {v: summarize(depth_err[m][v]) | {"mean_signed_deg": round(float(np.nanmean(depth_err[m][v])), 1)}
                                for v in views} for m in depth_err},
        "example_rep": example,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"angle_accuracy_{args.exercise}.json").write_text(json.dumps(out, indent=1))
    for m in out["per_frame_error"]:
        print(m, "per-frame", {v: (x or {}).get("mae_deg") for v, x in out["per_frame_error"][m].items()},
              "| depth", {v: (x or {}).get("mae_deg") for v, x in out["rep_depth_error"][m].items()})


if __name__ == "__main__":
    main()
