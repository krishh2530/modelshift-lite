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

Validation Using a Real ML Model and Controlled Drift Injection

To validate the proposed monitoring framework in a realistic deployment scenario, we tested ModelShift-Lite using a basic machine learning model trained with Logistic Regression on a network intrusion dataset. Logistic Regression was deliberately chosen due to its simplicity, interpretability, and widespread use in real-world systems, allowing the focus to remain on monitoring behavior rather than model complexity. After training the model on baseline data, prediction probabilities were generated for both baseline and live data. To simulate post-deployment environmental changes, controlled and explainable drifts were injected into the live data without retraining the model. These drifts included scale drift on traffic-related features (to represent increased network load), noise drift on selected temporal features (to mimic sensor and logging instability), and selective drift affecting only a subset of features to model silent degradation scenarios. Such drift types were chosen because they commonly occur in deployed systems and are subtle enough to degrade model behavior without immediately triggering accuracy alarms. This setup enables the evaluation of ModelShift-Lite’s ability to detect silent performance degradation in a label-free and model-agnostic manner.

---

## 11. Major Progress Update (Post Initial Documentation)

After the initial documentation phase, the project moved from a conceptual/standalone drift-monitoring prototype to a **fully integrated end-to-end validation pipeline** with:

- Real model predictions
- Controlled drift simulation
- Dashboard-ready data export
- Historical run tracking
- Automated HTML report generation
- Decision engine output (severity + taxonomy + root-cause candidates)

This section documents all major additions and the exact logic now implemented.

---

## 12. End-to-End Validation Pipeline (Completed)

The project now supports a full execution flow from raw processed data to dashboard visualization:

1. **Preprocess data**
2. **Train a Logistic Regression model**
3. **Inject controlled drift into live data**
4. **Export drift analysis + metrics into dashboard JSON format**
5. **Visualize results in the web dashboard**

### 12.1 Current Pipeline Scripts (Testing Folder)

The `Testing/` folder now contains the following operational pipeline scripts:

- `preprocessing.py`
- `train_model.py`
- `drift_injection.py`
- `export_dashboard_data.py`

Each file performs a specific stage in the validation workflow.

---

## 13. `export_dashboard_data.py` (Core Integration Layer)

This is the most important integration script added after the original documentation. It bridges the `Testing` pipeline and the `modelshift-lite` dashboard.

### 13.1 Purpose

`export_dashboard_data.py` does all of the following in one run:

- Loads baseline, clean live, and drifted live datasets
- Loads the trained model (`logreg_model.joblib`)
- Generates prediction probabilities
- Computes feature drift and prediction drift
- Computes health scores
- Computes window-wise health trends (for graph plotting)
- Computes evaluation metrics (when labels are usable)
- Builds decision engine output
- Builds root-cause candidates (top drifted features)
- Exports a dashboard-compatible JSON payload
- Stores historical runs and updates `latest.json` / `previous.json`
- Generates an HTML report artifact

This script effectively converts the project into a **reproducible monitoring system demo**.

---

## 14. Robust Path Handling and Project Structure Integration

A major enhancement was making the exporter robust to **current working directory (CWD)** differences.

### 14.1 Path Resolution Logic

The exporter now resolves paths relative to the script location:

- `THIS_DIR` → `Testing/`
- `PROJECT_DIR` → parent of `Testing/`
- `MODEL_SHIFT_LITE_DIR` → `Final_Year_Project/modelshift-lite`

This prevents path errors when running the script from different terminals/folders.

### 14.2 Dashboard Output Paths

Exported files are written into:

- `modelshift-lite/dashboard_web/data/latest.json`
- `modelshift-lite/dashboard_web/data/previous.json`
- `modelshift-lite/dashboard_web/data/history_index.json`
- `modelshift-lite/dashboard_web/data/report_latest.html`
- `modelshift-lite/dashboard_web/data/runs/<RUN_ID>.json`
- `modelshift-lite/dashboard_web/data/runs/<RUN_ID>.report.html`

This allows the dashboard to always read the latest results automatically.

---

## 15. Data Loading and Label Handling Improvements

### 15.1 Feature + Label Extraction

