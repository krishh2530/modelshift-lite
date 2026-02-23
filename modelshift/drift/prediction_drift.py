from __future__ import annotations

import numpy as np
from scipy.stats import ks_2samp


def compute_prediction_drift(
    baseline_predictions: np.ndarray,
    live_predictions: np.ndarray
) -> dict:
    """
    Compute prediction behavior drift using:
      1) KS-test on prediction probability distributions
      2) Binary entropy change (mean entropy of predicted probabilities)

    Notes:
    - Expects 1D probability arrays (values in [0, 1]).
    - Uses full binary entropy: -(p*log(p) + (1-p)*log(1-p))
    """

    baseline = _prepare_predictions("baseline", baseline_predictions)
    live = _prepare_predictions("live", live_predictions)

    # KS-test on prediction distributions
    ks_stat, p_value = ks_2samp(baseline, live)

    # Entropy analysis (full binary entropy)
    baseline_entropy = _binary_entropy_mean(baseline)
    live_entropy = _binary_entropy_mean(live)
    entropy_change = live_entropy - baseline_entropy

    # Lightweight shape/center diagnostics (useful for dashboards/reports)
    baseline_mean = float(np.mean(baseline))
    live_mean = float(np.mean(live))
    baseline_std = float(np.std(baseline))
    live_std = float(np.std(live))
    baseline_median = float(np.median(baseline))
    live_median = float(np.median(live))

    return {
        "ks_statistic": float(ks_stat),
        "p_value": float(p_value),

        "baseline_entropy": round(float(baseline_entropy), 6),
        "live_entropy": round(float(live_entropy), 6),
        "entropy_change": round(float(entropy_change), 6),
        "abs_entropy_change": round(float(abs(entropy_change)), 6),

        "baseline_mean_prob": round(baseline_mean, 6),
        "live_mean_prob": round(live_mean, 6),
        "mean_prob_shift": round(float(live_mean - baseline_mean), 6),

        "baseline_median_prob": round(baseline_median, 6),
        "live_median_prob": round(live_median, 6),
        "median_prob_shift": round(float(live_median - baseline_median), 6),

        "baseline_std_prob": round(baseline_std, 6),
        "live_std_prob": round(live_std, 6),
        "std_prob_shift": round(float(live_std - baseline_std), 6),

        "n_baseline": int(baseline.size),
        "n_live": int(live.size),
    }


def _binary_entropy_mean(preds: np.ndarray) -> float:
    """
    Mean binary entropy for probability predictions:
      H(p) = -(p*log(p) + (1-p)*log(1-p))

    Uses natural log (nats).
    """
    eps = 1e-9
    p = np.clip(preds.astype(float), eps, 1.0 - eps)
    entropy = -(p * np.log(p) + (1.0 - p) * np.log(1.0 - p))
    return float(np.mean(entropy))


def _prepare_predictions(name: str, arr) -> np.ndarray:
    """
    Validate and normalize prediction arrays to a clean 1D float numpy array.
    """
    if arr is None:
        raise ValueError(f"{name.capitalize()} predictions cannot be None")

    if not isinstance(arr, np.ndarray):
        # Allow lists/Series while staying user-friendly
        try:
            arr = np.asarray(arr, dtype=float)
        except Exception as exc:
            raise TypeError(
                f"{name.capitalize()} predictions must be a numpy array or array-like of numeric values"
            ) from exc
    else:
        arr = arr.astype(float, copy=False)

    arr = np.ravel(arr)

    if arr.size == 0:
        raise ValueError(f"{name.capitalize()} prediction array cannot be empty")

    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name.capitalize()} predictions contain NaN/Inf values")

    # We treat these as probability predictions for entropy-based drift
    if np.min(arr) < 0.0 or np.max(arr) > 1.0:
        raise ValueError(
            f"{name.capitalize()} predictions must be probability values in [0, 1]"
        )

    return arr