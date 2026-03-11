import numpy as np
import pandas as pd

from modelshift.monitor import ModelMonitor


def test_monitor_end_to_end_smoke():
    base = pd.DataFrame({"f1": np.arange(200), "f2": np.arange(200) * 2})
    live = base.copy()

    base_probs = np.linspace(0.05, 0.95, 200)
    live_probs = base_probs.copy()

    mon = ModelMonitor(base)

    # Feature drift path
    mon.update(live)
    fd = mon.compute_feature_drift()
    assert fd is not None

    # Prediction drift path
    mon.set_baseline_predictions(base_probs)
    mon.update_predictions(live_probs)
    pd_ = mon.compute_prediction_drift()
    assert pd_ is not None

    # Health path
    hs = mon.get_model_health_score()
    assert hs is not None