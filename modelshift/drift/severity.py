from __future__ import annotations

from typing import Any, Dict, List, Optional


# ----------------------------
# Basic per-signal thresholds
# ----------------------------
FEATURE_KS_LOW = 0.10
FEATURE_KS_MEDIUM = 0.20
FEATURE_KS_HIGH = 0.35

PRED_KS_WARNING = 0.10
PRED_KS_CRITICAL = 0.15

ENTROPY_DELTA_WARNING = 0.01
ENTROPY_DELTA_CRITICAL = 0.02


def classify_severity(ks_statistic: float) -> str:
    """
    Classify severity from a KS-like drift signal.

    Returns one of:
      LOW / MEDIUM / HIGH / CRITICAL
    """
    ks = _safe_float(ks_statistic, default=0.0)
    if ks < FEATURE_KS_LOW:
        return "LOW"
    if ks < FEATURE_KS_MEDIUM:
        return "MEDIUM"
    if ks < FEATURE_KS_HIGH:
        return "HIGH"
    return "CRITICAL"


def compute_health_score(feature_drift_results: dict) -> float:
    """
    Compute overall model health score (0–100) from feature drift.
    Higher score = healthier model.

    Uses average feature KS:
      health = max(0, 100 * (1 - avg_ks))
    """
    summary = summarize_feature_drift(feature_drift_results)
    if summary["feature_count"] == 0:
        raise ValueError("Feature drift results cannot be empty")

    avg_ks = summary["avg_ks"]
    health_score = max(0.0, 100.0 * (1.0 - avg_ks))
    return round(float(health_score), 2)


def summarize_feature_drift(feature_drift_results: Optional[dict]) -> Dict[str, Any]:
    """
    Extract feature drift summary stats from feature_drift_results.
    Safe against missing/malformed values.
    """
    if not isinstance(feature_drift_results, dict):
        return {
            "feature_count": 0,
            "avg_ks": 0.0,
            "max_ks": 0.0,
            "max_feature": None,
            "ks_values": [],
        }

    ks_pairs: List[tuple[str, float]] = []
    for feature, values in feature_drift_results.items():
        if not isinstance(values, dict):
            continue
        ks = _safe_float(values.get("ks_statistic"), default=None)
        if ks is None:
            continue
        ks_pairs.append((str(feature), ks))

    if not ks_pairs:
        return {
            "feature_count": 0,
            "avg_ks": 0.0,
            "max_ks": 0.0,
            "max_feature": None,
            "ks_values": [],
        }

    ks_values = [ks for _, ks in ks_pairs]
    max_feature, max_ks = max(ks_pairs, key=lambda x: x[1])

    return {
        "feature_count": len(ks_values),
        "avg_ks": round(sum(ks_values) / len(ks_values), 6),
        "max_ks": round(float(max_ks), 6),
        "max_feature": max_feature,
        "ks_values": [round(float(v), 6) for v in ks_values],
    }


def classify_drift_taxonomy(
    feature_drift_results: Optional[dict] = None,
    prediction_drift_results: Optional[dict] = None,
) -> str:
    """
    Agreement/disagreement taxonomy between feature drift and prediction drift.

    Returns one of:
      STABLE
      ROBUST_SHIFT              (feature drift high, prediction drift low)
      SILENT_BEHAVIOR_DRIFT     (feature drift low, prediction drift high)
      DEGRADING_DRIFT           (both high)
    """
    f_summary = summarize_feature_drift(feature_drift_results)
    max_feature_ks = _safe_float(f_summary.get("max_ks"), default=0.0)

    pred_ks = 0.0
    if isinstance(prediction_drift_results, dict):
        pred_ks = _safe_float(prediction_drift_results.get("ks_statistic"), default=0.0)

    feature_high = max_feature_ks >= FEATURE_KS_MEDIUM
    pred_high = pred_ks >= PRED_KS_WARNING

    if not feature_high and not pred_high:
        return "STABLE"
    if feature_high and not pred_high:
        return "ROBUST_SHIFT"
    if (not feature_high) and pred_high:
        return "SILENT_BEHAVIOR_DRIFT"
    return "DEGRADING_DRIFT"


