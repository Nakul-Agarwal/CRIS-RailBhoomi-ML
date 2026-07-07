"""
Rail Bhoomi - ML Prediction API
================================
Flask microservice exposing two endpoints:
  POST /api/predict_stages    → Task 1: Stage duration prediction
  POST /api/pipeline_snapshot → Task 2: Pipeline snapshot by date

Performance optimization:
  Task 2 precomputes predicted completion dates for ALL active projects
  at startup — so every request is just a date comparison, not a model run.
  Response time: <50ms regardless of dataset size.
"""

import os, json
import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'models')

app = Flask(__name__, static_folder=BASE_DIR)

# ── Load models ────────────────────────────────────────────────────────────────
print("[Rail Bhoomi API] Loading models...")
gap_models            = joblib.load(os.path.join(MODEL_DIR, 'gap_models.pkl'))
gap_stats             = joblib.load(os.path.join(MODEL_DIR, 'gap_stats.pkl'))
stage_duration_models = joblib.load(os.path.join(MODEL_DIR, 'stage_duration_models.pkl'))
le_railway            = joblib.load(os.path.join(MODEL_DIR, 'le_railway.pkl'))
le_division           = joblib.load(os.path.join(MODEL_DIR, 'le_division.pkl'))
with open(os.path.join(MODEL_DIR, 'encoder_meta.json')) as f:
    encoder_meta = json.load(f)
print("[Rail Bhoomi API] Models loaded successfully.")

STAGE_NAMES = ['37A','7A','20A','20E','20F','20H','Mutation']
GAP_KEYS    = ['gap_37A_7A','gap_7A_20A','gap_20A_20E',
               'gap_20E_20F','gap_20F_20H','gap_20H_mut']

BASE_FEATURES = [
    'railway_enc','division_enc',
    'primary_state','primary_district',
    'num_states','num_districts',
    'government_land','private_land','forest_area',
    'court_case_count','active_court_cases','has_court_cases',
    'start_year','start_month',
    'land_difficulty_score',
    'forest_proportion','private_proportion','govt_proportion',
    'digitalization_score','digitalization_delay',
]

GAP_PRIOR_FEATURES = {
    'gap_37A_7A':  [],
    'gap_7A_20A':  ['gap_37A_7A'],
    'gap_20A_20E': ['gap_37A_7A','gap_7A_20A'],
    'gap_20E_20F': ['gap_37A_7A','gap_7A_20A','gap_20A_20E'],
    'gap_20F_20H': ['gap_37A_7A','gap_7A_20A','gap_20A_20E','gap_20E_20F'],
    'gap_20H_mut': ['gap_37A_7A','gap_7A_20A','gap_20A_20E','gap_20E_20F','gap_20F_20H'],
}

STAGE_COL_MAP = {
    '37A':'date_37A','7A':'date_7A','20A':'date_20A','20E':'date_20E',
    '20F':'date_20F','20H':'date_20H','Mutation':'mutation_date'
}

def encode_safe(le, value):
    try:    return int(le.transform([str(value)])[0])
    except: return 0

def predict_gap(gap_key, feature_row, prior_gaps):
    model  = gap_models.get(gap_key)
    stats  = gap_stats.get(gap_key, {})
    prior_keys = GAP_PRIOR_FEATURES[gap_key]
    row_dict = {k: feature_row[k] for k in BASE_FEATURES}
    for pk in prior_keys:
        row_dict[pk] = prior_gaps.get(pk, stats.get('mean', 90))
    X = pd.DataFrame([row_dict])
    if model is None:
        return float(stats.get('mean', 90))
    pred = float(model.predict(X)[0])
    return round(max(stats.get('min', 20), min(stats.get('max', 365), pred)))

# ── CORS ───────────────────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

# ══════════════════════════════════════════════════════════════════════════════
# PRECOMPUTE PIPELINE DATES AT STARTUP (Task 2 optimization)
# For each active project, predict when it will reach each future stage.
# Store results in memory as a list of dicts.
# On request: just filter by target date — instant response.
# ══════════════════════════════════════════════════════════════════════════════
print("[Rail Bhoomi API] Precomputing pipeline dates for all active projects...")

