"""Full analysis for any of the six exercises: pose -> VLM exercise/view check -> exercise-specific reps +
XGBoost -> per-rep VLM second opinion -> AnalysisResult (docs/API_CONTRACT.md) + annotated video.

    from model.pipeline import run_pipeline
    result = run_pipeline("clip.mp4", planned_exercise="squat", protocol={...}, baseline=[...],
                          annotated_path="annotated.mp4")

The squat keeps its dedicated, validated model (model/analyze.py). The other five use model/exercises.py
signals and their own XGBoost models (model/train_all.py). The fine-tuned VLM runs in the local AI
service (model/ai_service.py); if that service is down, analysis still works without it.
"""

import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from model.analyze import ANGLE_ERROR_DEG, MIN_CHANGE, _num, analyze_landmarks, render_annotated
from model.config import ARTIFACTS, POSE_MODELS
from model.exercises import compute_signals, rep_features_generic
from model.extract_landmarks import pose_video
from model.features import segment_reps
from model.finetune.prepare_vlm_data import FRAMES_PER_REP, TILE, crop_box, letterbox, tile

AI_SERVICE = os.getenv("RM_AI_SERVICE_URL", "http://127.0.0.1:8100")
POSE_VARIANT = "full"

EXERCISE_INFO = {
    # label, what the chart shows, rep value means ("low" = smaller angle is the active end), camera advice
    "squat": ("Squat", "Knee angle", "low", {"side", "half_profile"},
              "Stand side-on to the camera, whole body in frame."),
    "leg_lunge": ("Lunge", "Knee angle (both legs)", "low", {"side", "half_profile"},
                  "Stand side-on to the camera, whole body in frame."),
    "leg_abduction": ("Leg raise to the side", "Leg raise angle", "high", {"front", "half_profile"},
                      "Face the camera so the sideways leg raise is visible, whole body in frame."),
    "arm_abduction": ("Arm raise to the side", "Arm raise angle", "high", {"front"},
                      "Face the camera so the sideways arm raise is visible, upper body and hips in frame."),
    "arm_vw": ("Arm V-W", "Elbow angle", "low", {"front", "half_profile"},
               "Face the camera (or turn slightly), both arms in frame."),
    "push_ups": ("Push-up (hands on table)", "Elbow angle", "low", {"front"},
                 "Set the camera so your arms and body line are visible for the whole movement."),
}
MIN_DEPTH = {"squat": 15, "leg_lunge": 15, "leg_abduction": 10, "arm_abduction": 20, "arm_vw": 20, "push_ups": 15}
MAX_VLM_REPS = 30

# Plain-language reasons for the generic models' features (base name -> (higher msg, lower msg, unit)).
# Primary signals are "high at rest, low when active", so a higher `peak` means a smaller movement.
GENERIC_REASONS = {
    "peak": ("Smaller movement than your approved reps", "Bigger movement than your approved reps", "degrees"),
    "rom": ("Larger range than usual", "Smaller range than usual", "degrees"),
    "down_s": ("Slower into the movement than usual", "Faster into the movement than usual", "s"),
    "up_s": ("Slower on the way back than usual", "Faster on the way back than usual", "s"),
    "peak_down_speed": ("Faster into the movement than usual", "Slower into the movement than usual", "deg/s"),
    "peak_up_speed": ("Faster on the way back than usual", "Slower on the way back than usual", "deg/s"),
    "duration_s": ("Rep took longer than usual", "Rep was quicker than usual", "s"),
    "jerk_rms": ("Less smooth than usual", "Smoother than usual", ""),
    "hold_s": ("Held the end position longer than usual", "Shorter hold at the end position", "s"),
    "trunk_lean_max": ("Body leaned or tilted more than usual", "Body leaned less than usual", "degrees"),
    "asymmetry_max": ("Left and right sides moved more unevenly", "Left and right sides moved more evenly", "degrees"),
    "other_max": ("The other limb moved more than usual", "The other limb moved less than usual", "degrees"),
    "elbow_min": ("Elbow stayed straighter than usual", "Elbow bent more than usual", "degrees"),
    "body_line_min": ("Body line straighter than usual", "Hips sagged or piked more than usual", "degrees"),
    "knee_min": ("Knee stayed straighter than usual", "Knee bent more than usual", "degrees"),
    "shoulder_max": ("Arms went higher than usual", "Arms stayed lower than usual", "degrees"),
}