def evaluate_drift_state(
    feature_drift_results: Optional[dict] = None,
    prediction_drift_results: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Composite severity + status decision engine.

    Combines:
    - avg feature KS
    - max feature KS
    - prediction KS
    - entropy delta

    Returns a normalized decision payload with:
      severity, status, taxonomy, health_score, signals, thresholds
    """
    f_summary = summarize_feature_drift(feature_drift_results)

    avg_feature_ks = _safe_float(f_summary.get("avg_ks"), default=0.0)
    max_feature_ks = _safe_float(f_summary.get("max_ks"), default=0.0)
    pred_ks = 0.0
    entropy_change = 0.0

    if isinstance(prediction_drift_results, dict):
        pred_ks = _safe_float(prediction_drift_results.get("ks_statistic"), default=0.0)
        entropy_change = _safe_float(prediction_drift_results.get("entropy_change"), default=0.0)

    # Normalize signals into 0..1 severity components
    # (Threshold denominators chosen to align with your current observed ranges.)
    avg_comp = min(1.0, avg_feature_ks / FEATURE_KS_MEDIUM)           # avg drift
    max_comp = min(1.0, max_feature_ks / FEATURE_KS_HIGH)             # worst feature
    pred_comp = min(1.0, pred_ks / PRED_KS_CRITICAL)                  # behavior drift
    ent_comp = min(1.0, abs(entropy_change) / ENTROPY_DELTA_CRITICAL) # confidence shift

    # Weighted composite score [0,1]
    composite_score = (
        0.30 * avg_comp +
        0.25 * max_comp +
        0.35 * pred_comp +
        0.10 * ent_comp
    )

    severity = _classify_composite_severity(composite_score)

    # Status favors prediction drift a bit more (behavior-centric monitoring)
    if pred_ks >= PRED_KS_CRITICAL or max_feature_ks >= FEATURE_KS_HIGH:
        status = "CRITICAL_DRIFT"
    elif pred_ks >= PRED_KS_WARNING or max_feature_ks >= FEATURE_KS_MEDIUM or avg_feature_ks >= FEATURE_KS_LOW:
        status = "WARNING_DRIFT"
    else:
        status = "STABLE"

    taxonomy = classify_drift_taxonomy(feature_drift_results, prediction_drift_results)

    # Health score is only meaningful if feature drift exists
    health_score = None
    if f_summary["feature_count"] > 0:
        health_score = compute_health_score(feature_drift_results)

    return {
        "severity": severity,
        "status": status,
        "taxonomy": taxonomy,
        "health_score": health_score,
        "signals": {
            "avg_feature_ks": round(avg_feature_ks, 6),
            "max_feature_ks": round(max_feature_ks, 6),
            "max_feature_name": f_summary.get("max_feature"),
            "prediction_ks": round(pred_ks, 6),
            "entropy_change": round(entropy_change, 6),
            "composite_score": round(float(composite_score), 6),
            "feature_count": int(f_summary.get("feature_count", 0)),
        },
        "thresholds": {
            "feature_ks_low": FEATURE_KS_LOW,
            "feature_ks_medium": FEATURE_KS_MEDIUM,
            "feature_ks_high": FEATURE_KS_HIGH,
            "pred_ks_warning": PRED_KS_WARNING,
            "pred_ks_critical": PRED_KS_CRITICAL,
            "entropy_delta_warning": ENTROPY_DELTA_WARNING,
            "entropy_delta_critical": ENTROPY_DELTA_CRITICAL,
        },
    }


# ----------------------------
# Internal helpers
# ----------------------------
def _classify_composite_severity(score: float) -> str:
    """
    Composite score is already normalized 0..1.
    """
    s = max(0.0, min(1.0, _safe_float(score, default=0.0)))

    if s < 0.20:
        return "LOW"
    if s < 0.45:
        return "MEDIUM"
    if s < 0.70:
        return "HIGH"
    return "CRITICAL"


def _safe_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default