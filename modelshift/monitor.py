import pandas as pd

from modelshift.baseline import BaselineWindow
from modelshift.drift.feature_drift import compute_feature_drift
from modelshift.drift.severity import classify_severity, compute_health_score
from modelshift.drift.prediction_drift import compute_prediction_drift


class ModelMonitor:
    """
    Main interface for ModelShift-Lite monitoring.
    """

    def __init__(self, reference_data: pd.DataFrame):
        """
        Initialize monitor with reference baseline data.
        """
        self.baseline = BaselineWindow(reference_data)

        # Data containers
        self.live_data = None

        # Feature drift
        self.feature_drift_results = None

        # Prediction drift
        self.baseline_predictions = None
        self.live_predictions = None
        self.prediction_drift_results = None

    # -----------------------
    # Data Update
    # -----------------------

    def update(self, live_data: pd.DataFrame):
        """
        Update monitor with new live data.
        """
        if not isinstance(live_data, pd.DataFrame):
            raise TypeError("Live data must be a pandas DataFrame")

        if live_data.empty:
            raise ValueError("Live data cannot be empty")

        self.live_data = live_data.copy()

    # -----------------------
    # Feature Drift
    # -----------------------

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

    # -----------------------
    # Prediction Drift
    # -----------------------

    def set_baseline_predictions(self, predictions):
        """
        Store baseline prediction probabilities.
        """
        self.baseline_predictions = predictions

    def update_predictions(self, live_predictions):
        """
        Update live prediction probabilities.
        """
        self.live_predictions = live_predictions

    def compute_prediction_drift(self) -> dict:
        """
        Compute prediction behavior drift.
        """
        if self.baseline_predictions is None:
            raise RuntimeError("Baseline predictions not set.")

        if self.live_predictions is None:
            raise RuntimeError("Live predictions not set.")

        self.prediction_drift_results = compute_prediction_drift(
            self.baseline_predictions,
            self.live_predictions
        )

        return self.prediction_drift_results
