"""Rep-correctness classifier for squats: XGBoost vs a rules baseline, leave-one-subject-out (#8, #28).

    python -m model.train_classifier

Reps are the ones our counter detects (so training matches what the app sees), each matched to
a REHAB24-6 ground-truth rep (temporal IoU >= 0.3) to get its correct/incorrect label.
Both camera views are used; a subject's reps are always in the same fold.

Positive class = INCORRECT rep (what we want to catch and send to the physio).
"""

import json

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

from model.config import ARTIFACTS, RESULTS
from model.data import gt_reps, load_series, manifest, rep_view
from model.eval_reps import match
from model.features import RELATIVE_FEATURES, add_relative, rep_features, segment_reps

TARGET_RECALL = 0.80  # catch at least this share of incorrect reps; physio review absorbs false alarms
XGB_PARAMS = dict(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                  min_child_weight=3, reg_lambda=1.0, eval_metric="logloss")


def build_dataset(exercise="squat") -> pd.DataFrame:
    rows = []
    for row in manifest(exercise):
        s = load_series(row)
        det = segment_reps(s.knee, s.fps)
        if len(det) < 3:
            continue
        feats = add_relative([rep_features(s, d) for d in det])  # relative to all reps in this session
        gt = gt_reps(row["video_id"])
        for i, j, v in match(det, gt):
            f = feats[i]
            f.update(video=row["video_id"], camera=row["camera"], view=rep_view(row["camera"], gt[j]["orientation17"]),
                     subject=gt[j]["subject"], gt_rep=gt[j]["rep"], iou=v, incorrect=1 - gt[j]["correct"])
            rows.append(f)
    return pd.DataFrame(rows)


RULE_FEATURES = ("trunk_lean_max", "min_knee_angle", "knee_travel_max", "hip_knee_ratio", "descent_s",
                 "trunk_lean_max_z", "min_knee_angle_z", "knee_travel_max_z", "hip_knee_ratio_z", "descent_s_z")


def rules_baseline(train: pd.DataFrame):
    """One-feature thresholds learned on the training fold: best single split by F1 over a few
    absolute and session-relative features (so the baseline gets the same information)."""
    best = (0.0, None, None, None)
    for feat in RULE_FEATURES:
        x, y = train[feat].to_numpy(), train["incorrect"].to_numpy()
        for thr in np.nanpercentile(x, np.arange(5, 96, 5)):
            for direction in (1, -1):
                pred = (direction * (x - thr) > 0).astype(int)
                f = f1_score(y, pred, zero_division=0)
                if f > best[0]:
                    best = (f, feat, thr, direction)
    _, feat, thr, direction = best
    return lambda df: (direction * (df[feat].to_numpy() - thr) > 0).astype(int), f"{feat} {'>' if direction > 0 else '<'} {thr:.1f}"


def metrics(y, pred, prob=None):
    out = {
        "precision_incorrect": round(precision_score(y, pred, zero_division=0), 3),
        "recall_incorrect": round(recall_score(y, pred, zero_division=0), 3),
        "f1_incorrect": round(f1_score(y, pred, zero_division=0), 3),
        "accuracy": round(float(np.mean(y == pred)), 3),
        "confusion_matrix [[TN,FP],[FN,TP]]": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
    }
    if prob is not None and len(set(y)) > 1:
        out["roc_auc"] = round(roc_auc_score(y, prob), 3)
    return out


