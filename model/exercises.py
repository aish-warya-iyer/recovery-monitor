"""Per-exercise movement signals for all six REHAB24-6 exercises.

Every exercise is reduced to one PRIMARY signal in degrees shaped like the squat's knee angle:
high at rest, dipping during the active part of a rep. That lets one rep segmenter and one feature
set serve every exercise. Raises (arm/leg abduction) are flipped (180 - raise angle) to fit.

  exercise        primary signal (at rest -> active)                        secondary signals
  squat           knee angle, hip-knee-ankle (~175 -> ~90)                    hip angle, trunk lean
  leg_lunge       mean knee angle of both legs (~175 -> ~95)                  trunk lean, knee asymmetry
  leg_abduction   180 - leg raise (hip->ankle vs body axis) (~180 -> ~140)    other leg, trunk tilt
  arm_abduction   180 - arm raise (hip-shoulder-wrist) (~170 -> ~30)          elbow angle, trunk tilt
  arm_vw          mean elbow angle, shoulder-elbow-wrist (V ~170 -> W ~90)    shoulder raise, asymmetry
  push_ups        mean elbow angle (~170 -> ~90)                              body line (shoulder-hip-ankle)
"""

from dataclasses import dataclass

import numpy as np

from model.features import angle_at, fill_and_smooth

# MediaPipe landmark indices
SH = (11, 12)
EL = (13, 14)
WR = (15, 16)
HP = (23, 24)
KN = (25, 26)
AN = (27, 28)


@dataclass
class Signals:
    fps: float
    primary: np.ndarray        # degrees, high at rest, low when active
    secondary: dict            # name -> degrees series
    tracked: np.ndarray        # bool per frame
    visibility: float
    side: str                  # "left" / "right" / "both"


def _pts(image, i, w, h):
    return image[:, i, :2] * np.array([w, h], dtype=np.float32)


def _vis(image, idx):
    return np.nan_to_num(np.min(image[:, list(idx), 3], axis=1), nan=0.0)


