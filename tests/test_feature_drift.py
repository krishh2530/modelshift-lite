import numpy as np
import pandas as pd

from modelshift.drift.feature_drift import compute_feature_drift


def _extract_feature_map(fd):
    """
    Your codebase has had schema changes before.
    This makes tests robust to either:
      fd["feature_drift_results"] or fd["feature_drift"] or fd["results"] or fd directly.
    """
    if not isinstance(fd, dict):
        return {}
    for k in ("feature_drift_results", "feature_drift", "results"):
        if k in fd and isinstance(fd[k], dict):
            return fd[k]
    return fd


def test_feature_drift_zero_when_identical():
    base = pd.DataFrame({"f1": np.arange(100), "f2": np.arange(100) * 2})
    live = base.copy()

    fd = compute_feature_drift(base, live)
    fmap = _extract_feature_map(fd)

    assert "f1" in fmap and "f2" in fmap

    ks1 = fmap["f1"].get("ks_statistic", fmap["f1"].get("ks"))
    ks2 = fmap["f2"].get("ks_statistic", fmap["f2"].get("ks"))

    # For identical arrays, KS should be exactly 0 in most implementations.
    assert float(ks1) == 0.0
    assert float(ks2) == 0.0


def test_feature_drift_high_when_strong_shift():
    base = pd.DataFrame({"f1": np.arange(100), "f2": np.arange(100) * 2})
    # Strong shift (no overlap) => KS tends toward 1
    drift = pd.DataFrame({"f1": np.arange(100) + 1000, "f2": (np.arange(100) * 2) + 1000})

    fd = compute_feature_drift(base, drift)
    fmap = _extract_feature_map(fd)

    ks1 = float(fmap["f1"].get("ks_statistic", fmap["f1"].get("ks")))
    ks2 = float(fmap["f2"].get("ks_statistic", fmap["f2"].get("ks")))

    assert 0.80 <= ks1 <= 1.0
    assert 0.80 <= ks2 <= 1.0