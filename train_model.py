"""
Rail Bhoomi - Model Training Script
=====================================
Author       : Nakul Agarwal
Organization : CRIS (CEP1 Section)
Mentor       : Pankaj Motwani (AGM, CRIS)

HOW IT WORKS:
=============
PRIORITY 1 → SQL Server available → fetches live data, saves Master_Dataset_Latest.xlsx, trains model
PRIORITY 2 → SQL Server not available → automatically uses Master_Dataset_5000.xlsx, trains model

HOW TO RUN:
===========
    python3 train_model.py

After training is complete, restart the API:
    python3 app.py

REQUIREMENTS:
=============
    pip install pandas openpyxl scikit-learn joblib
    pip install pyodbc   (only needed for SQL Server connection)
"""

import os, sys, json, warnings, glob
import pandas as pd
import numpy as np
import joblib
from datetime import datetime

warnings.filterwarnings('ignore')

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# DIGITALIZATION SCORE FETCHER
# Fetches live CLR data from data.gov.in API (Quarterly updated)
# API: DILRMP CLR Data, Rajya Sabha Session 267
# Resource ID: a8618f5c-5fd7-4cd4-ba02-e9371d17a6a2
# ══════════════════════════════════════════════════════════════════════════════
DILRMP_API_KEY      = "579b464db66ec23bdd000001c29fde491a1346807888ea15e336c0e0"
DILRMP_RESOURCE_ID  = "a8618f5c-5fd7-4cd4-ba02-e9371d17a6a2"

# State name → LGD code mapping
STATE_NAME_TO_LGD = {
    "Jammu and Kashmir":1, "Himachal Pradesh":2, "Punjab":3,
    "Chandigarh":4, "Uttarakhand":5, "Haryana":6, "Delhi":7,
    "Rajasthan":8, "Uttar Pradesh":9, "Bihar":10, "Sikkim":11,
    "Manipur":14, "Mizoram":15, "Tripura":16, "Assam":18,
    "West Bengal":19, "Jharkhand":20, "Odisha":21, "Chhattisgarh":22,
    "Madhya Pradesh":23, "Gujarat":24, "Maharashtra":27,
    "Andhra Pradesh":28, "Karnataka":29, "Goa":30, "Lakshadweep":31,
    "Kerala":32, "Tamil Nadu":33, "Puducherry":34,
    "Andaman and Nicobar Islands":35, "Telangana":36, "Ladakh":37,
    "Dadra and Nagar Haveli and Daman and Diu":38,
}

# Fallback scores (last known values from API, used if API is unavailable)
# Source: DILRMP API, Rajya Sabha Session 267, fetched July 2025
FALLBACK_DIG_SCORES = {
    1:0.7054, 2:1.0,    3:0.9962, 4:1.0,    5:0.9923,
    6:1.0,    7:0.2121, 8:0.9750, 9:1.0,    10:1.0,
    11:0.9620,12:0.0,   13:0.0,   14:0.8479, 15:1.0,
    16:1.0,   17:0.0,   18:0.8813,19:0.9970, 20:0.9935,
    21:0.9988,22:0.9801,23:0.9963,24:1.0,   27:1.0,
    28:1.0,   29:1.0,   30:1.0,   31:1.0,   32:1.0,
    33:1.0,   34:1.0,   35:1.0,   36:0.7796, 37:0.2863, 38:1.0,
}

def fetch_digitalization_scores():
    """
    Fetches latest CLR digitalization % from data.gov.in API.
    Returns dict: {lgd_state_code: score (0.0 to 1.0)}
    Falls back to last known values if API is unavailable.
    """
    import urllib.request, json as _json
    url = (f"https://api.data.gov.in/resource/{DILRMP_RESOURCE_ID}"
           f"?api-key={DILRMP_API_KEY}&format=json&limit=100")
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Python/3.9'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        records = data.get('records', [])
        scores  = dict(FALLBACK_DIG_SCORES)  # start with fallback
        fetched = 0
        for r in records:
            name  = str(r.get('state_ut','')).strip()
            pct   = r.get('no__of_villages_where_clr_completed____', None)
            lgd   = STATE_NAME_TO_LGD.get(name)
            if lgd and pct is not None:
                scores[lgd] = round(float(pct) / 100, 4)
                fetched += 1
        print(f"    ✅ Fetched live digitalization scores for {fetched} states from data.gov.in")
        return scores
    except Exception as e:
        print(f"    ⚠️  API unavailable ({e}) — using last known scores (July 2025)")
        return dict(FALLBACK_DIG_SCORES)


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION SETTINGS
# Update these when deploying on CRIS production server
# Leave as-is when running locally on Mac (will auto-fallback to Excel)
# ══════════════════════════════════════════════════════════════════════════════
DB_CONFIG = {
    'server':   'YOUR_SERVER_NAME',
    'database': 'YOUR_DATABASE_NAME',
    'username': 'YOUR_USERNAME',
    'password': 'YOUR_PASSWORD',
    'driver':   'ODBC Driver 17 for SQL Server',
}
USE_WINDOWS_AUTH = False

