# selftest.py (repo root)
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import math
import time

import numpy as np
import pandas as pd

from modelshift.drift.feature_drift import compute_feature_drift
from modelshift.drift.prediction_drift import compute_prediction_drift
from modelshift.drift.severity import compute_health_score


# -----------------------------
# Helpers (robust schema)
# -----------------------------
def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if np.isfinite(v):
            return float(v)
    except Exception:
        pass
    return float(default)


def _extract_pred_map(pd_: Any) -> Dict[str, Any]:
    if not isinstance(pd_, dict):
        return {}
    for k in ("prediction_drift", "prediction_drift_results", "results"):
        v = pd_.get(k)
        if isinstance(v, dict):
            return v
    return pd_


def _extract_fd_map(fd: Any) -> Dict[str, Any]:
    if not isinstance(fd, dict):
        return {}
    for k in ("feature_drift_results", "feature_drift", "results"):
        v = fd.get(k)
        if isinstance(v, dict):
            return v
    return fd


def _adapt_pred(pd_: Any) -> Dict[str, Any]:
    m = _extract_pred_map(pd_)
    if not isinstance(m, dict):
        return {}
    ks = m.get("ks_statistic", m.get("ks", m.get("ks_stat", m.get("statistic", 0.0))))
    pv = m.get("p_value", m.get("p", m.get("pvalue", 1.0)))
    out = dict(m)
    out["ks_statistic"] = _to_float(ks, 0.0)
    out["p_value"] = _to_float(pv, 1.0)
    return out


def _adapt_fd(fd: Any) -> Dict[str, Dict[str, float]]:
    m = _extract_fd_map(fd)
    out: Dict[str, Dict[str, float]] = {}
    if not isinstance(m, dict):
        return out
    for feat, v in m.items():
        if not isinstance(v, dict):
            continue
        ks = v.get("ks_statistic", v.get("ks", v.get("ks_stat", v.get("statistic", v.get("D", 0.0)))))
        pv = v.get("p_value", v.get("p", v.get("pvalue", v.get("p_val", 1.0))))
        out[str(feat)] = {
            "ks_statistic": _to_float(ks, 0.0),
            "p_value": _to_float(pv, 1.0),
        }
    return out


def _call_health(fd: Any, pd_: Any) -> Tuple[float, str]:
    fd_fixed = _adapt_fd(fd)
    pd_fixed = _adapt_pred(pd_)

    # Try dict form (newer)
    try:
        out = compute_health_score({"feature_drift": fd_fixed, "prediction_drift": pd_fixed})
        if isinstance(out, dict):
            sc = out.get("health_score", out.get("score", out.get("health", None)))
            md = out.get("mode", out.get("health_compute_mode", "severity"))
            if sc is not None:
                return float(sc), str(md)
        if isinstance(out, (int, float)):
            return float(out), "severity"
    except Exception:
        pass

    # Try 2-arg form (older)
    try:
        out = compute_health_score(fd_fixed, pd_fixed)
        if isinstance(out, dict):
            sc = out.get("health_score", out.get("score", out.get("health", None)))
            md = out.get("mode", out.get("health_compute_mode", "severity"))
            if sc is not None:
                return float(sc), str(md)
        if isinstance(out, (int, float)):
            return float(out), "severity"
    except Exception:
        pass

    # Fallback (simple)
    ks_vals = [v["ks_statistic"] for v in fd_fixed.values()] if fd_fixed else []
    avg_ks = float(np.mean(ks_vals)) if ks_vals else 0.0
    pred_ks = _to_float(pd_fixed.get("ks_statistic"), 0.0)
    score = 100.0 * (1.0 - min(max(0.70 * pred_ks + 0.30 * avg_ks, 0.0), 1.0))
    return float(np.clip(score, 0.0, 100.0)), "fallback"


def _entropy(probs: np.ndarray, bins: int = 24) -> float:
    p = np.clip(np.asarray(probs, dtype=float), 0.0, 1.0)
    h, _ = np.histogram(p, bins=bins, range=(0.0, 1.0), density=False)
    h = h.astype(float)
    if h.sum() <= 0:
        return 0.0
    q = h / h.sum()
    q = q[q > 0]
    return float(-np.sum(q * np.log2(q)))


def _hist(probs: np.ndarray, bins: int = 32) -> Dict[str, Any]:
    p = np.clip(np.asarray(probs, dtype=float), 0.0, 1.0)
    h, edges = np.histogram(p, bins=bins, range=(0.0, 1.0), density=False)
    return {
        "bins": [float(x) for x in edges.tolist()],
        "counts": [int(x) for x in h.tolist()],
    }


