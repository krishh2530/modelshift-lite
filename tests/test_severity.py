import numpy as np
import pandas as pd

from modelshift.drift.feature_drift import compute_feature_drift
from modelshift.drift.prediction_drift import compute_prediction_drift
from modelshift.drift.severity import compute_health_score


def _health_to_float(out):
    """
    compute_health_score has varied return types in many projects:
      - float
      - dict {health_score: ...}
      - tuple (score, mode)
    This helper accepts them all.
    """
    if isinstance(out, (int, float)):
        return float(out)

    if isinstance(out, dict):
        for k in ("health_score", "score", "health"):
            if k in out and out[k] is not None:
                return float(out[k])

    if isinstance(out, (tuple, list)) and len(out) >= 1:
        return float(out[0])

    return float(out)


def test_health_score_degrades_with_drift():
    baseX = pd.DataFrame({"f1": np.arange(200), "f2": np.arange(200) * 2})
    live_ok = baseX.copy()
    live_drift = pd.DataFrame({"f1": np.arange(200) + 1000, "f2": (np.arange(200) * 2) + 1000})

    base_p = np.linspace(0.05, 0.95, 200)
    ok_p = base_p.copy()
    drift_p = 1.0 - base_p

    fd_ok = compute_feature_drift(baseX, live_ok)
    pd_ok = compute_prediction_drift(base_p, ok_p)

    fd_d = compute_feature_drift(baseX, live_drift)
    pd_d = compute_prediction_drift(base_p, drift_p)

    # Support both signatures: dict bundle OR (fd, pd)
    try:
        h_ok = _health_to_float(compute_health_score({"feature_drift": fd_ok, "prediction_drift": pd_ok}))
        h_d = _health_to_float(compute_health_score({"feature_drift": fd_d, "prediction_drift": pd_d}))
    except TypeError:
        h_ok = _health_to_float(compute_health_score(fd_ok, pd_ok))
        h_d = _health_to_float(compute_health_score(fd_d, pd_d))

    assert np.isfinite(h_ok)
    assert np.isfinite(h_d)
    assert h_ok > h_d  # drift should reduce health