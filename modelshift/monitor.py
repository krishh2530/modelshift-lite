import pandas as pd
from modelshift.baseline import BaselineWindow
from modelshift.drift.feature_drift import compute_feature_drift
from modelshift.drift.severity import classify_severity, compute_health_score

class ModelMonitor:
    """
    Main interface for ModelShift-Lite monitoring.
    """

    def __init__(self, reference_data: pd.DataFrame):
        """
        Initialize monitor with reference baseline data.
        """
        self.baseline = BaselineWindow(reference_data)
        self.live_data = None
        self.feature_drift_results = None

    def update(self, live_data: pd.DataFrame):
        """
        Update monitor with new live data.
        """
        if not isinstance(live_data, pd.DataFrame):
            raise TypeError("Live data must be a pandas DataFrame")

        if live_data.empty:
            raise ValueError("Live data cannot be empty")

        self.live_data = live_data.copy()

    def compute_feature_drift(self) -> dict:
        """
        Compute feature-level drift between baseline and live data.
        """
        if self.live_data is None:
            raise RuntimeError("Live data not set. Call update() first.")

        self.feature_drift_results = compute_feature_drift(
            self.baseline.get_data(),
            self.live_data
        )

        return self.feature_drift_results

    def get_latest_feature_drift(self) -> dict:
        """
        Return last computed feature drift results.
        """
        if self.feature_drift_results is None:
            raise RuntimeError("No feature drift computed yet.")

        return self.feature_drift_results
    def get_feature_severity(self) -> dict:
        """
        Return severity classification per feature.
        """
        if self.feature_drift_results is None:
            raise RuntimeError("No feature drift computed yet.")

        severity = {}
        for feature, values in self.feature_drift_results.items():
            severity[feature] = classify_severity(values["ks_statistic"])

        return severity

    def get_model_health_score(self) -> float:
        """
        Return overall model health score.
        """
        if self.feature_drift_results is None:
            raise RuntimeError("No feature drift computed yet.")

        return compute_health_score(self.feature_drift_results)

