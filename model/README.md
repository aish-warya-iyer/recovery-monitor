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
| `features.py` | angles in pixel space, gap filling + Savitzky–Golay smoothing, rep segmentation, per-rep and session-relative features |
| `eval_reps.py` | detected vs ground-truth reps (temporal IoU ≥ 0.3) → `results/rep_counting_squat.json` |
| `train_classifier.py` | XGBoost + rules baseline, 9-fold leave-one-subject-out → `results/classifier_squat.json`, `artifacts/squat_xgb.json` |
| `splits.json` | fixed subject folds every script uses |

## Current results (squats, MediaPipe Pose Landmarker *full*)

Landmark extraction: ~38 frames/s per CPU worker on the Nano (faster than real time); all 18 squat
videos (9 recordings × 2 cameras) in 213 s with 9 workers.

**Rep counting** (390 annotated reps):

| view | precision | recall |
|---|---|---|
| side | 0.92 | 0.97 |
| front | 0.91 | 0.78 |

The side view is much better, which is why the quality gate asks patients to film from the side.
Caveat: the minimum-depth and edge-rep settings were chosen while looking at this data, so these
numbers are slightly optimistic.

**Rep correctness** (341 detected reps, 115 incorrect, leave-one-subject-out):

| | precision (incorrect) | recall (incorrect) | F1 | ROC AUC |
|---|---|---|---|---|
| XGBoost, session-relative features, threshold 0.24 | 0.53 | 0.80 | 0.64 | 0.80 |
| Rules baseline (best single threshold per fold) | 0.38 | 0.70 | 0.49 | — |

Each subject was coached to make *different* mistakes, so absolute features transfer poorly across
people (AUC 0.67). Comparing each rep with the same person's typical rep in the session lifts AUC to
0.80. This needs ≥ 3 reps in a session; below that the app falls back to rules. The feature set was
chosen after comparing three variants on the same folds, so treat 0.80 as slightly optimistic.

These are movement-evidence numbers from healthy volunteers acting out mistakes, not clinical validation.
The threshold favours catching bad reps (80% recall); the physio review absorbs the false alarms.
