from __future__ import annotations

import uuid
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from modelshift.baseline import BaselineWindow
from modelshift.drift.feature_drift import compute_feature_drift
from modelshift.drift.prediction_drift import compute_prediction_drift
from modelshift.drift.severity import (
    classify_severity,
    compute_health_score,
    evaluate_drift_state,
    summarize_feature_drift,
)

# -------------------------------------------------------------------
# Phase 2: Cloud SDK Configuration
# -------------------------------------------------------------------
_CLOUD_CONFIG = {
    "api_key": None,
    "endpoint": "http://127.0.0.1:8000/api/v1/track"
}

def init(api_key: str, endpoint: str = "http://127.0.0.1:8000/api/v1/track"):
    """
    Initialize the ModelShift-Lite SDK with your cloud API Key.
    This links your local ML models to your cloud dashboard.
    """
    _CLOUD_CONFIG["api_key"] = api_key
    _CLOUD_CONFIG["endpoint"] = endpoint
    print(f"[✓] ModelShift SDK Authenticated. Cloud sync enabled.")

# -------------------------------------------------------------------
# Core Engine
# -------------------------------------------------------------------
class ModelMonitor:
    """
    Main interface for ModelShift-Lite monitoring.

    Handles:
    - baseline/live feature drift
    - baseline/live prediction drift
    - composite status/severity/taxonomy summary
    """

    def __init__(self, reference_data: pd.DataFrame):
        """
        Initialize monitor with reference baseline data.
        """
        if not isinstance(reference_data, pd.DataFrame):
            raise TypeError("Reference data must be a pandas DataFrame")
        if reference_data.empty:
            raise ValueError("Reference data cannot be empty")

        self.baseline = BaselineWindow(reference_data.copy())

        # Data containers
        self.live_data: Optional[pd.DataFrame] = None

        # Feature drift
        self.feature_drift_results: Optional[Dict[str, Any]] = None

        # Prediction drift
        self.baseline_predictions: Optional[np.ndarray] = None
        self.live_predictions: Optional[np.ndarray] = None
        self.prediction_drift_results: Optional[Dict[str, Any]] = None

    # -----------------------
    # Data Update
    # -----------------------
    def update(self, live_data: pd.DataFrame):
        """
        Update monitor with new live data.
        Enforces same columns as baseline (reordered if needed).
        """
        if not isinstance(live_data, pd.DataFrame):
            raise TypeError("Live data must be a pandas DataFrame")
        if live_data.empty:
            raise ValueError("Live data cannot be empty")

        baseline_df = self.baseline.get_data()
        baseline_cols = list(baseline_df.columns)
        live_cols = list(live_data.columns)

        if set(live_cols) != set(baseline_cols):
            missing = [c for c in baseline_cols if c not in live_cols]
            extra = [c for c in live_cols if c not in baseline_cols]
            raise ValueError(
                f"Live data columns must match baseline columns. Missing={missing}, Extra={extra}"
            )

        # Reorder to baseline column order for deterministic behavior
        self.live_data = live_data[baseline_cols].copy()

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
        if self.feature_drift_results is None:
            raise RuntimeError("No feature drift computed yet.")
        return self.feature_drift_results

    def get_feature_severity(self) -> dict:
        if self.feature_drift_results is None:
            raise RuntimeError("No feature drift computed yet.")

        severity = {}
        for feature, values in self.feature_drift_results.items():
            if not isinstance(values, dict):
                continue
            severity[feature] = classify_severity(values.get("ks_statistic", 0.0))

        return severity

    def get_model_health_score(self) -> float:
        if self.feature_drift_results is None:
            raise RuntimeError("No feature drift computed yet.")
        return compute_health_score(self.feature_drift_results)

    def get_top_drifted_features(self, k: int = 5) -> List[Dict[str, Any]]:
        if self.feature_drift_results is None:
            raise RuntimeError("No feature drift computed yet.")
        if not isinstance(k, int) or k <= 0:
            raise ValueError("k must be a positive integer")

        rows: List[Dict[str, Any]] = []
        for feature, values in self.feature_drift_results.items():
            if not isinstance(values, dict):
                continue
            ks = _safe_float(values.get("ks_statistic"), 0.0)
            pv = _safe_float(values.get("p_value"), None)
            rows.append({
                "feature": str(feature),
                "ks_statistic": round(ks, 6),
                "p_value": None if pv is None else round(pv, 6),
                "severity": classify_severity(ks),
            })

        rows.sort(key=lambda x: x["ks_statistic"], reverse=True)
        return rows[:k]

    def get_most_drifted_feature(self) -> Optional[Dict[str, Any]]:
        top = self.get_top_drifted_features(k=1)
        return top[0] if top else None

    # -----------------------
    # Prediction Drift
    # -----------------------
    def set_baseline_predictions(self, predictions):
        self.baseline_predictions = _prepare_prediction_array(predictions, "baseline")

    def update_predictions(self, live_predictions):
        self.live_predictions = _prepare_prediction_array(live_predictions, "live")

    def compute_prediction_drift(self) -> dict:
        if self.baseline_predictions is None:
            raise RuntimeError("Baseline predictions not set.")
        if self.live_predictions is None:
            raise RuntimeError("Live predictions not set.")

        self.prediction_drift_results = compute_prediction_drift(
            self.baseline_predictions,
            self.live_predictions
        )
        return self.prediction_drift_results

    def get_latest_prediction_drift(self) -> dict:
        if self.prediction_drift_results is None:
            raise RuntimeError("No prediction drift computed yet.")
        return self.prediction_drift_results

    # -----------------------
    # Composite Summary
    # -----------------------
    def evaluate_health(self) -> Dict[str, Any]:
        if self.feature_drift_results is None:
            raise RuntimeError("No feature drift computed yet.")
        if self.prediction_drift_results is None:
            raise RuntimeError("No prediction drift computed yet.")

        decision = evaluate_drift_state(
            feature_drift_results=self.feature_drift_results,
            prediction_drift_results=self.prediction_drift_results,
        )

        feature_summary = summarize_feature_drift(self.feature_drift_results)
        top_features = self.get_top_drifted_features(k=5)
        most_feature = top_features[0] if top_features else None

        return {
            "status": decision.get("status"),
            "severity": decision.get("severity"),
            "taxonomy": decision.get("taxonomy"),
            "health_score": decision.get("health_score"),
            "feature_summary": feature_summary,
            "prediction_drift": self.prediction_drift_results,
            "top_drifted_features": top_features,
            "most_drifted_feature": most_feature,
            "signals": decision.get("signals", {}),
            "thresholds": decision.get("thresholds", {}),
        }

    def build_snapshot(self) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {
            "feature_drift": self.feature_drift_results,
            "prediction_drift": self.prediction_drift_results,
        }

        if self.feature_drift_results is not None:
            snapshot["feature_severity"] = self.get_feature_severity()
            snapshot["health_score"] = self.get_model_health_score()
            snapshot["top_drifted_features"] = self.get_top_drifted_features(k=5)
            snapshot["most_drifted_feature"] = self.get_most_drifted_feature()

        if self.feature_drift_results is not None and self.prediction_drift_results is not None:
            snapshot["decision"] = self.evaluate_health()

        return snapshot

    # -----------------------
    # Phase 2: Cloud Sync Method
    # -----------------------
    def push(self) -> Optional[Dict[str, Any]]:
        """
        Takes the local drift calculation and beams it securely to your FastAPI dashboard.
        """
        if not _CLOUD_CONFIG["api_key"]:
            print("[!] API Key Missing. Please add 'modelshift.init(api_key=\"YOUR_KEY\")' at the top of your script.")
            return None
            
        snapshot = self.build_snapshot()
        decision = snapshot.get("decision", {})
        
        mdf = snapshot.get("most_drifted_feature") or {}
        pred_drift = snapshot.get("prediction_drift") or {}
        
        # Package the data exactly how your dashboard expects it
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        payload = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": decision.get("status", "UNKNOWN"),
            "window_size": len(self.live_data) if self.live_data is not None else 0,
            
            # Dashboard Graph Metrics
            "clean_health": 100.0,
            "drifted_health": decision.get("health_score", 0.0),
            "drifted_pred_ks": pred_drift.get("ks_statistic", 0.0),
            "drifted_entropy_change": pred_drift.get("delta_entropy", 0.0),
            "drifted_last_window_feature": mdf.get("feature"),
            "drifted_last_window_ks": mdf.get("ks_statistic"),
            
            "evaluation": snapshot
        }

        # The Security Checkpoint
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": _CLOUD_CONFIG["api_key"]
        }
        
        try:
            print(f"[~] Beaming data to {_CLOUD_CONFIG['endpoint']}...")
            response = requests.post(_CLOUD_CONFIG["endpoint"], json=payload, headers=headers)
            response.raise_for_status()
            print(f"[✓] Successfully synced run '{run_id}' to ModelShift Cloud.")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[!] ModelShift Cloud Sync Failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"[!] Server Context: {e.response.text}")
            return None


# -----------------------
# Internal helpers
# -----------------------
def _prepare_prediction_array(values, name: str) -> np.ndarray:
    if values is None:
        raise ValueError(f"{name.capitalize()} predictions cannot be None")
    try:
        arr = np.asarray(values, dtype=float).reshape(-1)
    except Exception as exc:
        raise TypeError(f"{name.capitalize()} predictions must be numeric array-like") from exc

    if arr.size == 0:
        raise ValueError(f"{name.capitalize()} predictions cannot be empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name.capitalize()} predictions contain NaN/Inf")
    return arr


def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default