def main():
    df = build_dataset()
    df.to_csv(RESULTS / "squat_rep_features.csv", index=False)
    subjects = sorted(df["subject"].unique())
    print(f"{len(df)} reps ({df['incorrect'].sum()} incorrect) from {len(subjects)} subjects, both cameras")

    oof_prob = np.zeros(len(df))
    oof_rules = np.zeros(len(df), dtype=int)
    rule_desc = []
    for s in subjects:
        tr, te = df["subject"] != s, df["subject"] == s
        model = xgb.XGBClassifier(**XGB_PARAMS)
        model.fit(df.loc[tr, RELATIVE_FEATURES], df.loc[tr, "incorrect"])
        oof_prob[te.to_numpy()] = model.predict_proba(df.loc[te, RELATIVE_FEATURES])[:, 1]
        rule, desc = rules_baseline(df[tr])
        oof_rules[te.to_numpy()] = rule(df[te])
        rule_desc.append(desc)

    y = df["incorrect"].to_numpy()
    # threshold chosen on out-of-fold predictions to reach TARGET_RECALL on incorrect reps (#28)
    thresholds = np.linspace(0.05, 0.95, 91)
    ok = [t for t in thresholds if recall_score(y, (oof_prob >= t).astype(int), zero_division=0) >= TARGET_RECALL]
    threshold = float(max(ok)) if ok else 0.5
    pred = (oof_prob >= threshold).astype(int)

    per_subject = {}
    for s in subjects:
        m = (df["subject"] == s).to_numpy()
        per_subject[int(s)] = {"reps": int(m.sum()), "incorrect": int(y[m].sum()),
                               "recall_incorrect": round(recall_score(y[m], pred[m], zero_division=0), 3) if y[m].sum() else None,
                               "false_alarms": int(((pred == 1) & (y == 0) & m).sum())}

    final = xgb.XGBClassifier(**XGB_PARAMS).fit(df[RELATIVE_FEATURES], df["incorrect"])
    ARTIFACTS.mkdir(exist_ok=True)
    final.save_model(ARTIFACTS / "squat_xgb.json")
    imp = sorted(zip(RELATIVE_FEATURES, final.feature_importances_.tolist()), key=lambda x: -x[1])

    results = {
        "task": "squat rep correctness (positive = incorrect rep)",
        "dataset": "REHAB24-6 Ex6 squats, CC BY-NC 4.0 (Cernek et al., SISAP 2024)",
        "n_reps": len(df), "n_incorrect": int(y.sum()), "n_subjects": len(subjects),
        "evaluation": "leave-one-subject-out (9 folds); threshold picked on out-of-fold predictions",
        "threshold": round(threshold, 2), "target_recall": TARGET_RECALL,
        "xgboost": metrics(y, pred, oof_prob),
        "xgboost_by_view": {v: metrics(y[m], pred[m], oof_prob[m]) | {"reps": int(m.sum())}
                            for v in ("side", "half_profile", "front") if (m := (df["view"] == v).to_numpy()).any()},
        "xgboost_at_0.5": metrics(y, (oof_prob >= 0.5).astype(int), oof_prob),
        "rules_baseline": metrics(y, oof_rules) | {"rules_learned_per_fold": sorted(set(rule_desc))},
        "per_subject": per_subject,
        "feature_importance": [[f, round(v, 3)] for f, v in imp],
        "model_file": "model/artifacts/squat_xgb.json",
        "features": RELATIVE_FEATURES,
        "feature_note": "session-relative: each rep vs the median rep of the same session (needs >= 3 reps)",
    }
    (RESULTS / "classifier_squat.json").write_text(json.dumps(results, indent=1))
    meta = {"threshold": results["threshold"], "features": RELATIVE_FEATURES, "version": "squat_xgb_v1",
            "min_reps": 3}
    (ARTIFACTS / "squat_xgb_meta.json").write_text(json.dumps(meta, indent=1))
    for v, r in results["xgboost_by_view"].items():
        print("  view", v, {m: r[m] for m in ("reps", "precision_incorrect", "recall_incorrect", "f1_incorrect", "roc_auc") if m in r})
    for k in ("xgboost", "xgboost_at_0.5", "rules_baseline"):
        print(k, {m: v for m, v in results[k].items() if m != "rules_learned_per_fold"})
    print("threshold", results["threshold"], "| top features", imp[:5])


if __name__ == "__main__":
    main()
