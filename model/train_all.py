"""Rep counting + rep-correctness XGBoost for every REHAB24-6 exercise.

    ~/rm-venv/bin/python -m model.train_all                     # all six
    ~/rm-venv/bin/python -m model.train_all --exercise leg_lunge

Same method as the squat model (model/train_classifier.py), generalised through model/exercises.py:
- reps: dips in the exercise's primary signal, matched to ground-truth reps (temporal IoU >= 0.3)
- features: per rep, minus the median of the person's baseline (the recording's first 3 correct reps,
  which are then excluded from training and testing), like a physio-approved baseline in the app
- evaluation: leave-one-subject-out; rules baseline = best single threshold per fold on the same features
Writes model/artifacts/<exercise>_xgb.json (+ _meta.json; the squat's generic model is squat_generic_xgb
so it never replaces the app's dedicated squat model) and model/results/exercise_<exercise>.json.
"""

import argparse
import json

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

from model.config import ARTIFACTS, EXERCISES, RESULTS
from model.data import gt_reps, load_landmarks, manifest, rep_view
from model.eval_reps import match
from model.exercises import compute_signals, rep_features_generic
from model.features import segment_reps

BASELINE_REPS = 3
TARGET_RECALL = 0.80
XGB_PARAMS = dict(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                  min_child_weight=3, reg_lambda=1.0, eval_metric="logloss", random_state=0)
MIN_DEPTH = {"squat": 15, "leg_lunge": 15, "leg_abduction": 10, "arm_abduction": 20, "arm_vw": 20, "push_ups": 15}


def collect(exercise):
    rows, counting = [], {"gt": 0, "det": 0, "matched": 0, "by_view": {}}
    for row in manifest(exercise):
        lm = load_landmarks(row)
        sig = compute_signals(exercise, lm["image"], int(lm["width"]), int(lm["height"]), float(lm["fps"]))
        det = segment_reps(sig.primary, sig.fps, min_depth_deg=MIN_DEPTH[exercise])
        gt = gt_reps(row["video_id"])
        pairs = sorted(match(det, gt), key=lambda x: det[x[0]].start)
        counting["gt"] += len(gt)
        counting["det"] += len(det)
        counting["matched"] += len(pairs)
        hit = {j for _, j, _ in pairs}
        for j, g in enumerate(gt):
            v = counting["by_view"].setdefault(rep_view(row["camera"], g["orientation17"]), [0, 0])
            v[0] += j in hit
            v[1] += 1
        feats = [rep_features_generic(sig, d) for d in det]
        base_idx = [i for i, j, _ in pairs if gt[j]["correct"]][:BASELINE_REPS]
        if len(base_idx) < BASELINE_REPS:
            continue
        keys = [k for k in feats[0] if k != "tracked_fraction"]
        med = {k: np.nanmedian([feats[i][k] for i in base_idx]) for k in keys}
        for i, j, v in pairs:
            if i in base_idx:
                continue
            f = {**feats[i], **{k + "_rel": feats[i][k] - med[k] for k in keys}}
            f.update(subject=gt[j]["subject"], incorrect=1 - gt[j]["correct"], video=row["video_id"],
                     camera=row["camera"], view=rep_view(row["camera"], gt[j]["orientation17"]))
            rows.append(f)
    return pd.DataFrame(rows), counting


def rule_fold(train, cols):
    best = (0.0, cols[0], 0.0, 1)
    for c in cols:
        x, y = train[c].to_numpy(), train["incorrect"].to_numpy()
        for thr in np.nanpercentile(x, np.arange(5, 96, 5)):
            for d in (1, -1):
                f = f1_score(y, (d * (x - thr) > 0).astype(int), zero_division=0)
                if f > best[0]:
                    best = (f, c, thr, d)
    _, c, thr, d = best
    return lambda df: (d * (df[c].to_numpy() - thr) > 0).astype(int)


