"""Rep-counting accuracy against REHAB24-6 ground truth (#6).

    python -m model.eval_reps --exercise squat

Ground truth marks every *annotated* repetition. A detected rep is matched to the ground-truth
rep it overlaps most (temporal IoU >= 0.3). Reported overall and per camera: count error,
exact-count rate, precision/recall, boundary error in frames. Recall is also broken down by the
camera view of each ground-truth rep (views change within a video, so this is per rep).
"""

import argparse
import json
from collections import defaultdict

import numpy as np

from model.config import RESULTS
from model.data import gt_reps, load_series, manifest, rep_view
from model.features import segment_reps

IOU_MATCH = 0.3


def iou(a, b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union else 0.0


def match(det, gt):
    pairs = sorted(((iou((d.start, d.end), (g["start"], g["end"])), i, j)
                    for i, d in enumerate(det) for j, g in enumerate(gt)), reverse=True)
    used_d, used_g, out = set(), set(), []
    for v, i, j in pairs:
        if v < IOU_MATCH:
            break
        if i not in used_d and j not in used_g:
            used_d.add(i)
            used_g.add(j)
            out.append((i, j, v))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", default="squat")
    ap.add_argument("--variant", default="full")
    args = ap.parse_args()

    rows, by_view = [], defaultdict(lambda: defaultdict(float))
    view_recall = defaultdict(lambda: [0, 0])  # view -> [matched gt reps, gt reps]
    for row in manifest(args.exercise):
        s = load_series(row, args.variant)
        det = segment_reps(s.knee, s.fps)
        gt = gt_reps(row["video_id"])
        m = match(det, gt)
        bound = [abs(det[i].start - gt[j]["start"]) + abs(det[i].end - gt[j]["end"]) for i, j, _ in m]
        r = {
            "video": f"{row['video_id']}-{row['camera']}", "lights_on": int(row["lights_on"]),
            "side": s.side, "gt_reps": len(gt), "detected": len(det), "matched": len(m),
            "count_error": len(det) - len(gt),
            "precision": len(m) / len(det) if det else None, "recall": len(m) / len(gt) if gt else None,
            "mean_boundary_error_frames": float(np.mean(bound)) / 2 if bound else None,
        }
        rows.append(r)
        hit = {j for _, j, _ in m}
        for j, g in enumerate(gt):
            v = view_recall[rep_view(row["camera"], g["orientation17"])]
            v[0] += j in hit
            v[1] += 1
        for key in ("all", "camera_" + row["camera"]):
            v = by_view[key]
            v["videos"] += 1
            v["gt"] += len(gt)
            v["det"] += len(det)
            v["matched"] += len(m)
            v["exact"] += r["count_error"] == 0
            v["abs_count_error"] += abs(r["count_error"])
        print(f"{r['video']:12} gt={len(gt):2} det={len(det):2} matched={len(m):2} "
              f"boundary={r['mean_boundary_error_frames'] or 0:.1f}f side={s.side}")

    summary = {}
    for key, v in by_view.items():
        summary[key] = {
            "videos": int(v["videos"]),
            "gt_reps": int(v["gt"]),
            "detected_reps": int(v["det"]),
            "precision": round(v["matched"] / v["det"], 3) if v["det"] else None,
            "recall": round(v["matched"] / v["gt"], 3) if v["gt"] else None,
            "exact_count_rate": round(v["exact"] / v["videos"], 3),
            "mean_abs_count_error": round(v["abs_count_error"] / v["videos"], 2),
        }
    recall_by_view = {v: {"gt_reps": n, "recall": round(h / n, 3)} for v, (h, n) in sorted(view_recall.items())}
    out = {"exercise": args.exercise, "pose_model": args.variant, "match_rule": f"temporal IoU >= {IOU_MATCH}",
           "summary": summary, "recall_by_view": recall_by_view, "videos": rows}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"rep_counting_{args.exercise}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(summary, indent=1))
    print("recall by view:", json.dumps(recall_by_view))


if __name__ == "__main__":
    main()
