
import pandas as pd
import joblib
from modelshift.monitor import ModelMonitor, init

print("🌐 Connecting to Public Cloud via localhost.run...")

# 1. INITIALIZE WITH PUBLIC URL
# Replace this with the NEW API key you just generated
init(
    api_key="ms_tZ1CUC-9EGhaQjR5eulCS91zWJl5cHAb", 
    dashboard_url="https://e49284b0250e95.lhr.life"
)

# 2. LOAD ARTIFACTS
model = joblib.load('cancer_model.pkl')
df_ref = pd.read_csv('cancer_reference_data.csv')
df_ref_preds = pd.read_csv('cancer_reference_preds.csv')['prediction'].values
df_live = pd.read_csv('cancer_live_data.csv')

# 3. INJECT SEVERE CALIBRATION DRIFT
print("⚠️ Injecting severe data drift into the live data...")
df_live['mean radius'] = df_live['mean radius'] * 1.8
df_live['mean area'] = df_live['mean area'] * 2.5
live_preds = model.predict(df_live)

# 4. COMPUTE & TRANSMIT
print("🚀 Computing Math and Transmitting via Public Internet...")
monitor = ModelMonitor(df_ref)
monitor.set_baseline_predictions(df_ref_preds)

monitor.update(df_live)
monitor.update_predictions(live_preds)
monitor.compute_feature_drift()
monitor.compute_prediction_drift()

# This will now beam to lhr.life, route through the internet, and land in your server!
monitor.push()
print("✅ Payload Sent!")