# ---------------------------------------------------------------- VLM (local AI service)

def vlm_predict(images: list[str]) -> list[dict] | None:
    import httpx

    if not images:
        return []
    try:
        r = httpx.post(f"{AI_SERVICE}/vlm", json={"images": images}, timeout=300)
        r.raise_for_status()
        return r.json()["predictions"]
    except Exception:  # noqa: BLE001 — analysis must still work without the VLM
        return None


def make_tiles(video_path: str, lm: dict, windows: list[tuple[int, int]], out_dir: Path, prefix: str) -> list[str]:
    """One 8-frame tiled crop per (start, end) window, same format the VLM was trained on."""
    w, h = int(lm["width"]), int(lm["height"])
    pts = lm["image"][:, :, :2] * np.array([w, h], np.float32)
    vis = lm["image"][:, :, 3]
    pts = np.where((vis >= 0.3)[..., None], pts, np.nan)
    plans, wanted = [], set()
    for a, b in windows:
        idx = [int(round(x)) for x in np.linspace(a, b, FRAMES_PER_REP)]
        plans.append(idx)
        wanted.update(idx)
    frames, cap, i = {}, cv2.VideoCapture(video_path), 0
    last = max(wanted) if wanted else -1
    while i <= last:
        if not cap.grab():
            break
        if i in wanted:
            frames[i] = cap.retrieve()[1]
        i += 1
    cap.release()
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for k, idx in enumerate(plans):
        idx = [j for j in idx if j in frames and j < len(pts)]
        if len(idx) < FRAMES_PER_REP or not np.isfinite(pts[idx]).any():
            continue
        x, y, bw, bh = crop_box(pts, idx, w, h)
        img = tile([letterbox(frames[j][y:y + bh, x:x + bw], TILE) for j in idx])
        p = out_dir / f"{prefix}_{k:02d}.jpg"
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        paths.append(str(p))
    return paths


def detect_exercise(video_path: str, lm: dict, work_dir: Path) -> dict | None:
    """VLM votes over up to 4 windows of ~3.5 s spread through the video."""
    n = len(lm["image"])
    fps = float(lm["fps"])
    win = min(n - 1, int(3.5 * fps))
    k = max(1, min(4, int(n / max(win, 1))))
    starts = np.linspace(0, max(0, n - 1 - win), k).astype(int)
    paths = make_tiles(video_path, lm, [(s, s + win) for s in starts], work_dir, "window")
    preds = vlm_predict(paths)
    if not preds:
        return None
    ex = Counter(p["exercise"] for p in preds if p["exercise"])
    view = Counter(p["view"] for p in preds if p["view"])
    if not ex:
        return None
    top, votes = ex.most_common(1)[0]
    return {"exercise": top, "confidence": round(votes / len(preds), 2),
            "view": view.most_common(1)[0][0] if view else None, "votes": dict(ex), "windows": len(preds)}


# ---------------------------------------------------------------- generic (non-squat) analysis

@lru_cache
def _model(exercise: str):
    import xgboost as xgb

    meta = json.loads((ARTIFACTS / f"{exercise}_xgb_meta.json").read_text())
    booster = xgb.Booster()
    booster.load_model(str(ARTIFACTS / f"{exercise}_xgb.json"))
    return booster, meta


def display(exercise: str, primary: np.ndarray) -> np.ndarray:
    """What a person reads on the chart: the raise angle for raises, the joint angle otherwise."""
    return 180 - primary if EXERCISE_INFO[exercise][2] == "high" else primary


