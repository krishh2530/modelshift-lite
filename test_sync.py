import pandas as pd
import numpy as np
from modelshift.monitor import ModelMonitor, init
#ptams16@gmai.com-ms_9rTBLpxStxAVyXRS9zFwjS1bNP_K388x
#ryomensukuna2530@gmail.com-ms_tZ1CUC-9EGhaQjR5eulCS91zWJl5cHAb Password-HelloBye@1234
# 1. AUTHENTICATE (Paste your actual API key here)
YOUR_API_KEY = "ms_YOUR_KEY_HERE"
init(api_key=YOUR_API_KEY)

print("\n[~] Generating fake ML data...")
# 2. CREATE FAKE DATA
# Reference data (what the model was trained on)
reference_df = pd.DataFrame({
    "src_bytes": [100, 150, 200, 250, 300],
    "duration": [1.2, 1.5, 1.1, 1.8, 1.3]
})
ref_preds = np.array([0.1, 0.2, 0.15, 0.8, 0.1])

# Live data (simulating a massive drift / cyber attack)
live_df = pd.DataFrame({
    "src_bytes": [9000, 8500, 9200, 8800, 9500], # Massive spike
    "duration": [1.2, 1.5, 1.1, 1.8, 1.3]        # Normal
})
live_preds = np.array([0.9, 0.85, 0.95, 0.99, 0.88])

# 3. RUN THE ENGINE
print("[~] Running ModelShift Drift Engine...")
monitor = ModelMonitor(reference_df)
monitor.set_baseline_predictions(ref_preds)

monitor.update(live_df)
monitor.update_predictions(live_preds)

monitor.compute_feature_drift()
monitor.compute_prediction_drift()

# 4. BEAM IT TO THE CLOUD
print("[~] Attempting Cloud Sync...")
monitor.push()