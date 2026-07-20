# Rail Bhoomi — AI-Based Project Milestone Prediction System
 
**CRIS Internship 2026 | CEP-1 Section | Nakul Agarwal**
**Mentor: Mr. Pankaj Motwani, AGM (CEP-1), CRIS**
 
---
 
## 🔗 Live Demo
 
**[Click here to open the live prediction tool](https://cris-railbhoomi-ml-1.onrender.com)**
 
> Note: Free server — may take 30–50 seconds to wake up on first visit. Works instantly after that.
 
---
 
## What is this?
 
An AI-based Machine Learning system integrated with the **Rail Bhoomi portal** (CRIS, Ministry of Railways, Government of India) that predicts:
 
1. **Stage-wise Date Prediction** — Given the current notification stage of a land acquisition project, predicts expected dates for all future stages up to final Mutation
2. **Pipeline Completion Forecast** — Given a target date, forecasts how many active projects across all Railway zones will reach each notification stage by that date
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
| Digitalization | data.gov.in API (DILRMP — live quarterly data) |
| Containerisation | Docker + Docker Compose |
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
CRIS-RailBhoomi-ML/
├── app.py                      Flask REST API
├── train_model.py              Model training (SQL Server + Excel fallback)
├── index.html                  Web frontend UI
├── Master_Dataset_5000.xlsx    Training dataset (5,000 rows)
├── MasterDataset_v1.sql        SQL query for live data extraction
├── requirements.txt            Python dependencies
├── Procfile                    Gunicorn start command (Render)
├── render.yaml                 Render deployment config
├── Dockerfile                  Docker image definition
├── docker-compose.yml          One command deployment
├── DEPLOYMENT_GUIDE.txt        Complete deployment guide
├── DOCKER_GUIDE.txt            Docker deployment guide
├── NET_Integration_Guide.txt   Guide for CRIS .NET developer
└── models/
    ├── gap_models.pkl           6 trained gap regression models
    ├── gap_stats.pkl            Gap statistics for prediction bounds
    ├── stage_duration_models.pkl  Pipeline forecaster parameters
    ├── le_railway.pkl           Railway zone label encoder
    ├── le_division.pkl          Division label encoder
    ├── encoder_meta.json        Known zone/division classes
    └── training_report.json     Training summary and metrics
```
 
---
 
## Deployment Options
 
### Option 1 — Docker (Recommended — works anywhere)
 
Install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop) 

Then change the directory to the Project Folder based on Windows/Mac/Linux

then run:
 
```bash
docker-compose up -d
```
 
Open browser: `http://localhost:5000`
 
That is it. No Python installation needed. Auto-restarts on server reboot.

For details check DOCKER_GUIDE.txt in code files.
 
### Option 2 — Run Locally (Mac / Linux)

Run each command one by one: 
```bash
git clone https://github.com/Nakul-Agarwal/CRIS-RailBhoomi-ML.git
```
```bash
cd CRIS-RailBhoomi-ML-main
```
```bash
pip install -r requirements.txt
```
```bash
python3 train_model.py
```
```bash
python3 app.py
```
 
Open browser: `http://localhost:5000`

 ### Option 3 — Run Locally on Windows

**Requirement:** Python 3.8+ must be installed — download from [python.org](https://www.python.org/downloads) and tick **"Add Python to PATH"** during installation.

Download and extract the ZIP to Desktop.

Then open Command Promptand Run each command one by one: 

```cmd
cd %USERPROFILE%\Desktop\CRIS-RailBhoomi-ML-main
```
```cmd
pip install -r requirements.txt
```
```cmd
python train_model.py
```
```cmd
python app.py
```

Open browser: `http://localhost:5000`

> Keep Command Prompt open while using the tool. Press `Ctrl+C` to stop.
> 
### Option 4 — Render.com (Live Demo)
 
Already deployed at: **https://cris-railbhoomi-ml-1.onrender.com**
 
To deploy your own instance — connect this repository to [render.com](https://render.com). Render auto-detects `render.yaml` and deploys automatically.
 
---
 
## API Endpoints
 
```
GET  /api/health                  Health check
POST /api/predict_stages          Task 1: Stage-wise date prediction
POST /api/pipeline_snapshot       Task 2: Pipeline completion forecast
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
 
## Key Features
 
- **Domain-validated dataset** — 5,000 rows with mentor-specified stage gap constraints
- **Land hierarchy** — Forest (×3) > Private (×2) > Government (×1) difficulty scoring
- **Live DILRMP Integration** — State-level digitalization scores from data.gov.in API (quarterly updated)
- **LGD Hierarchy** — Zone → State → District cascading dropdowns from Local Government Directory
- **Auto-retraining** — Connects to Rail Bhoomi SQL Server when available; falls back to Excel automatically
- **<50ms response** — Pipeline snapshot precomputed at startup for instant queries
- **Docker ready** — Complete containerisation for one-command deployment anywhere
- **Rail Bhoomi integration** — Ready to embed in portal MIS section via iFrame or .NET HttpClient
---
 
## Integration with Rail Bhoomi Portal
 
The system runs as a microservice alongside the Rail Bhoomi .NET portal. See `NET_Integration_Guide.txt` for complete CRIS developer instructions including C# HttpClient code.
 
---
 
## About
 
| | |
|---|---|
| **Organisation** | Centre for Railway Information Systems (CRIS) |
| **Address** | ITPI Building, ITO, New Delhi — 110001 |
| **Portal** | [trial.ircep.gov.in/RABH](https://trial.ircep.gov.in/RABH/auth/users/login1.cshtml) |
| **Section** | CEP1 — Civil Engineering Projects 1 |
| **University** | Gati Shakti Vishwavidyalaya, Vadodara |
| **Duration** | 18 May – 31 July 2026 |
| **Student** | Nakul Agarwal|
| **Mentor** | Mr. Pankaj Motwani, AGM (CEP-1), CRIS |