The exporter loads CSVs and automatically detects a label column from common names such as:

- `label`
- `target`
- `class`
- `y`
- `attack`
- `attack_type`

If a label is found:
- It is separated and preserved for evaluation metrics.
- Features are kept independent for drift analysis.

### 15.2 Numeric-Only Feature Drift Input

For drift detection, only numeric columns are retained.

Additional safeguards:
- Infinite values are replaced
- NaN values are filled
- Data is kept stable for drift computations

### 15.3 Why This Matters

This makes the pipeline robust across different datasets and prevents drift functions from crashing on:
- String labels
- Missing values
- Mixed-type columns

---

## 16. Model Alignment and Prediction Pipeline

### 16.1 Feature Alignment to Trained Model

A very important issue solved during integration was **feature mismatch** between the model and exported datasets.

If the model exposes `feature_names_in_`, the exporter now:

- Forces all datasets to match the model’s expected columns
- Fills missing columns with `0.0`
- Reorders columns exactly to match training-time order

If the model does not expose feature names, the script falls back to a **union-column alignment** between frames.

### 16.2 Prediction Probability Extraction

The exporter supports multiple model types by trying:

1. `predict_proba()` → preferred (binary probability column used)
2. `decision_function()` → converted to probability via sigmoid
3. `predict()` → fallback

This makes the exporter reusable beyond Logistic Regression.

---

## 17. Drift Detection Logic (Now Fully Wired to Real Predictions)

ModelShift-Lite monitors two independent drift channels:

### 17.1 Feature Drift

Feature drift is computed between:

- Baseline features vs clean live features
- Baseline features vs drifted live features

This is performed using:

- `compute_feature_drift(...)`

Each feature receives a drift result (including KS statistic and p-value after schema normalization).

### 17.2 Prediction Drift

Prediction drift is computed between:

- Baseline prediction probabilities vs clean live prediction probabilities
- Baseline prediction probabilities vs drifted prediction probabilities

This is performed using:

- `compute_prediction_drift(...)`

This captures **behavior shift of the model output distribution**, even when labels are unavailable.

---

## 18. Health Score Computation (Robust + Version-Tolerant)

### 18.1 Health Score API Compatibility Handling

Different versions of the drift/severity functions may return slightly different schemas.  
To make the pipeline stable, the exporter now includes adapters that:

- Normalize feature drift schema keys
- Normalize prediction drift schema keys
- Accept multiple output formats from `compute_health_score(...)`

### 18.2 Fallback Health Score Logic

If the built-in health scoring function fails due to schema mismatch or signature mismatch, the exporter computes a safe fallback:

- Uses average KS drift from feature drift
- Converts drift magnitude to a 0–100 health score

Fallback concept:
- Higher KS drift ⇒ lower health score

This guarantees that the dashboard will still show values even when library interfaces vary.

---

## 19. Windowed Health Monitoring (Time-Series / Graph Support)

A major enhancement for the dashboard was adding **window-wise health computation** to generate trend graphs.

### 19.1 Why Windowing Was Added

Instead of a single drift number, the dashboard needs a trend over time/windows to show:

- How health changes across the live stream
- Whether drift is gradual or sudden
- Whether drift severity is stable or oscillating

### 19.2 Windowing Method

- Live data is split into windows (default size = 500 rows)
- For each window:
  - Feature drift is computed vs baseline
  - Prediction drift is computed vs baseline predictions
  - Health score is computed
- Result is stored as a wave/series

The exported payload now includes:

- `series.x`
- `series.clean_health`
- `series.drifted_health`

These are used directly by the frontend charts.

---

## 20. Drift Status Classification Logic (CLEAN / WARNING / CRITICAL)

A clear rule-based status system was added for dashboard display.

### 20.1 Current Status Rule

The dashboard status is currently derived from **prediction drift KS** using thresholds:

- `CRITICAL_DRIFT` if KS ≥ **0.15**
- `WARNING_DRIFT` if KS ≥ **0.10**
- `CLEAN` otherwise

This gives a simple and explainable status label for presentations.

---

## 21. Decision Engine (New Advanced Output)