def _axis_angle(a, b, ref):
    """Angle between vectors a->b and ref (T,2) in degrees."""
    v = b - a
    with np.errstate(invalid="ignore", divide="ignore"):
        cos = np.einsum("ij,ij->i", v, ref) / (np.linalg.norm(v, axis=1) * np.linalg.norm(ref, axis=1))
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def compute_signals(exercise: str, image: np.ndarray, width: int, height: int, fps: float) -> Signals:
    P = lambda i: _pts(image, i, width, height)  # noqa: E731
    mid = lambda a, b: (P(a) + P(b)) / 2  # noqa: E731
    down = mid(*HP) - mid(*SH)  # body axis pointing from shoulders to hips (downwards)
    lean = np.degrees(np.arctan2(np.abs(down[:, 0]), down[:, 1]))  # 0 = upright

    def knee(s):
        return angle_at(P(HP[s]), P(KN[s]), P(AN[s]))

    def elbow(s):
        return angle_at(P(SH[s]), P(EL[s]), P(WR[s]))

    def arm_raise(s):
        return angle_at(P(HP[s]), P(SH[s]), P(WR[s]))

    def leg_raise(s):
        return _axis_angle(P(HP[s]), P(AN[s]), down)

    def choose(vals, idx_sets, prefer_motion=True):
        """Pick the side (0 left / 1 right) that moves most and is visible."""
        scores = []
        for s in (0, 1):
            v = vals(s)
            vis = float(np.mean(_vis(image, idx_sets[s])))
            rng = float(np.nanpercentile(v, 95) - np.nanpercentile(v, 5)) if np.isfinite(v).any() else 0.0
            scores.append((rng if prefer_motion else 0) * vis + vis)
        return int(np.argmax(scores))

    if exercise == "squat":
        s = choose(knee, [(HP[0], KN[0], AN[0]), (HP[1], KN[1], AN[1])], prefer_motion=False)
        prim, idx = knee(s), (HP[s], KN[s], AN[s])
        sec = {"hip": angle_at(P(SH[s]), P(HP[s]), P(KN[s])), "trunk_lean": lean, "other": knee(1 - s)}
        side = ("left", "right")[s]
    elif exercise == "leg_lunge":
        prim = np.nanmean([knee(0), knee(1)], axis=0)
        idx = (HP[0], KN[0], AN[0], HP[1], KN[1], AN[1])
        sec = {"trunk_lean": lean, "asymmetry": np.abs(knee(0) - knee(1)), "other": np.nanmin([knee(0), knee(1)], axis=0)}
        side = "both"
    elif exercise == "leg_abduction":
        s = choose(leg_raise, [(HP[0], AN[0]), (HP[1], AN[1])])
        prim, idx = 180 - leg_raise(s), (HP[s], KN[s], AN[s])
        sec = {"other": leg_raise(1 - s), "trunk_lean": lean, "knee": knee(s)}
        side = ("left", "right")[s]
    elif exercise == "arm_abduction":
        s = choose(arm_raise, [(SH[0], WR[0]), (SH[1], WR[1])])
        prim, idx = 180 - arm_raise(s), (HP[s], SH[s], WR[s])
        sec = {"elbow": elbow(s), "trunk_lean": lean, "other": arm_raise(1 - s)}
        side = ("left", "right")[s]
    elif exercise == "arm_vw":
        prim = np.nanmean([elbow(0), elbow(1)], axis=0)
        idx = (SH[0], EL[0], WR[0], SH[1], EL[1], WR[1])
        sec = {"shoulder": np.nanmean([arm_raise(0), arm_raise(1)], axis=0),
               "asymmetry": np.abs(elbow(0) - elbow(1)), "trunk_lean": lean}
        side = "both"
    elif exercise == "push_ups":
        prim = np.nanmean([elbow(0), elbow(1)], axis=0)
        idx = (SH[0], EL[0], WR[0], SH[1], EL[1], WR[1])
        sec = {"body_line": np.nanmean([angle_at(P(SH[i]), P(HP[i]), P(AN[i])) for i in (0, 1)], axis=0),
               "asymmetry": np.abs(elbow(0) - elbow(1)), "trunk_lean": lean}
        side = "both"
    else:
        raise ValueError(f"unknown exercise {exercise!r}")

    vis = _vis(image, idx)
    tracked = vis >= 0.5

    def clean(x):
        x = np.asarray(x, dtype=np.float64).copy()
        x[~tracked] = np.nan
        return fill_and_smooth(x, fps)

    return Signals(fps, clean(prim), {k: fill_and_smooth(v, fps) for k, v in sec.items()}, tracked,
                   float(np.mean(vis)), side)


def rep_features_generic(sig: Signals, rep) -> dict:
    """Exercise-agnostic per-rep features from the primary and secondary signals."""
    sl = slice(rep.start, rep.end + 1)
    k = sig.primary[sl]
    fps = sig.fps
    b = rep.bottom - rep.start
    vel = np.diff(k) * fps
    jerk = np.diff(vel, n=2) * fps * fps
    rest, peak = float(np.nanmax(k)), float(np.nanmin(k))
    f = {
        "peak": peak, "rom": rest - peak, "start": float(k[0]), "end": float(k[-1]),
        "duration_s": (rep.end - rep.start) / fps, "down_s": b / fps, "up_s": (rep.end - rep.bottom) / fps,
        "down_up_ratio": (b + 1) / (rep.end - rep.bottom + 1),
        "peak_down_speed": float(-np.nanmin(vel)) if len(vel) else 0.0,
        "peak_up_speed": float(np.nanmax(vel)) if len(vel) else 0.0,
        "jerk_rms": float(np.sqrt(np.nanmean(jerk ** 2))) if len(jerk) else 0.0,
        "hold_s": float(np.sum(k < peak + 5) / fps),
        "tracked_fraction": float(np.mean(sig.tracked[sl])),
    }
    for name, s in sig.secondary.items():
        v = s[sl]
        if np.isfinite(v).any():
            f[f"{name}_max"] = float(np.nanmax(v))
            f[f"{name}_min"] = float(np.nanmin(v))
            f[f"{name}_at_peak"] = float(v[b]) if np.isfinite(v[b]) else float(np.nanmean(v))
        else:
            f[f"{name}_max"] = f[f"{name}_min"] = f[f"{name}_at_peak"] = np.nan
    return f