def score_generic(exercise, feats, baseline):
    if not feats or not baseline or len(baseline) < 3:
        return None, None
    import xgboost as xgb

    booster, meta = _model(exercise)
    bases = [f.removesuffix("_rel") for f in meta["features"]]
    med = {b: float(np.nanmedian([x.get(b, np.nan) for x in baseline])) for b in bases}
    spread = {b: float(np.nanstd([x.get(b, np.nan) for x in baseline], ddof=1)) for b in bases}
    X = np.array([[f.get(b, np.nan) - med[b] for b in bases] for f in feats], dtype=np.float32)
    dm = xgb.DMatrix(X, feature_names=meta["features"])
    prob = booster.predict(dm)
    contrib = booster.predict(dm, pred_contribs=True)[:, :-1]
    reasons = []
    for f, row in zip(feats, contrib):
        out, seen = [], set()
        for j in np.argsort(-row):
            b = bases[j]
            if row[j] <= 0 or b not in GENERIC_REASONS or b.split("_")[0] in seen:
                continue
            more, less, unit = GENERIC_REASONS[b]
            rel = f.get(b, np.nan) - med[b]
            if not np.isfinite(rel) or abs(rel) <= max(spread[b] if np.isfinite(spread[b]) else 0, MIN_CHANGE.get(unit, 0)):
                continue
            out.append({"code": "model_incorrect", "message": more if rel > 0 else less,
                        "value": _num(f.get(b), 2), "unit": unit or None, "feature": b})
            seen.add(b.split("_")[0])
            if len(out) == 2:
                break
        reasons.append(out)
    return prob, reasons, meta["threshold"], meta["version"]


def analyze_generic(lm: dict, exercise: str, protocol: dict, baseline: list | None) -> dict:
    fps = float(lm["fps"])
    sig = compute_signals(exercise, lm["image"], int(lm["width"]), int(lm["height"]), fps)
    reps = segment_reps(sig.primary, fps, min_depth_deg=MIN_DEPTH[exercise])
    feats = [rep_features_generic(sig, r) for r in reps]
    scored = score_generic(exercise, feats, baseline)
    prob, model_reasons, threshold, version = scored if scored[0] is not None else (None, None, None, None)
    disp = display(exercise, sig.primary)
    high = EXERCISE_INFO[exercise][2] == "high"

    rep_out = []
    for i, (r, f) in enumerate(zip(reps, feats)):
        seg = disp[r.start:r.end + 1]
        peak = float(np.nanmax(seg) if high else np.nanmin(seg))
        p = float(prob[i]) if prob is not None else None
        reasons = list(model_reasons[i]) if (p is not None and p >= threshold) else []
        if f["tracked_fraction"] < 0.8:
            reasons.append({"code": "low_tracking", "value": _num(f["tracked_fraction"], 2), "unit": None,
                            "message": "Body was hard to see during this rep; numbers are less reliable"})
        rep_out.append({
            "index": r.index, "start_frame": r.start, "end_frame": r.end,
            "start_s": round(r.start / fps, 2), "end_s": round(r.end / fps, 2),
            "peak_deg": _num(peak), "min_knee_angle_deg": _num(peak), "depth_reached": None,
            "range_deg": _num(f["rom"]), "duration_s": _num(f["duration_s"], 2),
            "descent_s": _num(f["down_s"], 2), "ascent_s": _num(f["up_s"], 2),
            "predicted_correct": (p < threshold) if p is not None else True,
            "probability_incorrect": _num(p, 3), "flag_reasons": reasons,
            "features": {k: _num(v, 4) for k, v in f.items()},
        })
    step = max(1, int(round(fps / 15)))
    tt = np.arange(0, len(disp), step)
    tracked = disp[np.isfinite(disp)]
    return {
        "exercise": exercise, "reps": rep_out,
        "metrics": {"side": sig.side, "peak_deg": _num(max((r["peak_deg"] for r in rep_out), default=None)
                                                        if high else min((r["peak_deg"] for r in rep_out), default=None)),
                    "median_range_deg": _num(float(np.median([f["rom"] for f in feats])) if feats else None),
                    "median_rep_duration_s": _num(float(np.median([f["duration_s"] for f in feats])) if feats else None, 2),
                    "reps_reaching_target": None, "expected_angle_error_deg": None,
                    "min_knee_angle_deg": None, "median_depth_deg": None},
        "angle_series": {"fps": round(fps / step, 2), "t": [round(i / fps, 3) for i in tt],
                         "knee": [_num(disp[i]) for i in tt], "label": EXERCISE_INFO[exercise][1],
                         "higher_is_active": high},
        "range_of_motion_deg": _num(float(tracked.max() - tracked.min())) if len(tracked) else 0.0,
        "confidence": _num(float(np.mean(sig.tracked)) * min(1.0, sig.visibility / 0.9), 2),
        "tracked_fraction": float(np.mean(sig.tracked)),
        "brightness": float(np.nanmean(lm["brightness"])) if len(lm["brightness"]) else 0.0,
        "person_fraction": float(np.mean(~np.isnan(lm["image"][:, 0, 0]))) if len(lm["image"]) else 0.0,
        "model": {"pose_model": f"mediapipe_pose_landmarker_{POSE_VARIANT}", "classifier": version,
                  "threshold": threshold, "baseline_reps": len(baseline or []) if prob is not None else 0},
    }