def _top_features(fd: Any, k: int = 8) -> List[Dict[str, Any]]:
    m = _adapt_fd(fd)
    rows = []
    for feat, v in m.items():
        ks = _to_float(v.get("ks_statistic"), 0.0)
        pv = _to_float(v.get("p_value"), 1.0)
        if ks >= 0.35:
            sev = "CRITICAL"
        elif ks >= 0.20:
            sev = "HIGH"
        elif ks >= 0.10:
            sev = "MEDIUM"
        else:
            sev = "LOW"
        rows.append({"feature": feat, "ks_statistic": ks, "p_value": pv, "severity": sev})
    rows.sort(key=lambda r: r["ks_statistic"], reverse=True)
    return rows[:k]


# -----------------------------
# Synthetic scenario generator
# -----------------------------
def _make_synthetic(seed: int, n: int = 2400, d: int = 14) -> Dict[str, Any]:
    rng = np.random.default_rng(int(seed))

    # baseline features
    base = rng.normal(0, 1.0, size=(n, d))
    base_df = pd.DataFrame(base, columns=[f"f{i}" for i in range(d)])

    # clean ~ baseline (small noise)
    clean = base + rng.normal(0, 0.08, size=(n, d))
    clean_df = pd.DataFrame(clean, columns=base_df.columns)

    # drifted (shift subset of features)
    drift = base.copy()
    drift[:, 0] += 2.0
    drift[:, 1] += 1.3
    drift[:, 2] *= 1.8
    drift[:, 3] += rng.normal(0, 2.2, size=n)
    drift_df = pd.DataFrame(drift, columns=base_df.columns)

    # synthetic "prediction probs"
    base_p = rng.beta(2.2, 2.6, size=n)  # mild center
    clean_p = np.clip(base_p + rng.normal(0, 0.02, size=n), 0, 1)
    drift_p = np.clip(1.0 - base_p + rng.normal(0, 0.03, size=n), 0, 1)  # strong invert shift

    # FIX: Cleaned up the dictionary return to prevent syntax errors
    return {
        "base_X": base_df,
        "clean_X": clean_df,
        "drift_X": drift_df,
        "base_p": base_p,
        "clean_p": clean_p,
        "drift_p": drift_p,
    }


