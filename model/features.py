"""Joint angles, smoothing, rep segmentation and per-rep features from pose landmarks (#5, #25).

Input is MediaPipe's per-frame `image` landmarks (T, 33, 4: x, y, z, visibility), normalized
to the frame. Angles are computed in pixel space (x*width, y*height) so that non-square
frames don't distort them.
"""

from dataclasses import asdict, dataclass

import numpy as np
from scipy.signal import find_peaks, savgol_filter

# MediaPipe Pose landmark indices
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
L_FOOT, R_FOOT = 31, 32
SIDES = {"left": (L_SHOULDER, L_HIP, L_KNEE, L_ANKLE, L_FOOT), "right": (R_SHOULDER, R_HIP, R_KNEE, R_ANKLE, R_FOOT)}

MIN_VISIBILITY = 0.5
MAX_GAP_S = 0.35  # interpolate tracking gaps up to this long; longer gaps stay NaN


def _points(image, idx, width, height):
    return image[:, idx, :2] * np.array([width, height], dtype=np.float32)


def angle_at(a, b, c):
    """Angle ABC in degrees for arrays of 2D points (T, 2). NaN where undefined."""
    v1, v2 = a - b, c - b
    n = np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cos = np.einsum("ij,ij->i", v1, v2) / n
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def fill_and_smooth(x, fps, window_s=0.3):
    """Interpolate short NaN gaps, then Savitzky-Golay smooth. Long gaps stay NaN."""
    x = np.asarray(x, dtype=np.float64).copy()
    n = len(x)
    if n == 0:
        return x
    nan = np.isnan(x)
    if nan.all():
        return x
    idx = np.arange(n)
    filled = np.interp(idx, idx[~nan], x[~nan])
    # keep NaN for gaps longer than MAX_GAP_S
    max_gap = int(MAX_GAP_S * fps)
    run_start = None
    for i in range(n + 1):
        if i < n and nan[i]:
            run_start = i if run_start is None else run_start
        elif run_start is not None:
            if i - run_start > max_gap or run_start == 0 or i == n:
                filled[run_start:i] = np.nan
            run_start = None
    win = max(5, int(window_s * fps) | 1)
    good = ~np.isnan(filled)
    if good.sum() > win:
        # smooth each contiguous tracked segment separately
        out = filled.copy()
        edges = np.flatnonzero(np.diff(np.concatenate([[0], good.astype(int), [0]])))
        for s, e in zip(edges[::2], edges[1::2]):
            if e - s > win:
                out[s:e] = savgol_filter(filled[s:e], win, 2)
        return out
    return filled


@dataclass
class Series:
    fps: float
    side: str
    visibility: float           # mean hip/knee/ankle visibility on the chosen side
    knee: np.ndarray            # smoothed knee angle, degrees (180 = straight)
    hip: np.ndarray             # smoothed hip angle (shoulder-hip-knee)
    trunk_lean: np.ndarray      # torso angle from vertical, degrees
    knee_other: np.ndarray      # other leg's knee angle (for asymmetry)
    knee_travel: np.ndarray     # horizontal knee-over-toe distance / shin length
    tracked: np.ndarray         # bool per frame: chosen side visible


