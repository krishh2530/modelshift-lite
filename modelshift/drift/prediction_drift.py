import numpy as np
from scipy.stats import ks_2samp


def compute_prediction_drift(
    baseline_predictions: np.ndarray,
    live_predictions: np.ndarray
) -> dict:
    """
    Compute prediction behavior drift using KS-test
    and entropy change.
    """

    _validate_predictions(baseline_predictions, live_predictions)

    # KS-test on prediction distributions
    ks_stat, p_value = ks_2samp(baseline_predictions, live_predictions)

    # Entropy analysis
    baseline_entropy = _entropy(baseline_predictions)
    live_entropy = _entropy(live_predictions)

    entropy_change = live_entropy - baseline_entropy

    return {
        "ks_statistic": float(ks_stat),
        "p_value": float(p_value),
        "baseline_entropy": round(baseline_entropy, 4),
        "live_entropy": round(live_entropy, 4),
        "entropy_change": round(entropy_change, 4),
    }


def _entropy(preds: np.ndarray) -> float:
    """
    Compute entropy of prediction probabilities.
    """
    preds = np.clip(preds, 1e-9, 1.0)
    return float(-np.mean(preds * np.log(preds)))


def _validate_predictions(baseline, live):
    if not isinstance(baseline, np.ndarray):
        raise TypeError("Baseline predictions must be a numpy array")

    if not isinstance(live, np.ndarray):
        raise TypeError("Live predictions must be a numpy array")

    if baseline.size == 0 or live.size == 0:
        raise ValueError("Prediction arrays cannot be empty")
