# Predictive Maintenance — Deployed ML Service

**Live demo:** _(coming soon — added once the API is deployed)_

Predicting industrial equipment failure from real-time sensor data, with a full pipeline from raw data to a production-style deployed API.

---

## Problem Statement

Predict the probability that a piece of industrial equipment will experience a machine failure, using real-time operating conditions (temperature, rotational speed, torque, tool wear) and product quality tier — enabling maintenance teams to intervene before an unplanned failure occurs, rather than reacting after the fact.

This models a generic CNC-style machining process (cutting/milling), based on the AI4I 2020 Predictive Maintenance dataset (UCI Machine Learning Repository).

---

## Dataset

- **Source:** [AI4I 2020 Predictive Maintenance Dataset](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset), UCI Machine Learning Repository
- **Size:** 10,000 rows, 14 columns, zero missing values
- **Target:** `machine_failure` (binary) — only **3.39%** of machines failed (339 / 10,000), a significant class imbalance
- **Features used:** `type` (product quality tier: L/M/H), `air_temperature_k`, `process_temperature_k`, `rotational_speed_rpm`, `torque_nm`, `tool_wear_min`
- **Dropped columns:**
  - `udi`, `product_id` — identifiers with no predictive signal
  - `twf`, `hdf`, `pwf`, `osf`, `rnf` — failure *subtypes*, only known after a failure occurs → excluded to prevent data leakage

---

## Architecture

```
CSV (raw data)
   │
   ▼
Postgres (Neon) — idempotent loader script
   │
   ▼
Jupyter Notebook — EDA + Feature Engineering
   │
   ▼
Model Training (Logistic Regression → XGBoost)
   │
   ▼
[Next] FastAPI service → Docker → CI/CD → Live deployment
```

---

## Data Warehousing

Raw data is loaded into a managed Postgres database (Neon) via an **idempotent** Python script (`src/load_to_db.py`) — safe to re-run any number of times without creating duplicate rows, using an upsert keyed on the row ID.

**Why a managed database instead of self-hosting:** avoids the operational overhead of patching, backups, and uptime management — and ensures the database stays reachable by both local development and the eventual deployed API, without switching providers.

---

## EDA — Key Findings

Three real, evidence-backed patterns were found before any modeling began:

1. **Product quality tier matters.** Low-quality (`L`) machines fail nearly twice as often as high-quality (`H`) machines (3.92% vs 2.09% failure rate).

2. **Tool wear has a threshold effect, not a linear trend.** Failure rate stays flat (~2–4%) for the first ~200 minutes of cumulative tool wear, then spikes sharply — reaching **33.9%** beyond 227 minutes. This non-linear "cliff" behavior, rather than a gradual increase, suggests tool degradation happens abruptly once a wear threshold is crossed.

3. **Temperature gap (process − air temperature) is a strong signal for heat dissipation failure.** When the gap is small (7.6–8.7K), failure rate jumps to **13–15%** — roughly 4–6x the baseline — consistent with the dataset's documented "Heat Dissipation Failure" mode, since a small gap indicates the machine is struggling to vent heat into its surroundings.

---

## Feature Engineering

Based on the EDA findings above, two threshold-based features were engineered:
- `high_wear` = 1 if `tool_wear_min > 200`, else 0
- `low_temp_gap` = 1 if `temp_gap < 8.7`, else 0

`type` was one-hot encoded into `type_L`, `type_M`, `type_H` (avoiding a false ordinal assumption between quality tiers).

**Note on feature importance:** in the final XGBoost model, `high_wear` and `low_temp_gap` showed zero importance. This isn't a failure of the feature engineering — tree-based models can already split directly on continuous values like `tool_wear_min` at any threshold, making explicit threshold flags redundant. These features would likely matter more for a linear model (like logistic regression), which cannot discover non-linear thresholds on its own. This distinction is itself a useful, evidence-backed insight about when threshold engineering adds value.

---

## Modeling

Two models were trained and compared on a stratified 80/20 train/test split (preserving the 3.39% failure rate in both sets):

| Model | Precision (failure) | Recall (failure) | F1 (failure) |
|---|---|---|---|
| Logistic Regression (baseline) | 0.20 | 0.88 | 0.33 |
| **XGBoost** | **0.58** | 0.82 | **0.68** |

**Why accuracy is not reported as the primary metric:** with only 3.39% of machines failing, a model predicting "no failure" every time would score 96.6% accuracy while being completely useless. Precision, recall, and F1 on the failure class are the metrics that actually matter here.

**Why XGBoost was chosen over logistic regression:** logistic regression draws a single smooth decision boundary, which struggles to represent the sharp, threshold-based patterns found in EDA (tool wear cliff, temperature gap cliff). XGBoost builds decision trees that can split directly on these thresholds, which is reflected in the large precision improvement (20% → 58%) with only a small recall trade-off (88% → 82%).

**Top features by importance (XGBoost):**
1. `rotational_speed_rpm` (31.7%)
2. `tool_wear_min` (22.8%)
3. `torque_nm` (22.8%)
4. `temp_gap` (8.1%)

---

## What I'd Do Differently at Scale

- Batch or bulk-load database writes rather than row-by-row inserts (already applied after an initial slow row-by-row version)
- Tune XGBoost hyperparameters systematically (Optuna) rather than using reasonable defaults
- Apply threshold tuning on the final model's predicted probabilities to explicitly balance false-alarm cost vs. missed-failure cost, based on real business priorities
- Add automated data drift monitoring in production, given the model's dependence on sensor value distributions staying consistent with training data

---

## Project Status

- [x] Dataset sourced, inspected, and documented
- [x] Data warehousing (Postgres, idempotent loader)
- [x] EDA with three validated, evidence-backed findings
- [x] Feature engineering, validated against EDA findings
- [x] Model comparison: Logistic Regression baseline vs. XGBoost
- [ ] Model versioning + `model_card.md`
- [ ] FastAPI service (`/predict`, `/health`)
- [ ] Dockerization
- [ ] CI/CD (GitHub Actions)
- [ ] Live deployment
- [ ] Monitoring / logging dashboard
- [ ] Minimal frontend (Streamlit)

---

## Tech Stack

- **Data:** Python, pandas, PostgreSQL (Neon)
- **Modeling:** scikit-learn, XGBoost
- **Notebook:** Jupyter (VS Code)
- _(Coming soon: FastAPI, Docker, GitHub Actions)_