A new `decision` block is now exported to support richer dashboard interpretation.

### 21.1 What the Decision Engine Outputs

It generates:

- `status`
- `severity`
- `taxonomy`
- `signals` (detailed intermediate values)

### 21.2 Signals Used

The decision engine computes:

- Average feature KS
- Maximum feature KS
- Prediction KS
- Entropy change
- Composite score
- Top signal feature name
- Feature count
- Clean health and drifted health

### 21.3 Composite Score Formula

A weighted composite score is computed using:

- **55%** max feature KS
- **35%** prediction KS
- **10%** absolute entropy change

Formula:

`composite_score = 0.55 * max_feature_ks + 0.35 * prediction_ks + 0.10 * |entropy_change|`

This allows the dashboard/report to summarize drift severity using a single explainable number.

### 21.4 Severity Mapping (Decision Block)

Decision severity is determined from status and drift signals:

- If status is `CRITICAL_DRIFT` → severity = `CRITICAL`
- If status is `WARNING_DRIFT` → severity = `MEDIUM`
- Else fallback based on max(feature KS, prediction KS):
  - ≥ 0.35 → `HIGH`
  - ≥ 0.20 → `MEDIUM`
  - ≥ 0.10 → `LOW`
  - otherwise → `STABLE`

### 21.5 Drift Taxonomy (Interpretation Layer)

The decision engine also classifies the type of shift:

- `FEATURE_SHIFT + PREDICTION_SHIFT`
- `FEATURE_SHIFT`
- `PREDICTION_SHIFT`
- `NO_SIGNIFICANT_SHIFT`

This makes the result easier to explain in demos/interviews.

---

## 22. Root Cause Candidates (Top Drifted Features)

A major improvement was the addition of a root-cause style panel.

### 22.1 What It Does

The exporter now builds a ranked list of the most drifted features using the feature KS statistics.

The payload includes:

- `top_drifted_features` (Top 8 by default)

Each row contains:
- Feature name
- KS statistic
- p-value
- Severity label

### 22.2 Root-Cause Severity per Feature

Feature severity is assigned using KS thresholds:

- KS ≥ 0.35 → `CRITICAL`
- KS ≥ 0.20 → `HIGH`
- KS ≥ 0.10 → `MEDIUM`
- Else → `LOW`

This improves interpretability and helps identify *which inputs likely caused the shift*.

---

## 23. Evaluation Metrics (Label-Aware, Safe, and Dashboard-Compatible)

After the original documentation, evaluation metrics were fully integrated into the exporter.

### 23.1 When Metrics Are Computed

Metrics are computed if labels are present and can be normalized to a binary format.

Supported binary label variants include:
- `{0,1}`
- `{-1,1}`
- `{1,2}`
- Generic 2-class numeric labels
- 2-class string labels

### 23.2 Metrics Now Exported

For each applicable dataset (`baseline`, `clean`, `drifted`), the exporter can compute:

- Accuracy
- Precision
- Recall
- F1-score
- ROC-AUC (only when both classes are present)
- MSE (Brier-style: probabilities vs labels)
- RMSE
- R² (on probabilities vs labels; included for dashboard compatibility)
- Log Loss
- Confusion Matrix (`tn`, `fp`, `fn`, `tp`)

### 23.3 Important Note About MSE and R²

Since this is a classification task using probabilities:

- **MSE** is interpreted as a **Brier score-style** probability error
- **R²** is included only because the UI expects it and should be interpreted cautiously

### 23.4 Handling Single-Class Label Issues (Important Fix)

A common real-world issue occurred during testing:

- Some live/drifted label sets contained only one class (e.g., all `1`s)

In that case:
- ROC-AUC is mathematically undefined
- Many evaluation metrics become misleading

To prevent failures, the exporter now returns a structured note like:

- `task: single_class_labels`
- Reason + explanation message

This is why you may see:
- `ROC-AUC = nan` in training sanity checks
- but a clean message in exported dashboard evaluation instead of a crash

This behavior is expected and correctly handled.

---

## 24. Dashboard Payload Schema (Version 2)

The exporter now outputs a structured payload with `schema_version = 2`.