# ══════════════════════════════════════════════════════════════════════════════
# SQL QUERY (authored by Nakul Agarwal, CRIS Internship 2026)
# ══════════════════════════════════════════════════════════════════════════════
SQL_QUERY = """
WITH AllocationBase AS (
    SELECT DISTINCT uwid, PROJECTID, ShortNameofWork, railway, division,
        exec_agency_rly, states, districts, land_acq_status
    FROM AllocationWise
),
ProjectBase AS (
    SELECT pb.project_id, pb.project_name, ab.uwid, pb.pink_book_ref,
        ab.PROJECTID AS allocation_project_id, ab.ShortNameofWork,
        ab.railway, ab.division, ab.exec_agency_rly,
        ab.states, ab.districts, ab.land_acq_status,
        pb.government_land, pb.private_land, pb.forest_area,
        pb.total_land, pb.land_available, pb.land_to_be_acquired,
        pb.state_id, pb.status
    FROM project_basic pb
    LEFT JOIN AllocationBase ab ON pb.pink_book_ref = ab.PROJECTID
),
Stage37A AS (
    SELECT project_id, CAST(MIN(publish_date) AS DATE) AS date_37A
    FROM notification_37A WHERE publish_date IS NOT NULL GROUP BY project_id
),
Stage7A AS (
    SELECT project_id, CAST(MIN(publish_date) AS DATE) AS date_7A
    FROM la_notification_master WHERE publish_date IS NOT NULL GROUP BY project_id
),
Stage20A AS (
    SELECT project_id, CAST(MIN(publish_date) AS DATE) AS date_20A
    FROM three_A_master WHERE publish_date IS NOT NULL GROUP BY project_id
),
Stage20E AS (
    SELECT project_id, CAST(MIN(publish_date) AS DATE) AS date_20E
    FROM three_d_master WHERE publish_date IS NOT NULL GROUP BY project_id
),
Stage20F AS (
    SELECT project_id, CAST(MIN(approval_date) AS DATE) AS date_20F
    FROM nhai_award WHERE approval_date IS NOT NULL GROUP BY project_id
),
Stage20H AS (
    SELECT na.project_id, CAST(MIN(nad.payment_date) AS DATE) AS date_20H
    FROM nhai_award na
    INNER JOIN nhai_award_det nad ON na.award_id = nad.award_id
    WHERE nad.payment_date IS NOT NULL GROUP BY na.project_id
),
StageMutation AS (
    SELECT na.project_id, CAST(MIN(nad.mutation_date) AS DATE) AS mutation_date
    FROM nhai_award na
    INNER JOIN nhai_award_det nad ON na.award_id = nad.award_id
    WHERE nad.mutation_date IS NOT NULL GROUP BY na.project_id
),
CourtCaseSummary AS (
    SELECT cc.project_id,
        COUNT(DISTINCT cc.case_id) AS court_case_count,
        SUM(CASE WHEN cc.status='Active' THEN 1 ELSE 0 END) AS active_court_cases,
        CAST(MIN(cc.from_date) AS DATE) AS first_court_case_date,
        CAST(MAX(cc.to_date)   AS DATE) AS last_court_case_date,
        SUM(ISNULL(ccd.area,0)) AS total_disputed_area,
        COUNT(DISTINCT ccd.survey_id) AS disputed_surveys
    FROM court_case cc
    LEFT JOIN court_case_details ccd ON cc.case_id = ccd.case_id
    GROUP BY cc.project_id
),
ObjectionSummary AS (
    SELECT tao.project_id,
        COUNT(DISTINCT tao.objection_id) AS objection_count,
        SUM(CASE WHEN tao.status='Active' THEN 1 ELSE 0 END) AS active_objections,
        CAST(MIN(tao.objection_date) AS DATE) AS first_objection_date,
        CAST(MAX(tao.objection_date) AS DATE) AS latest_objection_date,
        COUNT(DISTINCT tao.survey_id) AS affected_surveys,
        COUNT(DISTINCT tao.party_id)  AS affected_parties
    FROM three_A_objections tao
    GROUP BY tao.project_id
)
SELECT
    pb.uwid, pb.project_id, pb.project_name, pb.allocation_project_id,
    pb.ShortNameofWork, pb.railway, pb.division, pb.exec_agency_rly,
    pb.states, pb.districts, pb.land_acq_status,
    pb.government_land, pb.private_land, pb.forest_area,
    pb.total_land, pb.land_available, pb.land_to_be_acquired,
    pb.state_id, pb.status,
    s37.date_37A, s7.date_7A, s20A.date_20A, s20E.date_20E,
    s20F.date_20F, s20H.date_20H, sm.mutation_date,
    ISNULL(cc.court_case_count,0)    AS court_case_count,
    ISNULL(cc.active_court_cases,0)  AS active_court_cases,
    cc.first_court_case_date, cc.last_court_case_date,
    ISNULL(cc.total_disputed_area,0) AS total_disputed_area,
    ISNULL(cc.disputed_surveys,0)    AS disputed_surveys,
    ISNULL(obj.objection_count,0)    AS objection_count,
    ISNULL(obj.active_objections,0)  AS active_objections,
    obj.first_objection_date, obj.latest_objection_date,
    ISNULL(obj.affected_surveys,0)   AS affected_surveys,
    ISNULL(obj.affected_parties,0)   AS affected_parties
FROM ProjectBase pb
LEFT JOIN Stage37A s37     ON pb.project_id = s37.project_id
LEFT JOIN Stage7A s7       ON pb.project_id = s7.project_id
LEFT JOIN Stage20A s20A    ON pb.project_id = s20A.project_id
LEFT JOIN Stage20E s20E    ON pb.project_id = s20E.project_id
LEFT JOIN Stage20F s20F    ON pb.project_id = s20F.project_id
LEFT JOIN Stage20H s20H    ON pb.project_id = s20H.project_id
LEFT JOIN StageMutation sm  ON pb.project_id = sm.project_id
LEFT JOIN CourtCaseSummary cc  ON pb.project_id = cc.project_id
LEFT JOIN ObjectionSummary obj ON pb.project_id = obj.project_id
ORDER BY pb.project_id;
"""

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — LOAD DATA (SQL Server or Local Excel)
# ══════════════════════════════════════════════════════════════════════════════
def load_data():
    print("\n[1] Loading data...")

    # ── Try SQL Server first ──────────────────────────────────────────────────
    try:
        import pyodbc
        if USE_WINDOWS_AUTH:
            conn_str = (f"DRIVER={{{DB_CONFIG['driver']}}};"
                        f"SERVER={DB_CONFIG['server']};"
                        f"DATABASE={DB_CONFIG['database']};"
                        f"Trusted_Connection=yes;")
        else:
            conn_str = (f"DRIVER={{{DB_CONFIG['driver']}}};"
                        f"SERVER={DB_CONFIG['server']};"
                        f"DATABASE={DB_CONFIG['database']};"
                        f"UID={DB_CONFIG['username']};"
                        f"PWD={DB_CONFIG['password']};")

        conn = pyodbc.connect(conn_str, timeout=10)
        print("    ✅ SQL Server connected!")
        df = pd.read_sql(SQL_QUERY, conn)
        conn.close()
        print(f"    ✅ Fetched {len(df)} rows from SQL Server")

        # Save fresh dataset
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        df.to_excel(os.path.join(BASE_DIR, f'Master_Dataset_{ts}.xlsx'), index=False)
        df.to_excel(os.path.join(BASE_DIR, 'Master_Dataset_Latest.xlsx'), index=False)
        print(f"    ✅ Saved as Master_Dataset_{ts}.xlsx + Master_Dataset_Latest.xlsx")
        return df

    except Exception as e:
        if 'pyodbc' in str(type(e).__module__):
            print(f"    ⚠️  SQL Server not available: {e}")
        else:
            print(f"    ⚠️  SQL Server not available — using local dataset")

    # ── Fallback to local Excel ───────────────────────────────────────────────
    candidates = [
        os.path.join(BASE_DIR, 'Master_Dataset_Latest.xlsx'),
        os.path.join(BASE_DIR, 'Master_Dataset_5000.xlsx'),
    ]
    # Also pick newest timestamped file if exists
    timestamped = sorted(glob.glob(os.path.join(BASE_DIR, 'Master_Dataset_2*.xlsx')), reverse=True)
    candidates += timestamped

    for path in candidates:
        if os.path.exists(path):
            df = pd.read_excel(path)
            print(f"    ✅ Loaded {len(df)} rows from {os.path.basename(path)}")
            return df

    print("    ❌ No dataset found! Ensure Master_Dataset_5000.xlsx is in the folder.")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — TRAIN MODEL