def compute_series(image, width, height, fps) -> Series:
    vis = {s: np.nanmean(image[:, [ids[1], ids[2], ids[3]], 3]) for s, ids in SIDES.items()}
    side = max(vis, key=lambda s: -1 if np.isnan(vis[s]) else vis[s])
    other = "right" if side == "left" else "left"
    sh, hp, kn, an, ft = SIDES[side]
    P = lambda i: _points(image, i, width, height)  # noqa: E731

    with np.errstate(invalid="ignore"):
        frame_vis = np.min(np.nan_to_num(image[:, [hp, kn, an], 3], nan=0.0), axis=1)
    tracked = np.nan_to_num(frame_vis, nan=0.0) >= MIN_VISIBILITY

    def masked(x):
        x = x.copy()
        x[~tracked] = np.nan
        return fill_and_smooth(x, fps)

    knee = masked(angle_at(P(hp), P(kn), P(an)))
    hip = masked(angle_at(P(sh), P(hp), P(kn)))
    torso = P(sh) - P(hp)  # image y grows downward: upright torso points to -y
    lean = np.degrees(np.arctan2(np.abs(torso[:, 0]), -torso[:, 1]))
    shin = np.linalg.norm(P(kn) - P(an), axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        travel = np.abs(P(kn)[:, 0] - P(ft)[:, 0]) / shin
    osh, ohp, okn, oan, _ = SIDES[other]
    knee_other = fill_and_smooth(angle_at(P(ohp), P(okn), P(oan)), fps)
    return Series(fps, side, float(vis[side]), knee, hip, masked(lean), knee_other, masked(travel), tracked)


@dataclass
class Rep:
    index: int
    start: int
    bottom: int
    end: int


def segment_reps(knee, fps, min_depth_deg=15.0, min_rep_s=0.8, max_rep_s=8.0) -> list[Rep]:
    """Squat reps = knee-angle troughs with enough depth, bounded by the standing peaks around them.

    min_depth_deg is low on purpose: rehab squats are often shallow (REHAB24-6 has correct
    mini-squats of ~20 degrees).

    A rep starts at the standing peak before a trough and ends at the standing peak after it.
    """
    k = np.asarray(knee, dtype=np.float64)
    good = ~np.isnan(k)
    if good.sum() < fps:
        return []
    k = np.where(good, k, np.interp(np.arange(len(k)), np.flatnonzero(good), k[good]))
    troughs, _ = find_peaks(-k, prominence=min_depth_deg, distance=int(min_rep_s * fps * 0.6))
    peaks, _ = find_peaks(k, prominence=min_depth_deg / 3, distance=int(0.3 * fps))
    reps = []
    for t in troughs:
        before = peaks[peaks < t]
        after = peaks[peaks > t]
        # no standing peak on one side (first/last rep): take the highest point within half a max-length rep
        half = int(max_rep_s * fps / 2)
        lo = max(0, t - half)
        start = int(before[-1]) if len(before) else lo + int(np.argmax(k[lo : t + 1]))
        end = int(after[0]) if len(after) else t + int(np.argmax(k[t : t + half + 1]))
        if reps and start < reps[-1].end:  # two troughs sharing a peak: split at the higher point between them
            mid = reps[-1].bottom + int(np.argmax(k[reps[-1].bottom : t + 1]))
            reps[-1].end = start = mid
        dur = (end - start) / fps
        if min_rep_s <= dur <= max_rep_s and k[start] - k[t] >= min_depth_deg * 0.8:
            reps.append(Rep(len(reps) + 1, start, int(t), end))
    return reps


def rep_features(s: Series, rep: Rep) -> dict:
    """Per-rep features for the classifier and the explanations. All plain numbers."""
    sl = slice(rep.start, rep.end + 1)
    k, h, lean = s.knee[sl], s.hip[sl], s.trunk_lean[sl]
    fps = s.fps
    b = rep.bottom - rep.start
    vel = np.diff(k) * fps
    acc = np.diff(vel) * fps
    jerk = np.diff(acc) * fps
    standing = float(np.nanmax(k))
    depth = float(np.nanmin(k))
    dur = (rep.end - rep.start) / fps
    other = s.knee_other[sl]
    return {
        "min_knee_angle": depth,
        "knee_rom": standing - depth,
        "start_knee_angle": float(k[0]),
        "end_knee_angle": float(k[-1]),
        "min_hip_angle": float(np.nanmin(h)),
        "hip_rom": float(np.nanmax(h) - np.nanmin(h)),
        "hip_knee_ratio": float((np.nanmax(h) - np.nanmin(h)) / max(standing - depth, 1e-6)),
        "trunk_lean_max": float(np.nanmax(lean)),
        "trunk_lean_bottom": float(lean[b]) if not np.isnan(lean[b]) else float(np.nanmax(lean)),
        "knee_travel_max": float(np.nanmax(s.knee_travel[sl])),
        "duration_s": dur,
        "descent_s": b / fps,
        "ascent_s": (rep.end - rep.bottom) / fps,
        "descent_ascent_ratio": (b + 1) / (rep.end - rep.bottom + 1),
        "peak_descent_speed": float(-np.nanmin(vel)) if len(vel) else 0.0,
        "peak_ascent_speed": float(np.nanmax(vel)) if len(vel) else 0.0,
        "jerk_rms": float(np.sqrt(np.nanmean(jerk**2))) if len(jerk) else 0.0,
        "bottom_pause_s": float(np.sum(k < depth + 5) / fps),
        "asymmetry_bottom": float(abs(k[b] - other[b])) if not np.isnan(other[b]) else np.nan,
        "tracked_fraction": float(np.mean(s.tracked[sl])),
        "visibility": s.visibility,
    }


FEATURES = [  # stable column order for the model
    "min_knee_angle", "knee_rom", "start_knee_angle", "end_knee_angle", "min_hip_angle", "hip_rom",
    "hip_knee_ratio", "trunk_lean_max", "trunk_lean_bottom", "knee_travel_max", "duration_s", "descent_s",
    "ascent_s", "descent_ascent_ratio", "peak_descent_speed", "peak_ascent_speed", "jerk_rms",
    "bottom_pause_s", "asymmetry_bottom", "tracked_fraction", "visibility",
]


def rep_to_dict(rep: Rep, fps: float) -> dict:
    d = asdict(rep)
    d.update(start_s=rep.start / fps, end_s=rep.end / fps)
    return d


# ---------------------------------------------------------------- session-relative features
# Each rep compared with the same person's typical rep in the session (median), so the model
# learns "worse than your usual rep" instead of "different from other people".
RELATIVE_BASE = [f for f in FEATURES if f not in ("visibility", "tracked_fraction")]
RELATIVE_FEATURES = [f + suffix for f in RELATIVE_BASE for suffix in ("_rel", "_z")]
MIN_REPS_FOR_RELATIVE = 3


def add_relative(reps: list[dict]) -> list[dict]:
    """Adds <feature>_rel (difference from the session median) and <feature>_z (scaled by the session
    spread) to each rep's feature dict. Needs at least MIN_REPS_FOR_RELATIVE reps."""
    if len(reps) < MIN_REPS_FOR_RELATIVE:
        raise ValueError(f"need at least {MIN_REPS_FOR_RELATIVE} reps for session-relative features")
    out = [dict(r) for r in reps]
    for f in RELATIVE_BASE:
        x = np.array([r[f] for r in reps], dtype=np.float64)
        med = np.nanmedian(x)
        sd = np.nanstd(x, ddof=1) if np.sum(~np.isnan(x)) > 1 else np.nan
        for r, v in zip(out, x):
            r[f + "_rel"] = v - med
            r[f + "_z"] = (v - med) / (sd + 1e-6) if not np.isnan(sd) else 0.0
    return out
