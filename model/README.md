# Model lane

Pose → joint angles → rep segmentation → per-rep features → correctness classifier, all on the ZGX Nano.

Data (REHAB24-6, CC BY-NC 4.0, Černek et al., SISAP 2024) lives outside the repo in `~/rm-data`
(override with `RM_DATA`). Never commit data.

```bash
python3 -m venv ~/rm-venv && ~/rm-venv/bin/pip install -r model/requirements.txt
~/rm-venv/bin/python -m model.prepare_data                       # unzip, pose models, manifest, splits (#23)
~/rm-venv/bin/python -m model.extract_landmarks --exercise squat  # MediaPipe over all squat videos (#4)
~/rm-venv/bin/python -m model.eval_reps                           # rep-counting accuracy (#6)
~/rm-venv/bin/python -m model.train_classifier                    # XGBoost vs rules, leave-one-subject-out (#8)
~/rm-venv/bin/python -m pytest model/tests
```

| file | what |
|---|---|
| `features.py` | angles in pixel space, gap filling + Savitzky–Golay smoothing, rep segmentation, per-rep and baseline-relative features |
| `eval_reps.py` | detected vs ground-truth reps (temporal IoU ≥ 0.3) → `results/rep_counting_squat.json` |
| `eval_angles.py` | knee angle vs 3D motion capture, per frame and per-rep depth → `results/angle_accuracy_squat.json` |
| `train_classifier.py` | XGBoost + rules baseline, 9-fold leave-one-subject-out → `results/classifier_squat.json`, `artifacts/squat_xgb.json` |
| `splits.json` | fixed subject folds every script uses |

## Current results (squats, MediaPipe Pose Landmarker *full*)

Landmark extraction: ~38 frames/s per CPU worker on the Nano (faster than real time); all 18 squat
videos (9 recordings × 2 cameras) in 213 s with 9 workers.

**Knee-angle accuracy vs motion capture** (the "how precise is it" number; REHAB24-6 3D mocap from 16
optical cameras as ground truth, every frame inside the 390 annotated reps, by each rep's camera view):

| rep view | per-frame error (MAE) | error in rep depth (MAE) |
|---|---|---|
| **side** | **5.3°** | **5.3°** |
| half-profile (≈45°) | 25.7° | 33.8° |
| front | 41.8° | 66.9° |

From the side, the app's 2D knee angle is within ~5° of motion capture, comparable to the variation
between clinicians using a goniometer. Away from the side, a 2D projection distorts the angle; MediaPipe's
own 3D world landmarks do better there (15.7° half-profile, 21.4° front) but worse from the side (9.8°).

**Rep counting** (390 annotated reps; recall by the camera view of each rep; views change within a video):

| rep view | reps | recall |
|---|---|---|
| side | 98 | 0.97 |
| half-profile (≈45°) | 194 | 0.96 |
| front | 98 | 0.61 |

Precision (detected reps that match a labelled rep): 0.91 on camera 17, 0.92 on camera 18. Some
"false" detections are probably real reps the dataset didn't annotate. Caveat: the minimum-depth and
edge-rep settings were chosen while looking at this data, so these numbers are slightly optimistic.

**Rep correctness** (leave-one-subject-out, 9 folds; 287 detected reps, 115 incorrect, after setting
aside each recording's first 3 correct reps as that person's baseline):

| | precision (incorrect) | recall (incorrect) | F1 | ROC AUC |
|---|---|---|---|---|
| XGBoost vs the patient's baseline, threshold 0.17 | 0.53 | 0.80 | 0.64 | 0.70 |
| Rules baseline (best single threshold per fold, same baseline-relative features) | 0.50 | 0.83 | 0.62 | — |

What made the difference is **calibrating to the patient**: each REHAB24-6 subject was coached to make
*different* mistakes, so absolute features transfer poorly across people (AUC 0.67). Each rep is
therefore compared with the same person's physio-approved reps. In the app, the baseline is a session
the physio approved; a patient's first session is judged by rules until one is approved. Once rules get
the same calibrated features, XGBoost is only slightly better than one well-chosen threshold (F1 0.64 vs
0.62); we keep it because it combines several signals and explains each flag.

We also tried comparing each rep with the median rep of its own session (AUC 0.80 on these long
recordings), but it fails on real short sessions where most reps are wrong: the "typical" rep is then
the wrong one. The calibration reps here come from the same recording, which is easier than a baseline
from another day.

By view (same folds): side AUC 0.60 (68 reps) · half-profile AUC 0.71 (180) · front AUC 0.77 (39).

**Recommended camera position: side view.** Counting works from side or half-profile (0.97 / 0.96)
but fails from the front (0.61), and the angle numbers a physio reads are only accurate from the side
(5° vs 26° at half-profile). Some mistakes (knees caving in) show better from the front, which is why the
classifier is slightly stronger there; a second front camera is future work.

These are movement-evidence numbers from healthy volunteers acting out mistakes, not clinical validation.
The threshold favours catching bad reps (80% recall); the physio review absorbs the false alarms.
