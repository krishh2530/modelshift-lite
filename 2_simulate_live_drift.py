import pandas as pd
import joblib
from modelshift.monitor import ModelMonitor, init

# 1. Authenticate your SDK
# REPLACE THIS WITH YOUR ACTUAL API KEY FROM THE DASHBOARD
init(api_key="ms_tZ1CUC-9EGhaQjR5eulCS91zWJl5cHAb") 

print("📥 Loading Model and Data Artifacts...")
model = joblib.load('cancer_model.pkl')
df_ref = pd.read_csv('cancer_reference_data.csv')
df_ref_preds = pd.read_csv('cancer_reference_preds.csv')['prediction'].values
df_live = pd.read_csv('cancer_live_data.csv')

# ==========================================================
# 💉 INJECTING SILENT DATA DRIFT
# Simulating a broken imaging sensor that inflates tumor sizes
# ==========================================================
print("⚠️ INJECTING CALIBRATION ERROR: Inflating 'mean radius' and 'mean area'...")
df_live['mean radius'] = df_live['mean radius'] * 1.8
df_live['mean area'] = df_live['mean area'] * 2.5

# Generate production predictions on the broken data
live_preds = model.predict(df_live)

# ==========================================================
# 🚦 MODELSHIFT: DETECT AND TRANSMIT
# ==========================================================
print("🚀 Initializing ModelShift Engine...")
monitor = ModelMonitor(df_ref)
monitor.set_baseline_predictions(df_ref_preds)

print("📊 Analyzing Live Production Data...")
monitor.update(df_live)
monitor.update_predictions(live_preds)

monitor.compute_feature_drift()
monitor.compute_prediction_drift()

print("📡 Beaming Telemetry to Cloud Dashboard...")
monitor.push()

print("✅ Pipeline Complete! Check your Dashboard and your Email Inbox.")