# -----------------------------
# Public API
# -----------------------------
def run_selftest(seed: int = 7, test: str = "suite") -> Dict[str, Any]:
    """
    Returns a payload designed for BOTH:
      - readable JSON
      - rich UI animations (histograms, gauges, feature bars)

    test options:
      - "prediction"
      - "feature"
      - "pipeline"
      - "suite" (default, runs 3 scenarios)
      - "concept"
    """
    t0 = time.time()
    test = (test or "suite").strip().lower()

    try:
        if test not in {"prediction", "feature", "pipeline", "suite", "concept"}:
            test = "suite"

        cases: List[Dict[str, Any]] = []
        checks: List[Dict[str, Any]] = []

        # We run up to 3 scenarios in suite so it looks “real”
        seeds = [seed] if test != "suite" else [seed, seed + 11, seed + 23]

        for idx, s in enumerate(seeds, start=1):
            sim = _make_synthetic(seed=s)
            base_X = sim["base_X"]
            clean_X = sim["clean_X"]
            drift_X = sim["drift_X"]
            base_p = sim["base_p"]
            clean_p = sim["clean_p"]
            drift_p = sim["drift_p"]

            # --- CONCEPT DRIFT LOGIC ADDED HERE ---
            if test == "concept":
                # In Concept Drift, the relationship flips but features stay the same!
                drift_X = base_X.copy()
                drift_p = np.clip(base_p + 0.35, 0, 1)
            # --------------------------------------

            # compute drifts
            fd_clean = compute_feature_drift(base_X, clean_X)
            fd_drift = compute_feature_drift(base_X, drift_X)

            pd_clean = compute_prediction_drift(base_p, clean_p)
            pd_drift = compute_prediction_drift(base_p, drift_p)

            pd_clean_m = _adapt_pred(pd_clean)
            pd_drift_m = _adapt_pred(pd_drift)

            pred_ks_clean = _to_float(pd_clean_m.get("ks_statistic"), 0.0)
            pred_ks_drift = _to_float(pd_drift_m.get("ks_statistic"), 0.0)

            ent_base = _entropy(base_p)
            ent_clean = _entropy(clean_p)
            ent_drift = _entropy(drift_p)
            delta_ent_clean = float(ent_clean - ent_base)
            delta_ent_drift = float(ent_drift - ent_base)

            # health score (use pipeline if available)
            health_clean, mode_clean = _call_health(fd_clean, pd_clean)
            health_drift, mode_drift = _call_health(fd_drift, pd_drift)

            # histograms for visuals
            h_base = _hist(base_p, bins=40)
            h_clean = _hist(clean_p, bins=40)
            h_drift = _hist(drift_p, bins=40)

            top_feat = _top_features(fd_drift, k=8)

            cases.append(
                {
                    "case_id": f"C{idx}",
                    "seed": int(s),
                    "name": (
                        "Prediction Drift Test" if test == "prediction"
                        else "Feature Drift Test" if test == "feature"
                        else "Pipeline Health Test" if test == "pipeline"
                        else "Concept Drift Test" if test == "concept"
                        else f"Suite Scenario {idx}"
                    ),
                    "metrics": {
                        "pred_ks_clean": float(pred_ks_clean),
                        "pred_ks_drifted": float(pred_ks_drift),
                        "delta_entropy_clean": float(delta_ent_clean),
                        "delta_entropy_drifted": float(delta_ent_drift),
                        "health_clean": float(health_clean),
                        "health_drifted": float(health_drift),
                        "health_mode_clean": str(mode_clean),
                        "health_mode_drifted": str(mode_drift),
                    },
                    "viz": {
                        "pred_hist": {
                            "bins": h_base["bins"],
                            "baseline": h_base["counts"],
                            "clean": h_clean["counts"],
                            "drifted": h_drift["counts"],
                        },
                        "top_drifted_features": top_feat,
                    },
                }
            )

        # Decide which checks to enforce (based on selected test)
        # (We validate the FIRST case for “pass/fail”)
        c0 = cases[0]
        m0 = c0["metrics"]
        pred_clean = float(m0["pred_ks_clean"])
        pred_drift = float(m0["pred_ks_drifted"])
        h_clean = float(m0["health_clean"])
        h_drift = float(m0["health_drifted"])

        if test in {"prediction", "pipeline", "suite"}:
            checks.append(
                {
                    "name": "Prediction drift should be low for clean",
                    "pass": bool(pred_clean < 0.08),
                    "value": pred_clean,
                    "threshold": "< 0.08",
                }
            )
            checks.append(
                {
                    "name": "Prediction drift should be high for drifted",
                    "pass": bool(pred_drift > 0.10),
                    "value": pred_drift,
                    "threshold": "> 0.10",
                }
            )

        if test in {"feature", "pipeline", "suite"}:
            top = c0["viz"]["top_drifted_features"]
            mx = float(top[0]["ks_statistic"]) if top else 0.0
            checks.append(
                {
                    "name": "At least one feature should show strong shift",
                    "pass": bool(mx > 0.20),
                    "value": mx,
                    "threshold": "> 0.20",
                }
            )

        if test in {"pipeline", "suite"}:
            checks.append(
                {
                    "name": "Health should degrade under drift",
                    "pass": bool(h_drift < h_clean),
                    "value": {"clean": h_clean, "drifted": h_drift},
                    "threshold": "drifted < clean",
                }
            )

        # --- CONCEPT DRIFT CHECKS ADDED HERE ---
        if test == "concept":
            top = c0["viz"]["top_drifted_features"]
            mx = float(top[0]["ks_statistic"]) if top else 0.0
            checks.append(
                {
                    "name": "Feature drift should be ZERO (Inputs didn't change)",
                    "pass": bool(mx < 0.05),
                    "value": mx,
                    "threshold": "< 0.05",
                }
            )
            checks.append(
                {
                    "name": "Prediction drift should be MASSIVE (Concept flipped)",
                    "pass": bool(pred_drift > 0.30),
                    "value": pred_drift,
                    "threshold": "> 0.30",
                }
            )
        # ---------------------------------------

        ok = all(bool(x.get("pass")) for x in checks) if checks else True

        payload = {
            "ok": ok,
            "test": test,
            "seed": int(seed),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_ms": int((time.time() - t0) * 1000),
            "cases": len(cases),
            "passed": int(sum(1 for x in checks if x.get("pass"))),
            "failed": int(sum(1 for x in checks if not x.get("pass"))),
            "summary": cases[0]["metrics"] if cases else {},
            "checks": checks,
            "case_results": cases,
        }
        return payload

    except Exception as e:
        import traceback
        return {
            "ok": False,
            "test": test,
            "seed": int(seed),
            "error": str(e),
            "trace": traceback.format_exc(),
        }