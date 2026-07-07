# Rail Bhoomi — AI-Based Project Milestone Prediction System

**CRIS Internship 2026 | CEP1 Section | Nakul Agarwal (23EC102)**  
**Mentor: Mr. Pankaj Motwani, AGM (Civil Engineering), CRIS**

---

## What is this?

An AI-based Machine Learning system integrated with the **Rail Bhoomi portal** (CRIS, Ministry of Railways) that predicts:

1. **Stage-wise Date Prediction** — Given the current notification stage of a land acquisition project, predicts expected dates for all future stages up to final Mutation
2. **Pipeline Completion Forecast** — Given a target date, forecasts how many active projects across all Railway zones will reach each notification stage by that date

---

## Live Demo

🔗 **[Click here to open the live prediction tool](https://railbhoomi-ml.onrender.com)**

---

## Rail Bhoomi Notification Stages

```
Sec 37A → Sec 7A → Sec 20A → Sec 20E → Sec 20F → Sec 20H → Mutation
```

| Stage | Description |
|---|---|
| Section 37A | Special Railway Project Declaration |
| Section 7A | CALA Nomination |
| Section 20A | Land Identification |
| Section 20E | Land Party Identification |
| Section 20F | Compensation Disbursement |
| Section 20H | Physical Possession |
| Mutation | Revenue Record Mutation (Final) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| ML Models | scikit-learn (Gradient Boosting, Random Forest, Ridge) |
| Backend API | Python Flask + Gunicorn |
| Frontend | HTML5 / CSS3 / Vanilla JavaScript |
| Data | MS SQL Server (Rail Bhoomi DB) + Excel fallback |
| Digitalization | data.gov.in API (DILRMP) |
| Deployment | Render.com |

---

## Model Performance

| Stage Gap | Algorithm | CV R² | MAE |
|---|---|---|---|
| 37A → 7A | Gradient Boosting | 0.253 | 4.1 days |
| 7A → 20A | Gradient Boosting | 0.416 | 6.9 days |
| 20A → 20E | Gradient Boosting | 0.541 | 22.2 days |
| 20E → 20F | Gradient Boosting | 0.381 | 12.7 days |
| 20F → 20H | Random Forest | 0.427 | 6.7 days |
| 20H → Mutation | Ridge Regression | 0.497 | 20.9 days |

---

## Repository Structure

```
RailBhoomi_ML/
├── app.py                    Flask REST API
├── train_model.py            Model training pipeline
├── index.html                Web frontend
├── Master_Dataset_5000.xlsx  Training dataset (5000 rows)
├── MasterDataset_v1.sql      SQL query for live data extraction
├── requirements.txt          Python dependencies
├── render.yaml               Render deployment config
├── Procfile                  Gunicorn start command
└── models/
    ├── gap_models.pkl         6 trained gap regression models
    ├── gap_stats.pkl          Gap statistics for prediction bounds
    ├── stage_duration_models.pkl  Pipeline forecaster parameters
    ├── le_railway.pkl         Railway zone label encoder
    ├── le_division.pkl        Division label encoder
    ├── encoder_meta.json      Known zone/division classes
    └── training_report.json  Training summary and metrics
```

---

## API Endpoints

```
GET  /api/health
POST /api/predict_stages       Task 1: Stage-wise date prediction
POST /api/pipeline_snapshot    Task 2: Pipeline completion forecast
```

### Task 1 — Predict Stage Dates
```json
POST /api/predict_stages
{
  "railway": "NR",
  "division": "DLI",
  "current_stage": "20A",
  "current_date": "12-11-2025",
  "states": "7",
  "districts": "27",
  "government_land": 30.0,
  "private_land": 65.0,
  "forest_area": 5.0,
  "court_case_count": 0,
  "active_court_cases": 0
}
```

### Task 2 — Pipeline Snapshot
```json
POST /api/pipeline_snapshot
{
  "target_date": "31-12-2027"
}
```

---

## Run Locally

```bash
git clone https://github.com/YOUR_USERNAME/RailBhoomi_ML.git
cd RailBhoomi_ML
pip install -r requirements.txt
python3 train_model.py
python3 app.py
```
Open `http://localhost:5000`

---

## Key Features

- **Domain-validated synthetic dataset** — 5,000 rows with mentor-specified stage gap constraints
- **Land hierarchy** — Forest (×3) > Private (×2) > Government (×1) difficulty scoring
- **DILRMP Integration** — Live state-level land record digitalization scores from data.gov.in API
- **LGD Hierarchy** — Zone → State → District cascading dropdowns from Local Government Directory
- **Auto-retraining** — Connects to Rail Bhoomi SQL Server when available; falls back to Excel
- **<50ms response** — Pipeline snapshot precomputed at startup for instant queries

---

## About

**Organisation:** Centre for Railway Information Systems (CRIS), ITPI Building, ITO, New Delhi  
**Portal:** [trial.ircep.gov.in/RABH](http://trial.ircep.gov.in/RABH)  
**University:** Gati Shakti Vishwavidyalaya, Vadodara  
**Internship Duration:** 18 May – 31 July 2026
