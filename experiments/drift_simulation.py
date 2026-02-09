import numpy as np
import pandas as pd

from modelshift.monitor import ModelMonitor


def generate_baseline_data(n_samples=200):
    """
    Generate baseline data representing normal behavior.
    """
    return pd.DataFrame({
        "feature_1": np.random.normal(loc=0.0, scale=1.0, size=n_samples),
        "feature_2": np.random.normal(loc=5.0, scale=1.0, size=n_samples),
    })


def generate_live_data(baseline_df, drift_strength=0.0):
    """
    Generate live data with controlled drift.
    drift_strength controls how much the distribution shifts.
    """
    live_df = baseline_df.copy()

    # Inject drift only into feature_1
    live_df["feature_1"] = (
        live_df["feature_1"] + drift_strength
    )

    return live_df


def run_drift_simulation():
    baseline_df = generate_baseline_data()

    monitor = ModelMonitor(baseline_df)

    print("Running drift simulation...\n")

    for drift_level in [0.0, 0.5, 1.0, 1.5, 2.0]:
        live_df = generate_live_data(baseline_df, drift_strength=drift_level)

        monitor.update(live_df)
        drift_results = monitor.compute_feature_drift()

        ks_value = drift_results["feature_1"]["ks_statistic"]

        print(
            f"Drift level: {drift_level:.1f} | "
            f"Feature_1 KS statistic: {ks_value:.3f}"
        )


if __name__ == "__main__":
    run_drift_simulation()