### 24.1 Major Payload Sections

- `run_id`
- `generated_at`
- `window_size`
- `status`
- `series`
- `summary`
- `decision`
- `monitor_decision` (alias for compatibility)
- `top_drifted_features`
- `feature_drift`
- `prediction_drift`
- `prediction_drift_last_window`
- `evaluation`
- `proof`
- `payload_hash`
- `series_hash`

### 24.2 Why This Was Added

This schema allows the frontend to render:

- Health trend graphs
- Current and previous run metrics
- Decision/severity panels
- Root-cause candidate tables
- Evaluation metric tables
- Historical run comparisons

without recomputing anything in the browser.

---

## 25. Run History, Latest/Previous Tracking, and Report Generation

### 25.1 Historical Run Archiving

Each export run is archived as:

- `dashboard_web/data/runs/<RUN_ID>.json`

This preserves a time-stamped history of model monitoring snapshots.

### 25.2 Latest and Previous Run Pointers

The exporter automatically updates:

- `latest.json` → newest run
- `previous.json` → second newest run (if available)

This enables direct **current vs previous** comparisons in the dashboard.

### 25.3 History Index for UI

The script also generates:

- `history_index.json`

This contains a lightweight summary of recent runs:
- Status
- Health scores
- Prediction drift KS
- Entropy change
- Top drifted feature
- Severity/taxonomy
- Timestamps

Useful for the dashboard history tab and trend navigation.

### 25.4 Auto HTML Report Generation

The exporter now generates a readable HTML report for each run:

- `runs/<RUN_ID>.report.html`
- `report_latest.html`

This report includes:
- Latest summary
- Previous summary
- Decision engine table
- Root-cause candidates
- Evaluation metrics (latest + previous)

This is useful for:
- Demo screenshots
- Sharing progress with teammates
- Offline review

---

## 26. Frontend/Data Rendering Progress (High-Level)

Although frontend visuals are not the main focus, the backend-export pipeline is now aligned with dashboard needs.

### 26.1 Values Now Available in UI

The dashboard can now display:

- Clean vs drifted health waves
- Latest and previous summaries
- Status labels (`CLEAN`, `WARNING_DRIFT`, `CRITICAL_DRIFT`)
- Evaluation metrics table
- Decision engine details
- Top drifted features
- Historical run list

### 26.2 Previous Run Values Showing Same as Current (Observed Behavior)

During testing, a case was observed where current and previous scores looked identical.

This can happen if:
- Only one run exists (so previous is missing)
- The same export data was generated twice without changes
- Clean/drifted inputs and model remained unchanged between two exports

This is not necessarily a bug. To see different previous/current values:
- Run a clean export once
- Then inject drift and export again
- Or modify the input data/model before the second export

---

## 27. Mathematical Summary of Key Metrics and Signals

This section summarizes the key formulas/concepts now implemented in the project.

### 27.1 Feature Drift (KS Statistic)
For each feature, drift is measured using a Kolmogorov–Smirnov type statistic (from ModelShift-Lite drift module), comparing baseline and live distributions.

Interpretation:
- Higher KS ⇒ stronger feature distribution change

### 27.2 Prediction Drift (Output Distribution Shift)
Prediction drift compares baseline and live **prediction probability distributions**.

Signals include:
- KS statistic on prediction probabilities
- Entropy change (uncertainty behavior change)

### 27.3 Health Score
Health score is computed using ModelShift-Lite severity logic (or fallback logic if needed), representing overall reliability on a 0–100 style scale.

Interpretation:
- High score ⇒ stable behavior
- Low score ⇒ likely deployment degradation / drift

### 27.4 Classification Metrics
Given labels `y_true` and predicted probabilities `y_prob`:

- `y_pred = 1 if y_prob >= 0.5 else 0`

Metrics:
- Accuracy = correct predictions / total
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = harmonic mean of precision and recall
- ROC-AUC = ranking quality of probabilities (only if both classes exist)
- MSE = mean((y_true - y_prob)^2)  [Brier-style]
- RMSE = sqrt(MSE)
- Log Loss = cross-entropy loss on probabilities
- Confusion Matrix = TN, FP, FN, TP

