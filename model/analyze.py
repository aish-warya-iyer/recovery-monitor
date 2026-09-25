"""analyze_video(): one video in, one AnalysisResult out (docs/API_CONTRACT.md). Issues #10, #9, #27.

    from model.analyze import analyze_video
    result = analyze_video("squat.mp4", "squat", {"target_reps": 10, "target_depth_deg": 95},
                           annotated_path="squat_annotated.mp4")

Everything runs locally: MediaPipe pose on the CPU, rules + XGBoost on the rep features.
"""

import json
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

from model.config import ARTIFACTS, POSE_MODELS
from model.extract_landmarks import pose_video
from model.features import (MIN_BASELINE_REPS, SIDES, Series, _points, add_relative, compute_series,
                            rep_features, segment_reps)

POSE_VARIANT = "full"
DEFAULT_PROTOCOL = {"target_reps": 10, "target_depth_deg": 100, "pain_threshold": 5}

# Rule thresholds, from how CORRECT reps behave in REHAB24-6 squats (model/results/squat_rep_features.csv):
TRUNK_LEAN_MAX_DEG = 45.0   # ~95th percentile of correct reps
MIN_DESCENT_S = 0.9         # ~5th percentile of correct reps
JERK_SMOOTH, JERK_ROUGH = 2650.0, 21200.0  # 5th / 95th percentile of correct reps -> smoothness 1 / 0

# Quality gate
MIN_PERSON_FRACTION = 0.8
MIN_LEG_FRACTION = 0.7
MIN_BRIGHTNESS = 0.12
VIEW_SIDE_MAX, VIEW_FRONT_MIN = 0.22, 0.60   # shoulder width / torso length, validated per rep on REHAB24-6
# Measured knee-angle error vs motion capture by view (model/results/angle_accuracy_squat.json, per-frame MAE)
ANGLE_ERROR_DEG = {"side": 5.3, "half_profile": 25.7, "front": 41.8}

# How to phrase each session-relative feature when the model flags a rep (#27).
# base feature -> (what it measures, unit, message when higher than usual, message when lower than usual)
REASONS = {
    "min_knee_angle": ("depth", "degrees", "Shallower than your usual rep", "Deeper than your usual rep"),
    "knee_rom": ("range of motion", "degrees", "Larger knee range than usual", "Smaller knee range than usual"),
    "trunk_lean_max": ("trunk lean", "degrees", "Leaned forward more than usual", "Leaned forward less than usual"),
    "trunk_lean_bottom": ("trunk lean at the bottom", "degrees", "More forward lean at the bottom than usual", "Less forward lean at the bottom than usual"),
    "knee_travel_max": ("knee travel", "shin lengths", "Knee travelled further forward than usual", "Knee travelled less than usual"),
    "peak_descent_speed": ("descent speed", "deg/s", "Went down faster than usual", "Went down slower than usual"),
    "peak_ascent_speed": ("ascent speed", "deg/s", "Came up faster than usual", "Came up slower than usual"),
    "duration_s": ("rep duration", "s", "Rep took longer than usual", "Rep was quicker than usual"),
    "descent_s": ("descent time", "s", "Slower way down than usual", "Faster way down than usual"),
    "ascent_s": ("ascent time", "s", "Slower way up than usual", "Faster way up than usual"),
    "jerk_rms": ("smoothness", "", "Less smooth than usual", "Smoother than usual"),
    "bottom_pause_s": ("pause at the bottom", "s", "Paused longer at the bottom", "Shorter pause at the bottom"),
    "min_hip_angle": ("hip bend", "degrees", "Less hip bend than usual", "More hip bend than usual"),
    "hip_rom": ("hip range", "degrees", "Larger hip range than usual", "Smaller hip range than usual"),
    "hip_knee_ratio": ("hip vs knee movement", "", "Moved more from the hips than usual", "Moved more from the knees than usual"),
    "start_knee_angle": ("starting position", "degrees", "Started straighter than usual", "Started more bent than usual"),
    "end_knee_angle": ("finishing position", "degrees", "Finished straighter than usual", "Did not stand fully up"),
    "descent_ascent_ratio": ("down/up timing", "", "Spent longer going down than up", "Spent longer coming up than down"),
    "asymmetry_bottom": ("left/right difference", "degrees", "Legs more uneven than usual", "Legs more even than usual"),
}


