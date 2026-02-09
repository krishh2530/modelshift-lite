import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from modelshift.monitor import ModelMonitor


def generate_baseline_data(n_samples=200):
    return pd.DataFrame({
        "feature_1": np.random.normal(loc=0.0, scale=1.0, size=n_samples),
        "feature_2": np.random.normal(loc=5.0, scale=1.0, size=n_samples),
    })


def generate_live_data(baseline_df, drift_strength=0.0):
    live_df = baseline_df.copy()
    live_df["feature_1"] = live_df["feature_1"] + drift_strength
    return live_df


def run_drift_simulation():
    baseline_df = generate_baseline_data()
    monitor = ModelMonitor(baseline_df)

    drift_levels = [0.0, 0.5, 1.0, 1.5, 2.0]
    ks_values = []

    print("Running drift simulation...\n")

    for drift_level in drift_levels:
        live_df = generate_live_data(baseline_df, drift_strength=drift_level)

        monitor.update(live_df)
        drift_results = monitor.compute_feature_drift()

        ks_stat = drift_results["feature_1"]["ks_statistic"]
        ks_values.append(ks_stat)

        print(
            f"Drift level: {drift_level:.1f} | "
            f"Feature_1 KS statistic: {ks_stat:.3f}"
        )

    # Plot drift sensitivity curve
    plt.figure()
    plt.plot(drift_levels, ks_values, marker="o")
    plt.xlabel("Injected Drift Level")
    plt.ylabel("KS Statistic (Feature_1)")
    plt.title("Drift Sensitivity Curve for Feature_1")
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    run_drift_simulation()