def metrics(y, pred, prob=None):
    out = {"precision_incorrect": round(precision_score(y, pred, zero_division=0), 3),
           "recall_incorrect": round(recall_score(y, pred, zero_division=0), 3),
           "f1_incorrect": round(f1_score(y, pred, zero_division=0), 3),
           "accuracy": round(float(np.mean(y == pred)), 3)}
    if prob is not None and len(set(y)) > 1:
        out["roc_auc"] = round(roc_auc_score(y, prob), 3)
    return out


def run(exercise):
    df, counting = collect(exercise)
    rel = [c for c in df.columns if c.endswith("_rel")]
    y = df["incorrect"].to_numpy()
    subjects = sorted(df["subject"].unique())
    prob = np.zeros(len(df))
    rules = np.zeros(len(df), dtype=int)
    for s in subjects:
        tr, te = (df["subject"] != s).to_numpy(), (df["subject"] == s).to_numpy()
        m = xgb.XGBClassifier(**XGB_PARAMS).fit(df.loc[tr, rel], y[tr])
        prob[te] = m.predict_proba(df.loc[te, rel])[:, 1]
        rules[te] = rule_fold(df[tr], rel)(df[te])
    ok = [t for t in np.linspace(0.05, 0.95, 91) if recall_score(y, (prob >= t).astype(int), zero_division=0) >= TARGET_RECALL]
    thr = float(max(ok)) if ok else 0.5
    pred = (prob >= thr).astype(int)

    final = xgb.XGBClassifier(**XGB_PARAMS).fit(df[rel], y)
    ARTIFACTS.mkdir(exist_ok=True)
    # The squat keeps its dedicated model (squat_xgb.json, used by the app); the generic one is saved beside it.
    stem = f"{exercise}_generic_xgb" if exercise == "squat" else f"{exercise}_xgb"
    final.save_model(ARTIFACTS / f"{stem}.json")
    (ARTIFACTS / f"{stem}_meta.json").write_text(json.dumps(
        {"exercise": exercise, "threshold": round(thr, 2), "features": rel, "baseline_reps": BASELINE_REPS,
         "min_depth_deg": MIN_DEPTH[exercise], "version": f"{exercise}_xgb_v1"}, indent=1))
    imp = sorted(zip(rel, final.feature_importances_.tolist()), key=lambda x: -x[1])[:8]
    res = {
        "exercise": exercise,
        "rep_counting": {"gt_reps": counting["gt"], "detected": counting["det"],
                         "precision": round(counting["matched"] / max(counting["det"], 1), 3),
                         "recall": round(counting["matched"] / max(counting["gt"], 1), 3),
                         "recall_by_view": {v: round(h / n, 3) for v, (h, n) in sorted(counting["by_view"].items())}},
        "classifier": {"n_reps": len(df), "n_incorrect": int(y.sum()), "n_subjects": len(subjects),
                       "evaluation": "leave-one-subject-out; baseline = first 3 correct reps per recording (excluded)",
                       "threshold": round(thr, 2), "xgboost": metrics(y, pred, prob),
                       "rules_baseline": metrics(y, rules)},
        "top_features": [[f, round(v, 3)] for f, v in imp],
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"exercise_{exercise}.json").write_text(json.dumps(res, indent=1))
    rc, c = res["rep_counting"], res["classifier"]
    print(f"{exercise:14} reps: P {rc['precision']:.2f} R {rc['recall']:.2f} {rc['recall_by_view']} | "
          f"XGB F1 {c['xgboost']['f1_incorrect']:.2f} AUC {c['xgboost'].get('roc_auc', 0):.2f} "
          f"| rules F1 {c['rules_baseline']['f1_incorrect']:.2f} | n={c['n_reps']}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", choices=list(EXERCISES.values()), nargs="*")
    args = ap.parse_args()
    for ex in args.exercise or list(EXERCISES.values()):
        run(ex)


if __name__ == "__main__":
    main()
