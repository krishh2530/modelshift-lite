def classify_severity(ks_statistic: float) -> str:
    """
    Classify drift severity based on KS statistic.
    """
    if ks_statistic < 0.2:
        return "Low"
    elif ks_statistic < 0.5:
        return "Medium"
    else:
        return "High"


def compute_health_score(feature_drift_results: dict) -> float:
    """
    Compute overall model health score (0–100).
    Higher score = healthier model.
    """

    if not feature_drift_results:
        raise ValueError("Feature drift results cannot be empty")

    ks_values = [
        v["ks_statistic"] for v in feature_drift_results.values()
    ]

    avg_ks = sum(ks_values) / len(ks_values)

    # Map avg KS to health score
    health_score = max(0.0, 100 * (1 - avg_ks))

    return round(health_score, 2)
