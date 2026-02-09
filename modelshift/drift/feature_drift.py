import pandas as pd
from scipy.stats import ks_2samp


def compute_feature_drift(
    baseline_data: pd.DataFrame,
    live_data: pd.DataFrame
) -> dict:
    """
    Compute feature-level drift using the Kolmogorov–Smirnov test.

    Returns a dictionary:
    {
        feature_name: {
            "ks_statistic": float,
            "p_value": float
        }
    }
    """

    _validate_inputs(baseline_data, live_data)

    drift_results = {}

    for feature in baseline_data.columns:
        baseline_values = baseline_data[feature].dropna()
        live_values = live_data[feature].dropna()

        ks_stat, p_value = ks_2samp(baseline_values, live_values)

        drift_results[feature] = {
            "ks_statistic": float(ks_stat),
            "p_value": float(p_value),
        }

    return drift_results


def _validate_inputs(baseline_data, live_data):
    if not isinstance(baseline_data, pd.DataFrame):
        raise TypeError("Baseline data must be a pandas DataFrame")

    if not isinstance(live_data, pd.DataFrame):
        raise TypeError("Live data must be a pandas DataFrame")

    if baseline_data.empty or live_data.empty:
        raise ValueError("Baseline and live data cannot be empty")

    if list(baseline_data.columns) != list(live_data.columns):
        raise ValueError("Baseline and live data must have identical features")