# ---------------------------------------------------------------- orchestration

def _generic_result(core: dict, protocol: dict) -> dict:
    """Wrap the generic analysis in the full AnalysisResult shape (quality, flags, summary fields)."""
    ex = core["exercise"]
    reps = core["reps"]
    n = len(reps)
    checks = [
        ("person_visible", core["person_fraction"] >= 0.8, core["person_fraction"],
         "Make sure your whole body stays in the frame for the entire video."),
        ("body_visible", core["tracked_fraction"] >= 0.7, core["tracked_fraction"],
         "Step back so the joints used in this exercise are visible the whole time."),
        ("lighting", core["brightness"] >= 0.12, core["brightness"], "Add more light or face a window."),
        ("full_rep", n >= 1, n, "We could not see a complete repetition. Record at least one full rep."),
    ]
    quality = {"passed": all(ok for _, ok, _, _ in checks), "view": None,
               "checks": [{"name": c, "passed": bool(ok), "value": _num(v, 2), "message": None if ok else m}
                          for c, ok, v, m in checks],
               "instructions": [m for _, ok, _, m in checks if not ok]}
    n_correct = sum(r["predicted_correct"] for r in reps)
    conf = core["confidence"] or 0.0
    return {
        "exercise": ex, "status": "complete" if quality["passed"] else "rejected_quality",
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origin": "local_mediapipe_xgboost" if core["model"]["classifier"] else "local_mediapipe_vlm",
        "form_score": round(100 * (0.7 * n_correct / n + 0.3 * conf)) if n else 0,
        "repetitions": n, "correct_repetitions": n_correct,
        "range_of_motion_deg": core["range_of_motion_deg"], "movement_smoothness": None, "confidence": conf,
        "observations": [], "evidence": [], "protocol": protocol, "quality": quality,
        "metrics": core["metrics"], "reps": reps, "angle_series": core["angle_series"],
        "annotated_video_url": None, "model": core["model"],
    }


def finalize(result: dict, protocol: dict, vlm_info: dict | None, planned: str | None):
    """Add VLM facts, camera advice, flags and plain-language observations (all exercises)."""
    ex = result["exercise"]
    label, measure, _, good_views, advice = EXERCISE_INFO[ex]
    reps = result["reps"]
    n = len(reps)
    view = (vlm_info or {}).get("view") or result.get("quality", {}).get("view")
    result["quality"]["view"] = view
    view_ok = view in good_views if view else True
    result["quality"]["checks"] = [c for c in result["quality"]["checks"] if c["name"] != "camera_view"] + [
        {"name": "camera_view", "passed": view_ok, "value": view, "message": None if view_ok else advice}]
    result["quality"]["instructions"] = [c["message"] for c in result["quality"]["checks"] if not c["passed"]]
    # Angle error vs motion capture was only measured for squats; use the VLM's view (98% accurate).
    result["metrics"]["expected_angle_error_deg"] = ANGLE_ERROR_DEG.get(view) if ex == "squat" else None
    mismatch = bool(vlm_info and planned and vlm_info["exercise"] != planned and vlm_info["confidence"] >= 0.75)
    result["vlm"] = {"available": vlm_info is not None, "planned_exercise": planned,
                     "detected_exercise": (vlm_info or {}).get("exercise"), "confidence": (vlm_info or {}).get("confidence"),
                     "view": view, "votes": (vlm_info or {}).get("votes"), "mismatch": mismatch,
                     "model": "Qwen3-VL-4B + LoRA fine-tuned on REHAB24-6"}
    result["exercise_label"] = label
    result["measure_label"] = measure

    flagged = [r for r in reps if not r["predicted_correct"]]
    reasons = []
    if mismatch:
        reasons.append(f"Video looks like {EXERCISE_INFO[vlm_info['exercise']][0].lower()}, "
                       f"but the plan is {EXERCISE_INFO[planned][0].lower()}")
    if flagged:
        reasons.append(f"{len(flagged)} of {n} reps look different from correct form")
    if not result["quality"]["passed"]:
        reasons.append("Video quality too low to analyse reliably")
    elif not view_ok:
        reasons.append(f"Camera angle ({(view or 'unknown').replace('_', ' ')}) is not ideal for this exercise")
    target = (protocol or {}).get("target_reps")
    if n and target and n < target:
        reasons.append(f"{n} reps done, target was {target}")
    if ex == "squat":
        reached = result["metrics"].get("reps_reaching_target") or 0
        if n and reached < n:
            reasons.append(f"{n - reached} of {n} reps did not reach the target depth")
    result["flag"] = {"flagged": bool(reasons), "severity": "review" if reasons else "none", "reasons": reasons}
    if result["status"] == "complete" and (not view_ok or (result.get("confidence") or 0) < 0.6):
        result["status"] = "uncertain"

    obs = []
    if mismatch:
        obs.append(f"This looks like {EXERCISE_INFO[vlm_info['exercise']][0].lower()}, not "
                   f"{EXERCISE_INFO[planned][0].lower()} from your plan. It was analysed as what we saw; "
                   "your physiotherapist will check.")
    if n:
        obs.append(f"Detected {n} {label.lower()} repetitions.")
        if result["model"].get("classifier") is None:
            obs.append("Form was checked without a personal baseline yet. Once your physiotherapist approves "
                       "a session, later sessions are compared with your approved form.")
        if flagged:
            obs.append(f"{len(flagged)} reps were flagged for your physiotherapist to review.")
    obs.extend(result["quality"]["instructions"])
    obs.append("This is a movement measurement to support your physiotherapist, not a clinical assessment.")
    result["observations"] = obs
    result["evidence"] = [{"repetition": r["index"], "observation": r["flag_reasons"][0]["message"],
                           "value": r["flag_reasons"][0].get("value"), "unit": r["flag_reasons"][0].get("unit")}
                          for r in reps if r["flag_reasons"]][:10]
    return result