# ══════════════════════════════════════════════════════════════════════════════
def train_model(df):
    from sklearn.ensemble        import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model    import Ridge
    from sklearn.preprocessing   import LabelEncoder, StandardScaler
    from sklearn.impute          import SimpleImputer
    from sklearn.model_selection import KFold, cross_val_score
    from sklearn.metrics         import mean_absolute_error, r2_score
    from sklearn.pipeline        import Pipeline

    print("\n[2] Feature Engineering")

    # Parse dates
    STAGE_COLS = ['date_37A','date_7A','date_20A','date_20E',
                  'date_20F','date_20H','mutation_date']
    for col in STAGE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format='%d-%m-%Y', errors='coerce')

    # Compute stage gaps
    GAP_DEF = [
        ('date_37A', 'date_7A',        'gap_37A_7A'),
        ('date_7A',  'date_20A',       'gap_7A_20A'),
        ('date_20A', 'date_20E',       'gap_20A_20E'),
        ('date_20E', 'date_20F',       'gap_20E_20F'),
        ('date_20F', 'date_20H',       'gap_20F_20H'),
        ('date_20H', 'mutation_date',  'gap_20H_mut'),
    ]
    for src, dst, gname in GAP_DEF:
        if src in df.columns and dst in df.columns:
            df[gname] = (df[dst] - df[src]).dt.days

    # Encode categoricals
    le_rly = LabelEncoder()
    le_div = LabelEncoder()
    df['railway_enc']  = le_rly.fit_transform(df['railway'].astype(str))
    df['division_enc'] = le_div.fit_transform(df['division'].astype(str))

    # State / District
    df['primary_state']    = df['states'].astype(str).apply(
        lambda x: int(x.split(',')[0].strip()) if x!='nan' else 0)
    df['primary_district'] = df['districts'].astype(str).apply(
        lambda x: int(x.split(',')[0].strip()) if x!='nan' else 0)
    df['num_states']       = df['states'].astype(str).apply(
        lambda x: len(x.split(',')) if x!='nan' else 1)
    df['num_districts']    = df['districts'].astype(str).apply(
        lambda x: len(x.split(',')) if x!='nan' else 1)

    df['start_year']      = df['date_37A'].dt.year
    df['start_month']     = df['date_37A'].dt.month
    df['has_court_cases'] = (df['court_case_count'] > 0).astype(int)

    # ── Land Acquisition Difficulty Score ─────────────────────────────────────
    # Mentor's domain rule:
    # Forest land takes MOST time → Private land → Government land (easiest)
    # Weighted difficulty: forest*3 + private*2 + govt*1, normalized by total
    df['land_difficulty_score'] = (
        (df['forest_area'] * 3 + df['private_land'] * 2 + df['government_land'] * 1)
        / (df['total_land'].replace(0, 1))
    )

    # Forest proportion (key delay driver per mentor)
    df['forest_proportion']  = df['forest_area']  / df['total_land'].replace(0, 1)
    df['private_proportion'] = df['private_land']  / df['total_land'].replace(0, 1)
    df['govt_proportion']    = df['government_land'] / df['total_land'].replace(0, 1)

    # ── State Digitalization Score ─────────────────────────────────────────────
    # Source: DILRMP (Digital India Land Records Modernization Programme) reports
    # ── State Digitalization Score — fetched live from data.gov.in API ────────
    # Source: DILRMP CLR Data, Rajya Sabha Session 267 (2025)
    # API Resource: a8618f5c-5fd7-4cd4-ba02-e9371d17a6a2
    # Granularity: Quarterly — auto-updates when model is retrained
    print("    Fetching digitalization scores from data.gov.in API...")
    STATE_DIGITALIZATION = fetch_digitalization_scores()
    df['digitalization_score'] = df['primary_state'].map(STATE_DIGITALIZATION).fillna(0.70)
    # Inverse: low digitalization = high delay factor
    df['digitalization_delay'] = 1.0 - df['digitalization_score']

    print("    ✅ Land hierarchy features added (forest > private > govt)")
    print("    ✅ State digitalization scores added (DILRMP data)")

    # Base features
    BASE_FEAT = [
        'railway_enc', 'division_enc',
        'primary_state', 'primary_district',
        'num_states', 'num_districts',
        'government_land', 'private_land', 'forest_area',
        'court_case_count', 'active_court_cases', 'has_court_cases',
        'start_year', 'start_month',
        # Land acquisition difficulty (mentor's domain rule)
        'land_difficulty_score',
        'forest_proportion', 'private_proportion', 'govt_proportion',
        # State digitalization (DILRMP data)
        'digitalization_score', 'digitalization_delay',
    ]

    # Add objection features if available (from SQL Server live data)
    has_obj = 'objection_count' in df.columns
    if has_obj:
        BASE_FEAT += ['objection_count', 'active_objections', 'affected_parties']
        print("    ✅ Objection features included")

    print("    ✅ Features engineered successfully")

    PRIOR = {
        'gap_37A_7A':  [],
        'gap_7A_20A':  ['gap_37A_7A'],
        'gap_20A_20E': ['gap_37A_7A', 'gap_7A_20A'],
        'gap_20E_20F': ['gap_37A_7A', 'gap_7A_20A', 'gap_20A_20E'],
        'gap_20F_20H': ['gap_37A_7A', 'gap_7A_20A', 'gap_20A_20E', 'gap_20E_20F'],
        'gap_20H_mut': ['gap_37A_7A', 'gap_7A_20A', 'gap_20A_20E', 'gap_20E_20F', 'gap_20F_20H'],
    }

    print(f"\n[3] Training Stage Gap Models")
    print(f"    Dataset: {len(df)} rows | Features: {len(BASE_FEAT)}")
    print("    Using: GradientBoosting + RandomForest + Ridge → best by CV R²\n")

    gap_models = {}
    gap_stats  = {}
    report     = {}

    for _, _, gname in GAP_DEF:
        prior = PRIOR[gname]
        feats = [f for f in BASE_FEAT + prior if f in df.columns]
        mask  = df[gname].notna()
        X = df.loc[mask, feats].copy()
        y = df.loc[mask, gname].copy()

        for c in prior:
            if c in X.columns:
                X[c] = X[c].fillna(X[c].median())

        n = len(X)
        gap_stats[gname] = {
            'mean': float(y.mean()), 'std': float(y.std()),
            'min':  float(y.min()),  'max': float(y.max()), 'n': n
        }

        if n < 20:
            print(f"    [{gname}] Too few samples ({n}) — using mean fallback")
            gap_models[gname] = None
            report[gname] = {'model': 'mean_fallback', 'n': n}
            continue

        cv = KFold(n_splits=min(5, n // 10), shuffle=True, random_state=42)
        best_name, best_sc, best_m = None, -np.inf, None

        for cname, model in [
            ('GradientBoosting', GradientBoostingRegressor(
                n_estimators=200, learning_rate=0.05, max_depth=4,
                min_samples_leaf=5, subsample=0.8, random_state=42)),
            ('RandomForest', RandomForestRegressor(
                n_estimators=200, max_depth=6, min_samples_leaf=5,
                max_features='sqrt', random_state=42)),
            ('Ridge', Ridge(alpha=10.0)),
        ]:
            pipe  = Pipeline([('imp', SimpleImputer(strategy='median')),
                              ('scl', StandardScaler()), ('mdl', model)])
            score = cross_val_score(pipe, X, y, cv=cv, scoring='r2').mean()
            print(f"      {cname:<22}: CV R² = {score:.4f}")
            if score > best_sc:
                best_sc = score; best_name = cname; best_m = pipe

        best_m.fit(X, y)
        mae = mean_absolute_error(y, best_m.predict(X))
        r2  = r2_score(y, best_m.predict(X))
        print(f"      ✅ Best: {best_name} | CV R²={best_sc:.4f} | MAE={mae:.1f}d | n={n}\n")

        gap_models[gname] = best_m
        report[gname] = {
            'model': best_name, 'cv_r2': round(best_sc, 4),
            'train_mae': round(mae, 2), 'train_r2': round(r2, 4), 'n': n
        }

    # ── Stage duration models (Task 2 — Pipeline Forecaster) ─────────────────
    print("[4] Building Pipeline Snapshot Forecaster (Task 2)")
    stage_dur = {}
    for sname, gcols in [
        ('7A',       ['gap_37A_7A']),
        ('20A',      ['gap_37A_7A', 'gap_7A_20A']),
        ('20E',      ['gap_37A_7A', 'gap_7A_20A', 'gap_20A_20E']),
        ('20F',      ['gap_37A_7A', 'gap_7A_20A', 'gap_20A_20E', 'gap_20E_20F']),
        ('20H',      ['gap_37A_7A', 'gap_7A_20A', 'gap_20A_20E', 'gap_20E_20F', 'gap_20F_20H']),
        ('Mutation', ['gap_37A_7A', 'gap_7A_20A', 'gap_20A_20E', 'gap_20E_20F', 'gap_20F_20H', 'gap_20H_mut']),
    ]:
        vc   = [c for c in gcols if c in df.columns]
        mask = df[vc].notna().all(axis=1)
        td   = df.loc[mask, vc].sum(axis=1)
        if len(td) > 0:
            ld = np.log(td + 1)
            stage_dur[sname] = {
                'lognorm_mu': float(ld.mean()), 'lognorm_sigma': float(ld.std()),
                'min': float(td.min()),   'max': float(td.max()),
                'p25': float(td.quantile(0.25)), 'p50': float(td.quantile(0.50)),
                'p75': float(td.quantile(0.75)), 'mean': float(td.mean()),
                'std': float(td.std()),  'n': int(len(td)),
            }
            print(f"    {sname:<12}: n={len(td)}, median={td.median():.0f}d from 37A")

    # ── Save all artifacts ────────────────────────────────────────────────────
    print("\n[5] Saving model artifacts")
    joblib.dump(gap_models, os.path.join(MODEL_DIR, 'gap_models.pkl'))
    joblib.dump(gap_stats,  os.path.join(MODEL_DIR, 'gap_stats.pkl'))
    joblib.dump(stage_dur,  os.path.join(MODEL_DIR, 'stage_duration_models.pkl'))
    joblib.dump(le_rly,     os.path.join(MODEL_DIR, 'le_railway.pkl'))
    joblib.dump(le_div,     os.path.join(MODEL_DIR, 'le_division.pkl'))

    json.dump(
        {'railway_classes': le_rly.classes_.tolist(),
         'division_classes': le_div.classes_.tolist()},
        open(os.path.join(MODEL_DIR, 'encoder_meta.json'), 'w'), indent=2)

    json.dump({
        'trained_on':          datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
        'dataset_rows':        len(df),
        'features':            BASE_FEAT,
        'objections_included': has_obj,
        'gap_models':          report,
        'stage_durations':     {k: {ky: round(v,4) if isinstance(v,float) else v
                                    for ky,v in val.items()}
                                for k, val in stage_dur.items()},
    }, open(os.path.join(MODEL_DIR, 'training_report.json'), 'w'), indent=2)

    print(f"    ✅ Saved to: {MODEL_DIR}/")
    print("       gap_models.pkl, gap_stats.pkl, stage_duration_models.pkl")
    print("       le_railway.pkl, le_division.pkl, encoder_meta.json, training_report.json")
    return report


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 65)
    print("RAIL BHOOMI — MODEL TRAINING")
    print(f"Started : {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    print("=" * 65)

    df     = load_data()
    report = train_model(df)

    print("\n" + "=" * 65)
    print("TRAINING COMPLETE — SUMMARY")
    print("=" * 65)
    print(f"\nDataset rows : {len(df)}")
    print(f"\nTask 1 — Stage Gap Models:")
    for g, info in report.items():
        if info.get('model') == 'mean_fallback':
            print(f"  {g:<15}: Mean fallback (n={info['n']})")
        else:
            print(f"  {g:<15}: {info['model']:<20} CV R²={info['cv_r2']:.4f}  MAE={info['train_mae']:.1f}d")

    print(f"\n✅ Model ready for Flask API integration.")
    print(f"   Run: python3 app.py")
    print("=" * 65)
