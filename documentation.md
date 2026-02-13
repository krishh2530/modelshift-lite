# ModelShift-Lite – Project Documentation

## 1. Project Overview

ModelShift-Lite is a **label-free monitoring system** designed to detect **silent performance degradation** in deployed machine learning models.  
Instead of relying on ground-truth labels or accuracy metrics, the system monitors:

- Feature distribution drift
- Prediction behavior drift
- Model uncertainty (entropy)
- Overall model health score

The core idea is to treat the ML model as a **black box** and continuously observe how its behavior changes in real-world deployment.

---

## 2. Project Structure

The project is divided into two clearly separated parts:

Final_Year_Project/
│
├── modelshift-lite/ # Core monitoring library (actual project)
│
├── Testing/ # Validation & experimentation (use-case demo)
│ ├── data/
│ │ ├── raw/
│ │ └── processed/
│ ├── preprocessing.py
│ ├── train_model.py
│ ├── drift_injection.py
│ └── run_monitoring.py
│
└── documentation.md


This separation ensures that:
- Core logic remains reusable and clean
- Experimental code does not affect the library design

---

## 3. Core Monitoring System (modelshift-lite)

The monitoring system provides the following capabilities:

### 3.1 Baseline Window
- Stores reference (training-period) data
- Used as a stable comparison point for live data

### 3.2 Feature Drift Detection
- Uses the **Kolmogorov–Smirnov (KS) test**
- Measures distribution shifts between baseline and live features
- Works without labels

### 3.3 Prediction Behavior Drift
- Monitors how model output probabilities change over time
- Uses:
  - KS-test on prediction distributions
  - Entropy to measure uncertainty increase

### 3.4 Severity Classification
- Drift values are mapped to:
  - Low
  - Medium
  - High

### 3.5 Model Health Score
- Aggregates drift signals into a single score (0–100)
- Higher score → healthier model
- Lower score → higher degradation risk

---

## 4. Real-World Validation Setup (Testing Folder)

To demonstrate real-world usage, a **Network Intrusion Detection dataset** is used.

### 4.1 Dataset
- Source: Kaggle – Network Intrusion Detection
- Size: ~47,000 samples, 42 features
- Label: `class` (normal / attack types)

All attack types are mapped to a single class:
- `normal → 0`
- `anomaly → 1`

---

## 5. Preprocessing (`preprocessing.py`)

Steps performed:

1. Load raw CSV data
2. Clean label column (case normalization, trimming)
3. Binary label conversion (normal vs anomaly)
4. One-hot encoding of categorical features:
   - protocol_type
   - service
   - flag
5. Standard scaling of numerical features
6. **Time-based split**:
   - First 60% → baseline data
   - Remaining 40% → live data

Outputs:
- `baseline.csv`
- `live.csv`

This simulates a realistic deployment timeline.

---

## 6. Model Training (`train_model.py`)

A **simple Logistic Regression model** is used to generate prediction probabilities.

Key points:
- Model simplicity is intentional
- Focus is on monitoring, not classification accuracy
- Model acts as a black box

Outputs saved:
- Trained model (`logreg_model.joblib`)
- Baseline prediction probabilities (`baseline_probs.npy`)
- Live prediction probabilities (`live_probs.npy`)

Accuracy metrics are not used for evaluation.

---

## 7. Drift Injection (`drift_injection.py`)

To simulate real-world environmental changes, controlled drift is injected into live data.

### 7.1 Types of Drift Introduced

#### Scale Drift
- Increases traffic-related features by a factor (e.g., ×1.5)
- Simulates traffic surges or abnormal load

Affected features:
- src_bytes
- dst_bytes
- count
- srv_count

#### Noise Drift
- Adds Gaussian noise to selected features
- Simulates sensor noise or logging instability

Affected features:
- duration
- srv_diff_host_rate
- dst_host_srv_count

#### Selective Drift
- Only a subset of features is modified
- Makes degradation harder to detect (silent failure)

Labels are **not modified**.

Output:
- `live_drifted.csv`

---

## 8. Experimental Goal

The goal of the validation pipeline is to demonstrate that:

- Feature drift increases after environment changes
- Prediction uncertainty increases
- Model health score degrades
- All detection is done **without labels**

This proves the effectiveness of ModelShift-Lite in real deployment scenarios.

---

## 9. Current Project Status

### Completed
- Core monitoring system
- Feature drift detection
- Prediction behavior drift
- Severity & health scoring
- Dataset preprocessing
- Model training
- Drift injection

### Next Steps
- Generate predictions on drifted data
- Run ModelShift-Lite on clean vs drifted data
- Compare degradation metrics
- (Optional) Dashboard visualization

---

## 10. Key Takeaway

ModelShift-Lite focuses on **monitoring reliability**, not model accuracy.

It provides early warning signals for silent degradation in real-world ML systems where labels are unavailable or delayed.