import numpy as np
import pytest

from model.features import add_relative, angle_at, fill_and_smooth, segment_reps

FPS = 30


def squat_curve(depths, rep_s=3.0, pause_s=1.0, standing=172.0, start_mid_rep=False):
    """Synthetic knee-angle trace: one cosine dip per rep, standing pauses in between."""
    parts = [np.full(int(pause_s * FPS), standing)]
    for d in depths:
        t = np.linspace(0, 2 * np.pi, int(rep_s * FPS))
        parts.append(standing - d * (1 - np.cos(t)) / 2)
        parts.append(np.full(int(pause_s * FPS), standing))
    x = np.concatenate(parts)
    if start_mid_rep:  # video starts while the person is already squatting down
        x = x[int((pause_s + rep_s / 3) * FPS):]
    return x + np.random.default_rng(0).normal(0, 1.0, len(x))


def test_angle_at_right_angle():
    a, b, c = np.array([[0.0, 1.0]]), np.array([[0.0, 0.0]]), np.array([[1.0, 0.0]])
    assert angle_at(a, b, c)[0] == pytest.approx(90.0)


def test_counts_deep_and_shallow_reps():
    reps = segment_reps(fill_and_smooth(squat_curve([80, 75, 90, 22, 20]), FPS), FPS)
    assert len(reps) == 5
    assert all(r.start < r.bottom < r.end for r in reps)


def test_ignores_small_wobbles():
    wobble = squat_curve([6, 8, 5])
    assert segment_reps(fill_and_smooth(wobble, FPS), FPS) == []


def test_rep_at_video_start_is_bounded():
    reps = segment_reps(fill_and_smooth(squat_curve([80, 80, 80], start_mid_rep=True), FPS), FPS)
    assert len(reps) >= 2
    assert all((r.end - r.start) / FPS <= 8.0 for r in reps)


def test_fill_keeps_long_gaps_nan():
    x = np.full(100, 170.0)
    x[10:13] = np.nan   # short gap: filled
    x[40:80] = np.nan   # long gap: stays missing
    y = fill_and_smooth(x, FPS)
    assert not np.isnan(y[10:13]).any()
    assert np.isnan(y[45:75]).all()


def test_relative_features_need_a_baseline():
    with pytest.raises(ValueError):
        add_relative([{}], baseline=[{}, {}])


def test_relative_features_subtract_baseline_median():
    from model.features import RELATIVE_BASE

    base = [{f: v for f in RELATIVE_BASE} for v in (1.0, 2.0, 3.0)]
    out = add_relative([{f: 10.0 for f in RELATIVE_BASE}], base)
    assert out[0]["min_knee_angle_rel"] == pytest.approx(8.0)