# Features that describe the same thing to a person; only the strongest of each group is phrased.
CONCEPT = {"descent_s": "down_speed", "peak_descent_speed": "down_speed", "ascent_s": "up_speed",
           "peak_ascent_speed": "up_speed", "trunk_lean_max": "lean", "trunk_lean_bottom": "lean",
           "min_knee_angle": "depth", "knee_rom": "depth", "min_hip_angle": "hip", "hip_rom": "hip"}
MIN_CHANGE = {"degrees": 5.0, "s": 0.3, "deg/s": 30.0, "shin lengths": 0.08}


@lru_cache
def _classifier():
    import xgboost as xgb

    meta = json.loads((ARTIFACTS / "squat_xgb_meta.json").read_text())
    model = xgb.Booster()
    model.load_model(str(ARTIFACTS / "squat_xgb.json"))
    return model, meta


def _num(x, nd=1):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def detect_view(image, width, height) -> tuple[str, float | None]:
    P = lambda i: _points(image, i, width, height)  # noqa: E731
    shoulders = np.abs(P(11)[:, 0] - P(12)[:, 0])
    torso = np.linalg.norm((P(11) + P(12)) / 2 - (P(23) + P(24)) / 2, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = float(np.nanmedian(shoulders / torso)) if np.isfinite(torso).any() else float("nan")
    if math.isnan(ratio):
        return "unknown", None
    view = "side" if ratio < VIEW_SIDE_MAX else "front" if ratio > VIEW_FRONT_MIN else "half_profile"
    return view, ratio


def quality_check(lm: dict, s: Series, n_reps: int) -> dict:
    """Checks + plain re-record instructions (#9). Rejects only what makes the numbers meaningless."""
    image = lm["image"]
    person = float(np.mean(~np.isnan(image[:, 0, 0]))) if len(image) else 0.0
    legs = float(np.mean(s.tracked)) if len(s.tracked) else 0.0
    bright = float(np.nanmean(lm["brightness"])) if len(lm["brightness"]) else 0.0
    view, ratio = detect_view(image, int(lm["width"]), int(lm["height"]))
    checks = [
        ("person_visible", person >= MIN_PERSON_FRACTION, person,
         "Make sure your whole body stays in the frame for the entire video."),
        ("legs_visible", legs >= MIN_LEG_FRACTION, legs,
         "Step back so your hips, knees and feet are visible the whole time."),
        ("lighting", bright >= MIN_BRIGHTNESS, bright, "Add more light or face a window."),
        ("camera_view", view == "side", ratio,
         "Stand side-on to the camera so your knee bend is visible; angle measurements are only accurate "
         "from the side."),
        ("full_rep", n_reps >= 1, n_reps, "We could not see a complete squat. Record at least one full rep."),
    ]
    hard = {"person_visible", "legs_visible", "lighting", "full_rep"}  # wrong view -> caveat/uncertain, not rejected
    return {
        "passed": all(ok for name, ok, _, _ in checks if name in hard),
        "view": view,
        "checks": [{"name": n, "passed": bool(ok), "value": _num(v, 2), "message": None if ok else msg}
                   for n, ok, v, msg in checks],
        "instructions": [msg for _, ok, _, msg in checks if not ok],
    }


def _model_scores(feats: list[dict], baseline: list[dict] | None):
    """Returns (probabilities, per-rep top reasons), or (None, None) without an approved baseline."""
    if not feats or not baseline or len(baseline) < MIN_BASELINE_REPS:
        return None, None
    import xgboost as xgb

    model, meta = _classifier()
    rel = add_relative(feats, baseline)
    # A reason is only worth saying if the change exceeds both the patient's normal rep-to-rep spread
    # and a minimum a person would notice (5 degrees, 0.3 s, ...).
    spread = {b: max(float(np.nanstd([x[b] for x in baseline], ddof=1)), MIN_CHANGE.get(REASONS[b][1], 0.0))
              for b in REASONS}
    X = np.array([[r[f] for f in meta["features"]] for r in rel], dtype=np.float32)
    dm = xgb.DMatrix(X, feature_names=meta["features"])
    prob = model.predict(dm)
    contrib = model.predict(dm, pred_contribs=True)[:, :-1]  # last column is the bias
    reasons = []
    for r, c in zip(rel, contrib):
        by_base = {}
        for f, v in zip(meta["features"], c):
            base = f.removesuffix("_rel")
            by_base[base] = by_base.get(base, 0.0) + float(v)
        top, seen = [], set()
        for b, v in sorted(by_base.items(), key=lambda x: -x[1]):
            concept = CONCEPT.get(b, b)
            if v > 0 and b in REASONS and concept not in seen and abs(r[b + "_rel"]) > max(spread[b], 1e-6):
                top.append(b)
                seen.add(concept)
            if len(top) == 2:
                break
        out = []
        for b in top:
            what, unit, more, less = REASONS[b]
            out.append({"code": "model_incorrect", "message": more if r[b + "_rel"] > 0 else less,
                        "value": _num(r[b], 2), "unit": unit or None, "feature": b})
        reasons.append(out)
    return prob, reasons


def analyze_landmarks(lm: dict, exercise: str = "squat", protocol: dict | None = None,
                      baseline: list[dict] | None = None) -> dict:
    """Everything after pose estimation. Split out so tests and evaluation can reuse landmarks.

    baseline: per-rep feature dicts (reps[].features) from the patient's physio-approved reps. With
    fewer than MIN_BASELINE_REPS, correctness is judged by rules only."""
    if exercise != "squat":
        raise ValueError(f"exercise {exercise!r} is not supported by the model pipeline")
    protocol = {**DEFAULT_PROTOCOL, **(protocol or {})}
    fps = float(lm["fps"])
    s = compute_series(lm["image"], int(lm["width"]), int(lm["height"]), fps)
    reps = segment_reps(s.knee, fps)
    feats = [rep_features(s, r) for r in reps]
    quality = quality_check(lm, s, len(reps))
    prob, model_reasons = _model_scores(feats, baseline)
    _, meta = _classifier()
    threshold = meta["threshold"]

    rep_out, evidence = [], []
    target_depth = float(protocol["target_depth_deg"])
    for i, (r, f) in enumerate(zip(reps, feats)):
        reasons = []
        if f["min_knee_angle"] > target_depth:
            reasons.append({"code": "shallow_depth", "value": _num(f["min_knee_angle"]), "unit": "degrees",
                            "message": f"Did not reach the target depth ({f['min_knee_angle']:.0f}° vs target {target_depth:.0f}°)"})
        if f["trunk_lean_max"] > TRUNK_LEAN_MAX_DEG:
            reasons.append({"code": "trunk_lean", "value": _num(f["trunk_lean_max"]), "unit": "degrees",
                            "message": f"Leaned forward {f['trunk_lean_max']:.0f}° (limit {TRUNK_LEAN_MAX_DEG:.0f}°)"})
        if f["descent_s"] < MIN_DESCENT_S:
            reasons.append({"code": "too_fast", "value": _num(f["descent_s"], 2), "unit": "s",
                            "message": f"Went down in {f['descent_s']:.1f} s; aim for a slower, controlled descent"})
        if f["tracked_fraction"] < 0.8:
            reasons.append({"code": "low_tracking", "value": _num(f["tracked_fraction"], 2), "unit": None,
                            "message": "Legs were hard to see during this rep; numbers are less reliable"})
        p = float(prob[i]) if prob is not None else None
        model_flag = p is not None and p >= threshold
        if model_flag:
            reasons = model_reasons[i] + reasons
        # The classifier decides when there is an approved baseline to compare against. Rule findings
        # (depth, lean, speed) stay visible to the physio as notes. Without a baseline the rules decide.
        if p is not None:
            predicted_correct = not model_flag
        else:
            predicted_correct = not any(x["code"] in ("trunk_lean", "too_fast") for x in reasons)
        rep_out.append({
            "index": r.index, "start_frame": r.start, "end_frame": r.end,
            "start_s": round(r.start / fps, 2), "end_s": round(r.end / fps, 2),
            "min_knee_angle_deg": _num(f["min_knee_angle"]),
            "depth_reached": f["min_knee_angle"] <= target_depth,
            "duration_s": _num(f["duration_s"], 2), "descent_s": _num(f["descent_s"], 2), "ascent_s": _num(f["ascent_s"], 2),
            "trunk_lean_max_deg": _num(f["trunk_lean_max"]),
            "predicted_correct": predicted_correct,
            "probability_incorrect": _num(p, 3),
            "flag_reasons": reasons,
            "features": {k: _num(v, 4) for k, v in f.items()},  # raw per-rep features; future baselines
        })
        for x in reasons[:1]:
            evidence.append({"repetition": r.index, "observation": x["message"], "value": x["value"],
                             "unit": x["unit"]})

    n = len(reps)
    n_correct = sum(r["predicted_correct"] for r in rep_out)
    reached = sum(r["depth_reached"] for r in rep_out)
    tracked = s.knee[~np.isnan(s.knee)]
    confidence = float(np.mean(s.tracked)) * min(1.0, s.visibility / 0.9) if len(s.tracked) else 0.0
    if quality["view"] == "front":
        confidence *= 0.7
    jerk = float(np.median([f["jerk_rms"] for f in feats])) if feats else None
    smooth = None if jerk is None else float(np.clip(1 - (jerk - JERK_SMOOTH) / (JERK_ROUGH - JERK_SMOOTH), 0, 1))
    # Demo metric, documented in the contract: mostly "reps without flags", then depth, then tracking.
    form = round(100 * (0.6 * n_correct / n + 0.25 * reached / n + 0.15 * confidence)) if n else 0

    status = "rejected_quality" if not quality["passed"] else "uncertain" if (confidence < 0.6 or quality["view"] == "front") else "complete"
    flagged_reps = [r for r in rep_out if r["flag_reasons"] and not r["predicted_correct"]]
    flag_reasons = []
    if flagged_reps:
        flag_reasons.append(f"{len(flagged_reps)} of {n} reps look different from correct form")
    if not quality["passed"]:
        flag_reasons.append("Video quality too low to analyse reliably")
    elif status == "uncertain":
        flag_reasons.append("Low tracking confidence or unsuitable camera angle")
    if n and reached < n:
        flag_reasons.append(f"{n - reached} of {n} reps did not reach the target depth")
    if n and n < protocol["target_reps"]:
        flag_reasons.append(f"{n} reps done, target was {protocol['target_reps']}")

    observations = []
    if n:
        observations.append(f"Detected {n} squat repetitions; {reached} reached the target depth of {target_depth:.0f}°.")
        if prob is None:
            observations.append("Reps were checked with rules only. Once your physiotherapist approves a session, "
                                "later sessions are compared with your approved form.")
        if flagged_reps:
            observations.append(f"{len(flagged_reps)} reps were flagged for your physiotherapist to review.")
    observations.extend(quality["instructions"])
    observations.append("This is a movement measurement to support your physiotherapist, not a clinical assessment.")

    step = max(1, int(round(fps / 15)))
    tt = np.arange(0, len(s.knee), step)
    return {
        "exercise": exercise,
        "status": status,
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origin": "local_mediapipe_xgboost" if prob is not None else "local_mediapipe_rules",
        "form_score": int(form),
        "repetitions": n,
        "correct_repetitions": int(n_correct),
        "range_of_motion_deg": _num(float(tracked.max() - tracked.min())) if len(tracked) else 0.0,
        "movement_smoothness": _num(smooth, 2) if smooth is not None else 0.0,
        "confidence": _num(confidence, 2),
        "observations": observations,
        "evidence": evidence,
        "protocol": protocol,
        "quality": quality,
        "metrics": {
            "side": s.side,
            "min_knee_angle_deg": _num(min((f["min_knee_angle"] for f in feats), default=None)),
            "median_depth_deg": _num(float(np.median([f["min_knee_angle"] for f in feats])) if feats else None),
            "reps_reaching_target": int(reached),
            "expected_angle_error_deg": ANGLE_ERROR_DEG.get(quality["view"]),
            "median_rep_duration_s": _num(float(np.median([f["duration_s"] for f in feats])) if feats else None, 2),
        },
        "reps": rep_out,
        "flag": {"flagged": bool(flag_reasons), "severity": "review" if flag_reasons else "none", "reasons": flag_reasons},
        "angle_series": {
            "fps": round(fps / step, 2),
            "t": [round(i / fps, 3) for i in tt],
            "knee": [_num(s.knee[i]) for i in tt],
            "hip": [_num(s.hip[i]) for i in tt],
        },
        "annotated_video_url": None,
        "model": {"pose_model": f"mediapipe_pose_landmarker_{POSE_VARIANT}",
                  "classifier": meta["version"] if prob is not None else None, "threshold": threshold,
                  "baseline_reps": len(baseline or []) if prob is not None else 0},
    }


def analyze_video(path: str, exercise: str = "squat", protocol: dict | None = None,
                  annotated_path: str | None = None, progress=None, baseline: list[dict] | None = None) -> dict:
    """Pose → reps → features → rules + classifier → AnalysisResult. Optionally renders an annotated MP4.

    progress: optional callable(stage, fraction) with stage in {"pose", "analyze", "render"}."""
    report = progress or (lambda stage, fraction: None)
    lm = pose_video(str(path), str(POSE_MODELS / f"pose_landmarker_{POSE_VARIANT}.task"),
                    progress=lambda f: report("pose", f))
    report("analyze", 0.0)
    result = analyze_landmarks(lm, exercise, protocol, baseline)
    result["processing_s"] = round(float(lm["seconds"]), 2)
    if annotated_path:
        report("render", 0.0)
        render_annotated(str(path), lm, result, annotated_path)
        result["annotated_video_path"] = str(annotated_path)
    return result


# ---------------------------------------------------------------- annotated video

_BONES = [(11, 12), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (27, 31), (24, 26), (26, 28), (28, 32)]


def render_annotated(video_path: str, lm: dict, result: dict, out_path: str, max_width: int = 720) -> None:
    """Skeleton, live knee angle, rep counter, amber border on flagged reps.

    Frames are piped into the ffmpeg bundled with imageio-ffmpeg and encoded as H.264 MP4
    (yuv420p, faststart) so every browser can play and seek it.
    """
    import subprocess

    import cv2
    import imageio_ffmpeg

    cap = cv2.VideoCapture(video_path)
    fps = float(lm["fps"])
    w, h = int(lm["width"]), int(lm["height"])
    scale = min(1.0, max_width / w)
    size = (int(w * scale) // 2 * 2, int(h * scale) // 2 * 2)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    ff = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{size[0]}x{size[1]}", "-r", f"{fps}", "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)],
        stdin=subprocess.PIPE)
    image = lm["image"]
    side = result["metrics"].get("side")
    highlight = SIDES[side][1:4] if result.get("exercise", "squat") == "squat" and side in SIDES else None
    label = result["angle_series"].get("label", "Knee angle").split(" (")[0]
    reps = result["reps"]
    series_t = np.array(result["angle_series"]["t"])
    series_k = result["angle_series"]["knee"]
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or i >= len(image):
                break
            frame = cv2.resize(frame, size)
            pts = image[i]
            if not np.isnan(pts[0, 0]):
                xy = lambda j: (int(pts[j, 0] * size[0]), int(pts[j, 1] * size[1]))  # noqa: E731
                for a, b in _BONES:
                    cv2.line(frame, xy(a), xy(b), (230, 230, 230), 2, cv2.LINE_AA)
                if highlight:
                    hip, knee, ankle = highlight
                    for a, b in ((hip, knee), (knee, ankle)):
                        cv2.line(frame, xy(a), xy(b), (60, 200, 255), 4, cv2.LINE_AA)
                    cv2.circle(frame, xy(knee), 7, (60, 200, 255), -1, cv2.LINE_AA)
            done = sum(r["end_frame"] <= i for r in reps)
            current = next((r for r in reps if r["start_frame"] <= i <= r["end_frame"]), None)
            ang = series_k[int(np.abs(series_t - i / fps).argmin())] if len(series_t) else None
            review = current is not None and not current["predicted_correct"]
            if review:
                cv2.rectangle(frame, (0, 0), (size[0] - 1, size[1] - 1), (0, 170, 255), 10)
            cv2.rectangle(frame, (0, 0), (size[0], 44), (30, 30, 30), -1)
            text = f"Reps {done}/{len(reps)}" + (f"   {label} {ang:.0f} deg" if ang is not None else "")
            cv2.putText(frame, text + ("   REVIEW" if review else ""), (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (255, 255, 255), 2, cv2.LINE_AA)
            ff.stdin.write(frame.tobytes())
            i += 1
    finally:
        cap.release()
        ff.stdin.close()
        ff.wait()
    if ff.returncode:
        raise RuntimeError(f"ffmpeg failed with exit code {ff.returncode}")