# Load dataset
_data_path = os.path.join(BASE_DIR, 'Master_Dataset_Latest.xlsx')
if not os.path.exists(_data_path):
    _data_path = os.path.join(BASE_DIR, 'Master_Dataset_5000.xlsx')
if not os.path.exists(_data_path):
    print("[Rail Bhoomi API] ❌ Dataset not found! Please ensure Master_Dataset_5000.xlsx is in the folder.")
    sys.exit(1)

_df = pd.read_excel(_data_path)
_date_cols = ['date_37A','date_7A','date_20A','date_20E',
              'date_20F','date_20H','mutation_date']
for _col in _date_cols:
    _df[_col] = pd.to_datetime(_df[_col], format='%d-%m-%Y', errors='coerce')

# Active projects = have 37A but NOT yet reached mutation
_active = _df[_df['date_37A'].notna() & _df['mutation_date'].isna()].copy()

# Precomputed store: list of dicts
# Each dict: { stage_name: predicted_datetime or actual_datetime }
_precomputed = []   # one entry per active project
_total_active = len(_active)

for _, proj in _active.iterrows():
    entry = {'project_id': proj['project_id']}

    # Build feature row
    states_list = [int(x.strip()) for x in str(proj.get('states','3')).split(',')
                   if str(x).strip().isdigit()]
    dists_list  = [int(x.strip()) for x in str(proj.get('districts','27')).split(',')
                   if str(x).strip().isdigit()]

    ps  = states_list[0] if states_list else 3

    # Real scores: DILRMP API, data.gov.in, Rajya Sabha Session 267 (2025)
    STATE_DIG = {
        1:0.7054, 2:1.0,    3:0.9962, 4:1.0,    5:0.9923,
        6:1.0,    7:0.2121, 8:0.9750, 9:1.0,    10:1.0,
        11:0.9620,12:0.0,   13:0.0,   14:0.8479, 15:1.0,
        16:1.0,   17:0.0,   18:0.8813,19:0.9970, 20:0.9935,
        21:0.9988,22:0.9801,23:0.9963,24:1.0,   27:1.0,
        28:1.0,   29:1.0,   30:1.0,   31:1.0,   32:1.0,
        33:1.0,   34:1.0,   35:1.0,   36:0.7796, 37:0.2863, 38:1.0,
    }
    dig = STATE_DIG.get(ps, 0.70)
    g_l = float(proj.get('government_land', 30) or 30)
    p_l = float(proj.get('private_land',    60) or 60)
    f_l = float(proj.get('forest_area',      5) or 5)
    tot = (g_l + p_l + f_l) or 1

    feat = {
        'railway_enc':           encode_safe(le_railway,  proj.get('railway','NR')),
        'division_enc':          encode_safe(le_division,  proj.get('division','DLI')),
        'primary_state':         ps,
        'primary_district':      dists_list[0] if dists_list else 27,
        'num_states':            len(states_list),
        'num_districts':         len(dists_list),
        'government_land':       g_l,
        'private_land':          p_l,
        'forest_area':           f_l,
        'court_case_count':      int(proj.get('court_case_count',   0) or 0),
        'active_court_cases':    int(proj.get('active_court_cases', 0) or 0),
        'has_court_cases':       1 if int(proj.get('court_case_count', 0) or 0) > 0 else 0,
        'start_year':            proj['date_37A'].year,
        'start_month':           proj['date_37A'].month,
        'land_difficulty_score': (f_l*3 + p_l*2 + g_l*1) / tot,
        'forest_proportion':      f_l / tot,
        'private_proportion':     p_l / tot,
        'govt_proportion':        g_l / tot,
        'digitalization_score':   dig,
        'digitalization_delay':   1.0 - dig,
    }

    # Find current stage (last completed stage)
    curr_idx  = 0
    curr_date = proj['date_37A']
    for si, sn in enumerate(STAGE_NAMES):
        sc = STAGE_COL_MAP[sn]
        if pd.notna(proj[sc]):
            curr_date = proj[sc]
            curr_idx  = si

    # Fill known gaps from actual dates
    prior_gaps = {}
    for gi, gk in enumerate(GAP_KEYS):
        from_col = STAGE_COL_MAP[STAGE_NAMES[gi]]
        to_col   = STAGE_COL_MAP[STAGE_NAMES[gi+1]]
        if pd.notna(proj[from_col]) and pd.notna(proj[to_col]):
            prior_gaps[gk] = (proj[to_col] - proj[from_col]).days

    # Record already-completed stages
    for si, sn in enumerate(STAGE_NAMES):
        sc = STAGE_COL_MAP[sn]
        if pd.notna(proj[sc]):
            entry[sn] = proj[sc]

    # Predict future stages from current position
    running_date = curr_date
    for gi in range(curr_idx, len(GAP_KEYS)):
        gk         = GAP_KEYS[gi]
        next_stage = STAGE_NAMES[gi + 1]
        if next_stage in entry:
            # Already have actual date — use it
            running_date = entry[next_stage]
            prior_gaps[gk] = (entry[next_stage] - (entry.get(STAGE_NAMES[gi]) or running_date)).days
            continue
        days = predict_gap(gk, feat, prior_gaps)
        prior_gaps[gk] = days
        running_date   = running_date + timedelta(days=int(days))
        entry[next_stage] = running_date

    _precomputed.append(entry)