### 27.5 Decision Composite Score
Used for summarization in the decision block:

`0.55 * max_feature_ks + 0.35 * prediction_ks + 0.10 * |entropy_change|`

This is an interpretable weighted signal, not a model accuracy metric.

---

## 28. Practical Demo / Execution Guide (Team Reproduction)

This section explains how teammates can reproduce the working pipeline on their own systems.

---

### 28.1 What Teammates Need

1. **Clone or download the `modelshift-lite` repo**
2. **Place the `Testing/` folder** (shared separately) inside the same parent project directory

Expected structure:

- `Final_Year_Project/`
  - `modelshift-lite/`
  - `Testing/`

---

### 28.2 Python Environment Setup

Install required packages (at minimum):

- `numpy`
- `pandas`
- `scikit-learn`
- `joblib`

(Plus any project-specific dependencies already used by `modelshift-lite`.)

---

### 28.3 Start with "Disconnected / Empty" Dashboard (Presentation Demo)

To demonstrate the dashboard before data is connected:

#### Option A (Safe Demo Method)
Temporarily clear generated dashboard data files from:

- `modelshift-lite/dashboard_web/data/latest.json`
- `modelshift-lite/dashboard_web/data/previous.json`
- `modelshift-lite/dashboard_web/data/history_index.json`
- `modelshift-lite/dashboard_web/data/report_latest.html`
- `modelshift-lite/dashboard_web/data/runs/` (generated run files)

(Recommended: backup these files first instead of deleting permanently.)

This will show the dashboard without populated monitoring values.

---

### 28.4 Generate a Clean Monitoring Run (Connected Version)

From the `Testing/` folder, run:

1. `python preprocessing.py`
2. `python train_model.py`
3. `python export_dashboard_data.py`

This will:
- Prepare data
- Train the logistic regression model
- Export the first monitoring payload into dashboard files

At this stage, dashboard values should appear (clean baseline/live comparison).

---

### 28.5 Inject Drift and Generate Drifted Monitoring Run

Then run:

1. `python drift_injection.py`
2. `python export_dashboard_data.py`

This creates a new run with:
- Drifted live data
- Updated drift metrics
- Updated decision severity
- New `latest.json`
- Older run moved to `previous.json`

Now the dashboard can show a meaningful **previous vs current** comparison.

> Note: Retraining is not required after drift injection if the same trained model is being used for drift monitoring.

---

### 28.6 Reconnect After Disconnect Demo

If the dashboard was shown in disconnected mode, simply rerun:

- `python export_dashboard_data.py`

(as long as processed files and model already exist)

This regenerates:
- `latest.json`
- `history_index.json`
- `report_latest.html`
- run artifacts

If files are missing, rerun the full pipeline:
- `preprocessing.py`
- `train_model.py`
- `drift_injection.py` (optional for drift demo)
- `export_dashboard_data.py`

---

## 29. What Is Now Fully Completed (Updated Status)

### 29.1 Core Monitoring (Completed)
- Feature drift detection
- Prediction drift detection
- Health score computation
- Severity/status classification

### 29.2 Validation Pipeline (Completed)
- Dataset preprocessing
- Logistic Regression model training
- Controlled drift injection
- Prediction generation
- Clean vs drifted monitoring export

### 29.3 Explainability / Interpretation (Completed)
- Decision engine (severity + taxonomy)
- Top drifted feature ranking
- Composite drift scoring

### 29.4 Reporting and Visualization Support (Completed)
- Dashboard-ready JSON export
- Run history tracking
- Latest/previous comparison support
- HTML report generation

---

## 30. Final Updated Takeaway

ModelShift-Lite is now validated as a **practical, deployment-style monitoring system** rather than just a theoretical drift detector.

It can:

- Monitor model behavior without requiring labels in real time
- Detect both feature-level and prediction-level distribution changes
- Quantify reliability using health scores
- Provide explainable root-cause candidates
- Track changes over time with historical runs
- Export directly to a dashboard for easy demonstration and analysis

This makes it a strong prototype for real-world ML monitoring in environments where labels are delayed, sparse, or unavailable.

---