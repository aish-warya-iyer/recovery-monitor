# Analysis API contract (v1)

Status: **proposed** in #1. Once merged, changes are a team decision: open an issue first.

Both lanes build against this:
- **Model lane** delivers `model.analyze.analyze_video(path, exercise, protocol) -> dict` returning `AnalysisResult`.
- **App lane** stores it, serves it, and renders it. Until the real function lands, use
  [`fixtures/analysis_result.json`](../fixtures/analysis_result.json).

Every field the current frontend reads (`repetitions`, `form_score`, `observations`, …) is kept
unchanged, so existing screens keep working. New fields are additive.

## `AnalysisResult`

```jsonc
{
  "session_id": "s-001",
  "exercise": "squat",                 // "squat" (primary, model-backed) | "seated_leg_extension" (rules only)
  "status": "complete",                // "complete" | "uncertain" | "rejected_quality"
  "analyzed_at": "2026-09-24T10:00:00Z",
  "source": "upload",                  // "upload" | "camera" | "demo"
  "origin": "local_mediapipe_xgboost", // which pipeline produced this

  // ---- summary fields the current UI already uses (unchanged meaning) ----
  "form_score": 72,                    // 0-100, demo metric, not clinically validated
  "repetitions": 8,                    // reps detected
  "correct_repetitions": 6,            // reps the model did not flag
  "range_of_motion_deg": 74.5,         // max - min knee angle over the session
  "movement_smoothness": 0.86,         // 0-1
  "confidence": 0.91,                  // 0-1, pose tracking reliability (NOT medical certainty)
  "observations": ["..."],             // short plain-language sentences
  "evidence": [{ "repetition": 3, "observation": "Did not reach target depth", "value": 112.0, "unit": "degrees" }],

  // ---- new ----
  "protocol": { "target_reps": 10, "target_depth_deg": 95, "pain_threshold": 5 },

  "quality": {
    "passed": true,
    "view": "side",                    // "side" | "half_profile" | "front" | "unknown"
    "checks": [
      { "name": "person_visible", "passed": true, "value": 0.98, "message": null },
      { "name": "legs_visible",   "passed": true, "value": 0.91, "message": null },
      { "name": "camera_view",    "passed": true, "value": null, "message": null },
      { "name": "lighting",       "passed": true, "value": 0.42, "message": null },
      { "name": "full_rep",       "passed": true, "value": 8,    "message": null }
    ],
    "instructions": []                 // plain re-record instructions when a check fails,
                                       // e.g. "Turn sideways to the camera"
  },

  "metrics": {
    "side": "left",                    // leg measured (the more visible one)
    "min_knee_angle_deg": 88.1,        // deepest point in the session
    "median_depth_deg": 96.4,          // median of per-rep minimum knee angle
    "reps_reaching_target": 6,
    "median_rep_duration_s": 2.9
  },

  "reps": [
    {
      "index": 1,
      "start_frame": 120, "end_frame": 205,
      "start_s": 4.0, "end_s": 6.83,
      "min_knee_angle_deg": 91.2,
      "depth_reached": true,           // min_knee_angle_deg <= protocol.target_depth_deg
      "duration_s": 2.83, "descent_s": 1.4, "ascent_s": 1.43,
      "trunk_lean_max_deg": 31.0,
      "predicted_correct": true,
      "probability_incorrect": 0.12,   // from the classifier; null when rules-only
      "flag_reasons": []               // [{ "code": "shallow_depth", "message": "...", "value": 112.0, "unit": "degrees" }]
    }
  ],

  "flag": {
    "flagged": true,                   // true => goes to the physio review queue
    "severity": "review",              // "none" | "review" | "urgent"
    "reasons": ["2 reps look incorrect", "Pain 6/10 is above the plan's threshold of 5"]
  },

  "angle_series": {                    // for the chart synced with the video
    "fps": 30,
    "t": [0.0, 0.033],                 // seconds (downsampled to ≤ 15 Hz)
    "knee": [172.1, 171.8],            // degrees, null where not tracked
    "hip": [168.0, 167.5]
  },

  "annotated_video_url": "/api/sessions/s-001/annotated-video",   // null until rendered

  "model": {
    "pose_model": "mediapipe_pose_landmarker_full",
    "classifier": "squat_xgb_v1",      // null for rules-only exercises
    "threshold": 0.35                  // probability_incorrect at/above this => rep flagged
  }
}
```

### Flag codes (`reps[].flag_reasons[].code`)

| code | meaning |
|---|---|
| `shallow_depth` | minimum knee angle above the protocol's target depth |
| `trunk_lean` | torso leaned forward more than the limit |
| `too_fast` | descent or ascent faster than the protocol tempo |
| `asymmetry` | left/right knee angles differ a lot at the bottom |
| `model_incorrect` | classifier probability above threshold (top feature reasons follow as separate entries) |
| `low_tracking` | pose visibility low during this rep; treat numbers with caution |

### Session-level flag rules (backend, #36)
A session is flagged when any of: a rep is flagged · `quality.passed` is false · `confidence` < 0.6 ·
pain ≥ `protocol.pain_threshold` · pain went up vs last session · fewer reps than target.

## Rules
- Units: angles in degrees (180 = straight leg), time in seconds, frames at the video's fps.
- A knee angle is the angle hip–knee–ankle. Smaller = deeper squat.
- `null` means "not measured". The UI shows "—", never a made-up value.
- This is movement evidence for a physiotherapist, not a diagnosis. Keep that wording in the UI.