def run_pipeline(video_path: str, planned_exercise: str | None = "squat", protocol: dict | None = None,
                 baseline: list | None = None, annotated_path: str | None = None, progress=None,
                 work_dir: str | None = None) -> dict:
    report = progress or (lambda stage, fraction: None)
    protocol = protocol or {}
    work = Path(work_dir or Path(video_path).parent) / "vlm"
    lm = pose_video(str(video_path), str(POSE_MODELS / f"pose_landmarker_{POSE_VARIANT}.task"),
                    progress=lambda f: report("pose", f))
    report("analyze", 0.0)
    vlm_info = detect_exercise(str(video_path), lm, work)
    exercise = planned_exercise or "squat"
    if vlm_info and vlm_info["confidence"] >= 0.75 and vlm_info["exercise"] != exercise:
        exercise = vlm_info["exercise"]  # analyse what was actually done; the mismatch is flagged

    if exercise == "squat":
        result = analyze_landmarks(lm, "squat", protocol, baseline)
        result["angle_series"]["label"] = "Knee angle"
        result["angle_series"]["higher_is_active"] = False
        for r in result["reps"]:
            r["peak_deg"] = r["min_knee_angle_deg"]
    else:
        result = _generic_result(analyze_generic(lm, exercise, protocol, baseline), protocol)
    report("analyze", 0.5)

    # Per-rep second opinion from the fine-tuned VLM; stands in for correctness when there is no baseline.
    reps = result["reps"][:MAX_VLM_REPS]
    preds = vlm_predict(make_tiles(str(video_path), lm, [(r["start_frame"], r["end_frame"]) for r in reps], work, "rep"))
    for r, p in zip(reps, preds or []):
        r["vlm"] = {"correct": p["correct"], "exercise": p["exercise"]}
        if result["model"].get("classifier") is None and p["correct"] is False and exercise != "squat":
            r["predicted_correct"] = False
            r["flag_reasons"].insert(0, {"code": "vlm_incorrect", "value": None, "unit": None,
                                         "message": "Our video model thinks this rep looks off (no personal baseline yet)"})
    result["correct_repetitions"] = sum(r["predicted_correct"] for r in result["reps"])
    result = finalize(result, protocol, vlm_info, planned_exercise)
    result["processing_s"] = round(float(lm["seconds"]), 2)
    if annotated_path:
        report("render", 0.0)
        render_annotated(str(video_path), lm, result, annotated_path)
    return result