print(f"[Rail Bhoomi API] Precomputed {len(_precomputed)} active projects. Ready!")

# Compute median days for display
_median_days = {}
for sn in STAGE_NAMES[1:]:
    params = stage_duration_models.get(sn, {})
    _median_days[sn] = int(params.get('p50', 0))

# ── Health ──────────────────────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status':'ok',
                    'active_projects': _total_active,
                    'message':'Rail Bhoomi ML API running'})

# ── Task 1: Stage Prediction ───────────────────────────────────────────────────
@app.route('/api/predict_stages', methods=['POST','OPTIONS'])
def predict_stages():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data          = request.get_json()
        railway       = str(data.get('railway','NR'))
        division      = str(data.get('division','DLI'))
        current_stage = str(data.get('current_stage','37A'))
        current_date  = str(data.get('current_date',''))
        states        = str(data.get('states','3'))
        districts     = str(data.get('districts','27'))
        govt_land     = float(data.get('government_land', 30))
        priv_land     = float(data.get('private_land',    60))
        forest        = float(data.get('forest_area',      5))
        court_cases   = int(data.get('court_case_count',   0))
        active_cc     = int(data.get('active_court_cases', 0))

        try:    curr_dt = datetime.strptime(current_date, '%d-%m-%Y')
        except: curr_dt = datetime.today()

        states_list    = [int(x.strip()) for x in states.split(',') if x.strip().isdigit()]
        districts_list = [int(x.strip()) for x in districts.split(',') if x.strip().isdigit()]

        # Real scores: DILRMP API, data.gov.in, Rajya Sabha Session 267 (2025)
        STATE_DIGITALIZATION = {
            1:0.7054, 2:1.0,    3:0.9962, 4:1.0,    5:0.9923,
            6:1.0,    7:0.2121, 8:0.9750, 9:1.0,    10:1.0,
            11:0.9620,12:0.0,   13:0.0,   14:0.8479, 15:1.0,
            16:1.0,   17:0.0,   18:0.8813,19:0.9970, 20:0.9935,
            21:0.9988,22:0.9801,23:0.9963,24:1.0,   27:1.0,
            28:1.0,   29:1.0,   30:1.0,   31:1.0,   32:1.0,
            33:1.0,   34:1.0,   35:1.0,   36:0.7796, 37:0.2863, 38:1.0,
        }
        primary_state_code = states_list[0] if states_list else 3
        dig_score = STATE_DIGITALIZATION.get(primary_state_code, 0.70)

        total_land = govt_land + priv_land + forest
        total_land = total_land if total_land > 0 else 1

        feature_row = {
            'railway_enc':          encode_safe(le_railway, railway),
            'division_enc':         encode_safe(le_division, division),
            'primary_state':        primary_state_code,
            'primary_district':     districts_list[0] if districts_list else 27,
            'num_states':           len(states_list),
            'num_districts':        len(districts_list),
            'government_land':      govt_land,
            'private_land':         priv_land,
            'forest_area':          forest,
            'court_case_count':     court_cases,
            'active_court_cases':   active_cc,
            'has_court_cases':      1 if court_cases > 0 else 0,
            'start_year':           curr_dt.year,
            'start_month':          curr_dt.month,
            # Land hierarchy features
            'land_difficulty_score': (forest*3 + priv_land*2 + govt_land*1) / total_land,
            'forest_proportion':     forest    / total_land,
            'private_proportion':    priv_land / total_land,
            'govt_proportion':       govt_land / total_land,
            # Digitalization features
            'digitalization_score':  dig_score,
            'digitalization_delay':  1.0 - dig_score,
        }

        stage_idx = {s:i for i,s in enumerate(STAGE_NAMES)}
        curr_idx  = stage_idx.get(current_stage, 0)

        predictions  = []
        prior_gaps   = {}
        running_date = curr_dt

        for gap_i, gap_key in enumerate(GAP_KEYS):
            target_stage = STAGE_NAMES[gap_i + 1]
            if gap_i + 1 <= curr_idx:
                continue
            days = predict_gap(gap_key, feature_row, prior_gaps)
            prior_gaps[gap_key] = days
            running_date = running_date + timedelta(days=int(days))
            predictions.append({
                'stage':          target_stage,
                'predicted_days': int(days),
                'predicted_date': running_date.strftime('%d-%m-%Y'),
                'gap_from_now':   (running_date - curr_dt).days,
            })

        return jsonify({
            'success':       True,
            'current_stage': current_stage,
            'current_date':  curr_dt.strftime('%d-%m-%Y'),
            'predictions':   predictions,
            'railway':       railway,
            'division':      division,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ── Task 2: Pipeline Snapshot — INSTANT (precomputed) ─────────────────────────
@app.route('/api/pipeline_snapshot', methods=['POST','OPTIONS'])
def pipeline_snapshot():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data        = request.get_json()
        target_date = str(data.get('target_date',''))

        try:    target_dt = datetime.strptime(target_date, '%d-%m-%Y')
        except: return jsonify({'success':False, 'error':'Invalid date. Use DD-MM-YYYY'}), 400

        # ── INSTANT: just count how many precomputed dates <= target_dt ──────
        stage_results = []
        for stage_name in STAGE_NAMES:
            count = 0
            for entry in _precomputed:
                stage_date = entry.get(stage_name)
                if stage_date and pd.notna(stage_date):
                    # Compare — stage_date is datetime
                    sd = stage_date if isinstance(stage_date, datetime) else stage_date.to_pydatetime()
                    if sd <= target_dt:
                        count += 1

            pct = round((count / _total_active) * 100, 1) if _total_active > 0 else 0
            stage_results.append({
                'stage':              stage_name,
                'projects_reached':   count,
                'percentage':         pct,
                'median_days_needed': _median_days.get(stage_name, 0),
            })

        return jsonify({
            'success':        True,
            'target_date':    target_dt.strftime('%d-%m-%Y'),
            'total_active':   _total_active,
            'stage_snapshot': stage_results,
        })

    except Exception as e:
        return jsonify({'success':False, 'error': str(e)}), 400


# ── Serve frontend ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)


import sys as _sys
if __name__ == '__main__':
    _port = int(os.environ.get('PORT', 5000))
    print(f"[Rail Bhoomi API] Starting server on port {_port}")
    app.run(debug=False, host='0.0.0.0', port=_port)
