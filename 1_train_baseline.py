import pandas as pd
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib

print("⚙️ Loading Breast Cancer Dataset...")
data = load_breast_cancer(as_frame=True)
X = data.data
y = data.target

# Split: 70% for our "Healthy Reference", 30% for our future "Live Production"
X_ref, X_live, y_ref, y_live = train_test_split(X, y, test_size=0.3, random_state=42)

print("🧠 Training Random Forest Model...")
model = RandomForestClassifier(random_state=42)
model.fit(X_ref, y_ref)

# Get the baseline predictions so ModelShift knows what "normal" looks like
ref_preds = model.predict(X_ref)

# Save everything so our live pipeline can use it later
joblib.dump(model, 'cancer_model.pkl')
X_ref.to_csv('cancer_reference_data.csv', index=False)
pd.DataFrame({'prediction': ref_preds}).to_csv('cancer_reference_preds.csv', index=False)
X_live.to_csv('cancer_live_data.csv', index=False)

print("✅ Phase 1 Complete: Model Trained and Baseline Artifacts Saved!")