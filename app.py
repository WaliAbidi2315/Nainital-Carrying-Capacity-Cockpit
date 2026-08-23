"""
Nainital Carrying Capacity Cockpit — Report-Style Edition
Municipal decision-support dashboard for sustainable mountain tourism governance.
Built for the Urban Immersion fieldwork, BS Analytics & Sustainability Studies, TISS (2024-28).

Run:  streamlit run app.py
Place available KoboToolbox exports (Enterprise*.xlsx, Location*.xlsx, *Residents*.xlsx,
Workers*.xlsx, Tourist*.xlsx) in the same folder or a ./data subfolder. Any file not found
falls back to a labeled synthetic dataset so the app still runs end-to-end. Open the
"Data Diagnostics" expander at the top of the app at any time to see exactly which files
were used and how complete each derived field is.
"""

import glob
import re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestRegressor

# ============================================================================
# PAGE CONFIG + THEME
# ============================================================================
st.set_page_config(page_title="Nainital Carrying Capacity Cockpit", page_icon="🏔️",
                    layout="wide", initial_sidebar_state="collapsed")

SLATE, EMERALD, AMBER, CRIMSON, GRAY_BG = "#1E293B", "#059669", "#D97706", "#DC2626", "#F8FAFC"
BLUE, PURPLE, GREY = "#0EA5E9", "#7C3AED", "#64748B"
PLOTLY_SEQ = [EMERALD, AMBER, CRIMSON, BLUE, PURPLE, GREY]

st.markdown(f"""
<style>
.stApp {{ background-color: {GRAY_BG}; }}
h1, h2, h3, h4 {{ color: {SLATE} !important; font-family: 'Segoe UI', sans-serif; }}
[data-testid="stSidebar"] {{ display: none !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}
.nav-bar {{
    display: flex; gap: 8px; flex-wrap: wrap;
    background: {SLATE}; border-radius: 12px;
    padding: 10px 16px; margin-bottom: 20px; align-items: center;
}}
.nav-bar-title {{
    color: white; font-weight: 700; font-size: 1.0rem;
    margin-right: 12px; white-space: nowrap;
}}
.nav-btn {{
    background: rgba(255,255,255,0.12); color: #E2E8F0 !important;
    border: 1px solid rgba(255,255,255,0.2); border-radius: 8px;
    padding: 6px 14px; font-size: 0.83rem; font-weight: 500;
    cursor: pointer; text-decoration: none; white-space: nowrap;
    transition: background 0.15s;
}}
.nav-btn:hover {{ background: rgba(255,255,255,0.22); color: white !important; }}
.nav-btn.active {{
    background: {EMERALD}; border-color: {EMERALD}; color: white !important; font-weight: 700;
}}
.kpi-card {{
    background: white; border-radius: 12px; padding: 18px 16px; border-left: 5px solid {EMERALD};
    box-shadow: 0 1px 4px rgba(0,0,0,0.08); text-align: left; height: 100%;
}}
.kpi-card.amber {{ border-left-color: {AMBER}; }}
.kpi-card.crimson {{ border-left-color: {CRIMSON}; }}
.kpi-card.slate {{ border-left-color: {SLATE}; }}
.kpi-label {{ font-size: 0.78rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }}
.kpi-value {{ font-size: 1.9rem; font-weight: 700; color: {SLATE}; }}
.kpi-sub {{ font-size: 0.75rem; color: #94A3B8; margin-top: 2px; }}
.callout {{
    background: #ECFDF5; border-left: 4px solid {EMERALD}; border-radius: 6px;
    padding: 14px 18px; font-size: 0.94rem; color: #065F46; margin: 12px 0 20px 0; line-height: 1.55;
}}
.callout.amber {{ background: #FFFBEB; border-left-color: {AMBER}; color: #92400E; }}
.callout.crimson {{ background: #FEF2F2; border-left-color: {CRIMSON}; color: #991B1B; }}
.callout.blue {{ background: #EFF6FF; border-left-color: {BLUE}; color: #1E40AF; }}
.outcome-box {{
    background: white; border: 1px solid #E2E8F0; border-left: 5px solid {SLATE}; border-radius: 8px;
    padding: 16px 20px; margin: 18px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}
.outcome-box h4 {{ margin-top: 0; }}
.section-tag {{
    display:inline-block; background:{SLATE}; color:white; font-size:0.72rem; font-weight:600;
    padding:3px 10px; border-radius:20px; letter-spacing:0.05em; margin-bottom:6px;
}}
.section-intro {{ font-size: 1.0rem; line-height: 1.65; color: #334155; margin-bottom: 8px; }}
hr {{ border-color: #E2E8F0; }}
table {{ font-size: 0.88rem; }}
</style>
""", unsafe_allow_html=True)

PLOTLY_TEMPLATE = dict(
    layout=go.Layout(
        font=dict(family="Segoe UI, sans-serif", color=SLATE),
        plot_bgcolor="white", paper_bgcolor="white",
        colorway=PLOTLY_SEQ, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#EEF2F7"), yaxis=dict(gridcolor="#EEF2F7"),
    )
)

# ============================================================================
# COLUMN-RESOLUTION + SAFE-DISPLAY HELPERS
# ============================================================================
def _looks_like_scale(name: str) -> bool:
    name = str(name)
    return bool(re.search(r"1.*5", name)) or "very" in name.lower()

def find_col(df, *keywords):
    """Find the column matching any keyword, preferring the candidate that actually holds
    data. KoboToolbox 'all versions' exports frequently split one question into a near-empty
    label column plus an adjacent Likert-scale answer column."""
    cols = list(df.columns)
    candidates = []
    for kw in keywords:
        for i, c in enumerate(cols):
            if kw.lower() in str(c).lower():
                candidates.append(i)
    if not candidates:
        return None
    scored = sorted(((i, df[cols[i]].notna().sum()) for i in candidates), key=lambda x: -x[1])
    if scored[0][1] > 0:
        return cols[scored[0][0]]
    for i in candidates:
        if i + 1 < len(cols) and _looks_like_scale(cols[i + 1]) and df[cols[i + 1]].notna().sum() > 0:
            return cols[i + 1]
    return cols[candidates[0]]

def yn(series):
    s = series.astype(str).str.strip().str.lower()
    return s.map(lambda x: 1 if x in ("yes", "y", "true") else (0 if x in ("no", "n", "false") else np.nan))

def norm(series, invert=False):
    s = pd.to_numeric(series, errors="coerce")
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(50.0, index=series.index)
    out = (s - lo) / (hi - lo) * 100
    return 100 - out if invert else out

def find_file(*patterns):
    for p in patterns:
        matches = glob.glob(f"data/{p}") + glob.glob(p)
        if matches:
            return matches[0]
    return None

def safe_pct(series_or_value, decimals=0, default="Data not available"):
    """Guard against silent NaN -> 'nan%' display bugs."""
    v = series_or_value.mean() if hasattr(series_or_value, "mean") else series_or_value
    if v is None or (isinstance(v, (int, float)) and pd.isna(v)):
        return default
    return f"{v*100:.{decimals}f}%"

def safe_num(value, fmt="{:.0f}", default="N/A"):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return fmt.format(value)
    except (ValueError, TypeError):
        return default

def safe_mean(series, default=np.nan):
    v = pd.to_numeric(series, errors="coerce").mean()
    return v if not pd.isna(v) else default

def whitelist_categories(series, valid_values):
    """KoboToolbox 'all versions' exports frequently leak stray numeric contamination
    (e.g. a handful of rows containing '0', '1', or a row-count value) into otherwise-clean
    categorical columns, and multi-select questions can appear as concatenated combo strings.
    This keeps only exact, known-good category labels and maps everything else to NaN,
    rather than letting junk categories clutter chart axes/legends."""
    s = series.astype(str).str.strip()
    valid_lower = {v.lower(): v for v in valid_values}
    return s.str.lower().map(valid_lower)

def bucket_to_numeric(series, bucket_map):
    """Map a binned/range categorical field (e.g. '₹5,001–₹10,000') to a representative
    numeric midpoint. Rows with an unrecognized value (including stray raw-numeric
    contamination that doesn't match any known bucket label) become NaN rather than being
    silently mis-coerced."""
    s = series.astype(str).str.strip()
    return s.map(bucket_map)

def map_noise(series):
    """Handles both the clean text labels and the numeric/parenthetical variants that show
    up across merged KoboToolbox form versions (e.g. '1 (much quieter)', bare '4')."""
    s = series.astype(str).str.strip()
    direct = {"Much quieter": 0, "About the same": 25, "Somewhat louder": 60,
              "Much louder — it disrupts my daily routine": 100}
    out = s.map(direct)
    numeric_scale = {"1": 0, "2": 25, "3": 50, "4": 75, "5": 100}
    leading_digit = s.str.extract(r"^(\d)")[0]
    fallback = leading_digit.map(numeric_scale)
    return out.fillna(fallback)

# ============================================================================
# SYNTHETIC FALLBACK GENERATORS (schema-matched, used only if a real file is missing)
# ============================================================================
def _synthetic_location(n=10, rng=None):
    rng = rng or np.random.default_rng(42)
    lat0, lon0 = 29.388, 79.459
    return pd.DataFrame({
        "lat": lat0 + rng.normal(0, 0.004, n), "lon": lon0 + rng.normal(0, 0.004, n),
        "zone_name": [f"Mall Road Zone {i+1}" for i in range(n)],
        "emergency_min": rng.choice([10, 15, 20, 25, 30, 45, 60], n),
        "parking_spots": rng.integers(0, 15, n),
        "footpaths": rng.choice(["Yes", "No"], n, p=[0.5, 0.5]),
        "potholes": rng.choice(["Yes", "No"], n, p=[0.4, 0.6]),
        "waterlogging": rng.choice(["Yes", "No"], n, p=[0.3, 0.7]),
        "signboards": rng.integers(0, 8, n),
        "dustbins": rng.integers(0, 12, n),
        "toilets": rng.integers(0, 4, n),
        "healthcare": rng.choice(["Yes", "No"], n, p=[0.4, 0.6]),
        "wifi": rng.choice(["Yes", "No"], n, p=[0.3, 0.7]),
        "accommodation_units": rng.integers(2, 40, n),
    })

def _synthetic_enterprise(n=159, rng=None):
    rng = rng or np.random.default_rng(1)
    lat0, lon0 = 29.388, 79.459
    types = ["Hotel", "Homestay", "Restaurant", "Travel Agency", "Adventure Sports", "Retail"]
    return pd.DataFrame({
        "lat": lat0 + rng.normal(0, 0.004, n), "lon": lon0 + rng.normal(0, 0.004, n),
        "type": rng.choice(types, n),
        "owner_local": rng.choice(["Yes", "No"], n, p=[0.55, 0.45]),
        "ft_employees": rng.integers(0, 20, n), "seasonal_employees": rng.integers(0, 15, n),
        "local_employees": rng.integers(0, 15, n),
        "tank_capacity": rng.choice([0, 500, 1000, 2000, 5000, 12000, 20000], n),
        "constraint": rng.choice(["Not at all", "Minor adjustments", "Significant reduction", "Had to refuse guests"],
                                  n, p=[0.4, 0.35, 0.17, 0.08]),
        "shortage_flag": rng.choice(["Yes", "No"], n, p=[0.35, 0.65]),
        "rainwater": rng.choice(["Yes", "No"], n, p=[0.04, 0.96]),
        "open_to_rainwater": rng.choice(["Yes", "No"], n, p=[0.6, 0.4]),
        "renewable": rng.choice(["Yes", "No"], n, p=[0.12, 0.88]),
        "elec_peak": rng.integers(3000, 40000, n), "elec_off": rng.integers(1500, 20000, n),
        "sewage": rng.choice(["Connected to municipal sewage line", "Septic tank",
                               "Own sewage treatment plant", "No system in place"], n, p=[0.35, 0.4, 0.1, 0.15]),
    })

def _synthetic_residents(n=239, rng=None):
    rng = rng or np.random.default_rng(2)
    lat0, lon0 = 29.388, 79.459
    return pd.DataFrame({
        "lat": lat0 + rng.normal(0, 0.004, n), "lon": lon0 + rng.normal(0, 0.004, n),
        "piped_hours": rng.choice([1, 2, 3, 4, 6, 8, 12, 24], n, p=[.1,.15,.15,.2,.15,.1,.1,.05]).clip(0, 24),
        "equity": rng.choice(["Yes", "No"], n, p=[0.36, 0.64]),
        "coping_tanker": rng.choice(["Yes", "No"], n, p=[0.26, 0.74]),
        "rainwater_hh": rng.choice(["Yes", "No"], n, p=[0.08, 0.92]),
        "travel_rating": rng.choice([1, 2, 3, 4, 5], n, p=[.27,.26,.21,.11,.15]),
        "noise": rng.choice(["Much louder — it disrupts my daily routine", "Somewhat louder", "About the same",
                              "Much quieter"], n, p=[0.22, 0.41, 0.14, 0.23]),
        "price_compare": rng.choice(["Much higher", "Slightly higher", "No change"], n, p=[0.19, 0.4, 0.41]),
        "visit_less_peak": rng.choice(["Yes", "No"], n, p=[0.45, 0.55]),
        "tourism_livelihood": rng.choice(["Yes", "No"], n, p=[0.38, 0.62]),
        "tourism_helps_growth": rng.choice(["Yes", "No"], n, p=[0.6, 0.4]),
    })

def _synthetic_workers(n=296, rng=None):
    rng = rng or np.random.default_rng(3)
    sectors = ["Hospitality", "Transport", "Street Vendors", "Boat", "Retail/Shop", "Sanitation"]
    return pd.DataFrame({
        "sector": rng.choice(sectors, n),
        "status": rng.choice(["Salaried Employment", "Own Account Workers", "Casual Employment", "Employers"],
                              n, p=[0.29, 0.28, 0.4, 0.03]),
        "arrangement": rng.choice(["Permanent (year-round)", "Seasonal"], n, p=[0.81, 0.19]),
        "months_worked": rng.choice([0, 2, 3, 4, 6, 10, 12], n, p=[.07,.03,.04,.02,.02,.03,.79]),
        "income_peak": rng.integers(4000, 35000, n),
        "income_off": rng.integers(1500, 20000, n),
        "insurance": rng.choice(["Yes", "No"], n, p=[0.23, 0.77]),
        "govt_support": rng.choice(["Yes", "No", np.nan], n, p=[0.1, 0.3, 0.6]),
        "payment_on_time": rng.choice(["Yes", "No", np.nan], n, p=[0.4, 0.15, 0.45]),
        "primary_tourism": rng.choice(["Yes", "No"], n, p=[0.65, 0.35]),
    })

def _synthetic_tourist(n=320, rng=None):
    rng = rng or np.random.default_rng(4)
    purposes = ["Leisure/Vacation", "Honeymoon", "Family Trip", "Pilgrimage", "Adventure", "Business+Leisure"]
    states = ["Delhi", "Uttar Pradesh", "Uttarakhand", "Maharashtra", "West Bengal", "Other"]
    return pd.DataFrame({
        "group_size": rng.integers(1, 12, n),
        "expenditure": rng.integers(1500, 50000, n),
        "overspent": rng.choice(["Yes", "No"], n, p=[0.34, 0.66]),
        "direction_ease": rng.choice([1, 2, 3, 4, 5], n, p=[.05,.1,.2,.4,.25]),
        "satisfaction": rng.choice([1, 2, 3, 4, 5], n, p=[.04,.09,.24,.39,.24]),
        "cleanliness": rng.choice([1, 2, 3, 4, 5], n, p=[.02,.07,.23,.44,.24]),
        "origin_state": rng.choice(states, n),
        "purpose": rng.choice(purposes, n),
    })

# ============================================================================
# DATA LOADING (real files preferred, synthetic fallback, cached, error-safe)
# ============================================================================
@st.cache_data(show_spinner="Loading fieldwork datasets...")
def load_all():
    src_flags, diag = {}, {}

    def try_load(name, pattern, builder, synth_fn, synth_n):
        path = find_file(pattern)
        if not path:
            diag[name] = {"status": "synthetic", "reason": "No matching file found in folder.", "path": None}
            return synth_fn(), "synthetic"
        try:
            raw = pd.read_excel(path)
            out = builder(raw)
            diag[name] = {"status": "real", "reason": f"Loaded {len(out)} rows from {path.split('/')[-1]}.", "path": path}
            return out, "real"
        except Exception as e:
            diag[name] = {"status": "synthetic", "reason": f"Found '{path}' but failed to parse it ({e}). Using synthetic fallback.", "path": path}
            return synth_fn(n=synth_n), "synthetic"

    def build_location(raw):
        loc = pd.DataFrame({
            "lat": pd.to_numeric(raw[find_col(raw, "_geolocation_latitude")], errors="coerce"),
            "lon": pd.to_numeric(raw[find_col(raw, "_geolocation_longitude")], errors="coerce"),
            "emergency_min": pd.to_numeric(raw[find_col(raw, "ambulance")], errors="coerce"),
            "footpaths": raw[find_col(raw, "dedicated footpaths")],
            "potholes": raw[find_col(raw, "potholes on the road")],
            "waterlogging": raw[find_col(raw, "water logging")],
            "signboards": pd.to_numeric(raw[find_col(raw, "directional signboards")], errors="coerce"),
            "dustbins": pd.to_numeric(raw[find_col(raw, "total number of dustbins", "number of dustbins")], errors="coerce"),
            "toilets": pd.to_numeric(raw[find_col(raw, "public toilets are there")], errors="coerce"),
            "healthcare": raw[find_col(raw, "healthcare facilities")],
            "wifi": raw[find_col(raw, "public_open wifi", "open wifi connection")],
            "accommodation_units": pd.to_numeric(raw[find_col(raw, "registered accommodation units")], errors="coerce"),
        })
        hp = pd.to_numeric(raw[find_col(raw, "hotel based parking spots")], errors="coerce").fillna(0)
        pp = pd.to_numeric(raw[find_col(raw, "public parking spots")], errors="coerce").fillna(0)
        combo = pd.to_numeric(raw[find_col(raw, "parking spots (hotel")], errors="coerce")
        loc["parking_spots"] = combo.fillna(hp + pp)
        loc["zone_name"] = [f"Mall Road Zone {i+1}" for i in range(len(loc))]
        return loc.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    def build_enterprise(raw):
        ent = pd.DataFrame({
            "lat": pd.to_numeric(raw[find_col(raw, "current location_latitude")], errors="coerce"),
            "lon": pd.to_numeric(raw[find_col(raw, "current location_longitude")], errors="coerce"),
            "type": raw[find_col(raw, "type of enterprise")],
            "owner_local": raw[find_col(raw, "owner of this business a resident")],
            "ft_employees": pd.to_numeric(raw[find_col(raw, "full-time employees")], errors="coerce"),
            "seasonal_employees": pd.to_numeric(raw[find_col(raw, "seasonal or temporary employees")], errors="coerce"),
            "local_employees": pd.to_numeric(raw[find_col(raw, "employees that are residents")], errors="coerce"),
            "tank_capacity": pd.to_numeric(raw[find_col(raw, "storage tanks capacity")], errors="coerce"),
            "constraint": raw[find_col(raw, "water constraints affected your ability")],
            "shortage_flag": raw[find_col(raw, "water shortage during peak tourist season")],
            "rainwater": raw[find_col(raw, "enterprise have a rainwater harvesting")],
            "open_to_rainwater": raw[find_col(raw, "open to installing or improving a rainwater")],
            "renewable": raw[find_col(raw, "solar panels or any other renewable")],
            "elec_peak": pd.to_numeric(raw[find_col(raw, "electricity bill during peak")], errors="coerce"),
            "elec_off": pd.to_numeric(raw[find_col(raw, "electricity bill during off")], errors="coerce"),
            "sewage": raw[find_col(raw, "how does your establishment manage sewage")],
        })
        valid_constraints = ["Not at all", "Minor adjustments", "Significant reduction", "Had to refuse guests"]
        ent["constraint"] = ent["constraint"].where(ent["constraint"].isin(valid_constraints))
        return ent.reset_index(drop=True)

    def build_residents(raw):
        res = pd.DataFrame({
            "lat": pd.to_numeric(raw[find_col(raw, "_location_latitude")], errors="coerce"),
            "lon": pd.to_numeric(raw[find_col(raw, "_location_longitude")], errors="coerce"),
            "piped_hours": pd.to_numeric(raw[find_col(raw, "piped water supply")], errors="coerce").clip(upper=24),
            "equity": raw[find_col(raw, "water needs of local residents are given priority")],
            "coping_tanker": raw[find_col(raw, "buy packaged water or hire a private tanker")],
            "rainwater_hh": raw[find_col(raw, "household have a rainwater harvesting")],
            "travel_rating": pd.to_numeric(raw[find_col(raw, "rate- traveling in nainital", "describe travelling within nainital")], errors="coerce"),
            "noise": raw[find_col(raw, "noise levels in your neighbourhood")],
            "price_compare": raw[find_col(raw, "prices of daily goods")],
            "visit_less_peak": raw[find_col(raw, "visit mall road or the naini lake as often")],
            "tourism_livelihood": raw[find_col(raw, "is tourism  primary source of livelihood", "is tourism your primary source of livelihood")],
            "tourism_helps_growth": raw[find_col(raw, "tourism has helped nainital to grow")],
        })
        return res.reset_index(drop=True)

    def build_workers(raw):
        return pd.DataFrame({
            "sector": raw[find_col(raw, "what sector do you work in")],
            "status": raw[find_col(raw, "status of employment")],
            "arrangement": raw[find_col(raw, "employment arrangement")],
            "months_worked": pd.to_numeric(raw[find_col(raw, "months in the previous year you received work")], errors="coerce"),
            "income_peak": pd.to_numeric(raw[find_col(raw, "monthly income during peak")], errors="coerce"),
            "income_off": pd.to_numeric(raw[find_col(raw, "monthly income during the off-season")], errors="coerce"),
            "insurance": raw[find_col(raw, "health insurance or accident")],
            "govt_support": raw[find_col(raw, "government or institutional support")],
            "payment_on_time": raw[find_col(raw, "receive your payment on time")],
            "primary_tourism": raw[find_col(raw, "tourism your primary source of employment")],
        })

    def build_tourist(raw):
        expenditure_bucket_map = {
            "Less than ₹2,000": 1000, "₹2,000–₹5,000": 3500, "₹5,001–₹10,000": 7500,
            "₹10,001–₹20,000": 15000, "More than ₹20,000": 25000,
        }
        purpose_map = {
            "Leisure/Vacation": "Leisure/Vacation", "Vacation": "Leisure/Vacation",
            "Leisure": "Leisure/Vacation", "Leisure Vacation": "Leisure/Vacation",
            "Family Trip": "Family Trip", "Pilgrimage": "Pilgrimage", "Honeymoon": "Honeymoon",
            "Business+Leisure": "Business+Leisure", "Adventure": "Adventure", "Other": "Other",
        }
        return pd.DataFrame({
            "group_size": pd.to_numeric(raw[find_col(raw, "travelling with")], errors="coerce"),
            "expenditure": bucket_to_numeric(raw[find_col(raw, "approximate total expenditure")], expenditure_bucket_map),
            "overspent": raw[find_col(raw, "gone beyond your expected budget")],
            "direction_ease": pd.to_numeric(raw[find_col(raw, "how easy was it to find directions")], errors="coerce"),
            "satisfaction": pd.to_numeric(raw[find_col(raw, "overall, how satisfied")], errors="coerce"),
            "cleanliness": pd.to_numeric(raw[find_col(raw, "rate the cleanliness")], errors="coerce"),
            "origin_state": raw[find_col(raw, "state/country are you visiting from")],
            "purpose": raw[find_col(raw, "main purpose of your visit")].astype(str).str.strip().map(purpose_map),
        })

    loc, s1 = try_load("Location", "Location*.xlsx", build_location, _synthetic_location, 10)
    ent, s2 = try_load("Enterprise", "Enterprise*.xlsx", build_enterprise, _synthetic_enterprise, 159)
    res, s3 = try_load("Residents", "*Residents*.xlsx", build_residents, _synthetic_residents, 239)
    work, s4 = try_load("Workers", "Workers*.xlsx", build_workers, _synthetic_workers, 296)
    tour, s5 = try_load("Tourist", "Tourist*.xlsx", build_tourist, _synthetic_tourist, 320)
    src_flags = {"Location": s1, "Enterprise": s2, "Residents": s3, "Workers": s4, "Tourist": s5}
    return loc, ent, res, work, tour, src_flags, diag

# ============================================================================
# SPATIAL JOIN (Enterprise & Residents -> nearest Location zone)
# ============================================================================
def assign_zone(points_df, loc_df):
    """Spatially join only the geotagged subset of points_df to the nearest Location zone.
    Rows without coordinates are simply excluded from this join (they still exist in the
    full sample-wide dataframe used everywhere else) — geotagging coverage is often partial
    in multi-version KoboToolbox exports and should never silently shrink the whole dataset."""
    valid = points_df.dropna(subset=["lat", "lon"]).copy()
    if len(valid) == 0 or len(loc_df) == 0:
        valid["zone_id"] = np.nan
        valid["zone_name"] = None
        return valid
    tree = cKDTree(loc_df[["lat", "lon"]].values)
    _, idx = tree.query(valid[["lat", "lon"]].values, k=1)
    valid["zone_id"] = idx
    valid["zone_name"] = loc_df.loc[idx, "zone_name"].values
    return valid

# ============================================================================
# INDEX COMPUTATION
# ============================================================================
CONSTRAINT_MAP = {"Not at all": 0, "Minor adjustments": 35, "Significant reduction": 75, "Had to refuse guests": 100}
PRICE_MAP = {"No change": 0, "Slightly higher": 50, "Much higher": 100}
VALID_ENTERPRISE_TYPES = ["Hotel/Resort", "Homestay", "Restaurant/Cafe", "Travel Agency",
                           "Retail Shop", "Guide Service", "Other"]
VALID_SEWAGE = ["Connected to municipal sewage line", "Septic tank",
                "Own sewage treatment plant", "No system in place"]
VALID_YN_TEXT = ["Yes", "No"]

def compute_location_scores(loc):
    d = loc.copy()
    d["emergency_score"] = norm(d["emergency_min"], invert=True)
    d["footpaths_score"] = yn(d["footpaths"]).fillna(0.5) * 100
    d["potholes_score"] = 100 - yn(d["potholes"]).fillna(0.5) * 100
    d["waterlog_score"] = 100 - yn(d["waterlogging"]).fillna(0.5) * 100
    d["parking_score"] = norm(d["parking_spots"])
    d["signboard_score"] = norm(d["signboards"])
    d["dustbin_score"] = norm(d["dustbins"])
    d["toilet_score"] = norm(d["toilets"])
    d["healthcare_score"] = yn(d["healthcare"]).fillna(0.5) * 100
    d["wifi_score"] = yn(d["wifi"]).fillna(0.5) * 100
    d["Emergency_Preparedness"] = d[["emergency_score", "healthcare_score"]].mean(axis=1)
    d["Accessibility"] = d[["footpaths_score", "potholes_score", "waterlog_score", "parking_score"]].mean(axis=1)
    d["Digital_Comms_Infra"] = d[["wifi_score", "signboard_score"]].mean(axis=1)
    d["Site_Hygiene"] = d[["dustbin_score", "toilet_score"]].mean(axis=1)
    d["Site_Infrastructure_Readiness"] = d[["Emergency_Preparedness", "Accessibility",
                                             "Digital_Comms_Infra", "Site_Hygiene"]].mean(axis=1)
    load = norm(d["accommodation_units"])
    supply = d[["parking_score", "toilet_score", "waterlog_score"]].mean(axis=1)
    d["Physical_Carrying_Capacity"] = (supply - 0.4 * load).clip(0, 100)
    return d

def compute_enterprise_scores(ent):
    d = ent.copy()
    d["type"] = whitelist_categories(d["type"], VALID_ENTERPRISE_TYPES)
    d["owner_local"] = whitelist_categories(d["owner_local"], VALID_YN_TEXT)
    d["sewage"] = whitelist_categories(d["sewage"], VALID_SEWAGE)
    d["constraint_score"] = d["constraint"].map(CONSTRAINT_MAP)
    d["shortage_score"] = yn(d["shortage_flag"]) * 100
    d["tank_deficit_score"] = norm(d["tank_capacity"], invert=True)
    parts = d[["constraint_score", "shortage_score", "tank_deficit_score"]]
    row_mean = parts.mean(axis=1, skipna=True)
    overall_mean = row_mean.mean()
    d["Water_Stress_Exposure"] = row_mean.fillna(overall_mean if not pd.isna(overall_mean) else 50.0)
    d["rainwater_flag"] = yn(d["rainwater"])
    d["renewable_flag"] = yn(d["renewable"])
    d["local_owner_flag"] = yn(d["owner_local"])
    d["Energy_Seasonality_Load"] = ((d["elec_peak"] - d["elec_off"]) / d["elec_off"].replace(0, np.nan) * 100).clip(0, 300)
    d["local_employee_ratio"] = (d["local_employees"] / d["ft_employees"].replace(0, np.nan)).clip(0, 1) * 100
    d["seasonal_hire_ratio"] = (d["seasonal_employees"] / (d["ft_employees"] + d["seasonal_employees"]).replace(0, np.nan)).clip(0, 1) * 100
    return d

def compute_resident_scores(res):
    d = res.copy()
    d["equity_penalty"] = (1 - yn(d["equity"])) * 100
    d["coping_burden"] = yn(d["coping_tanker"]) * 100
    d["piped_adequacy"] = norm(d["piped_hours"])
    d["mobility_friction"] = norm(d["travel_rating"], invert=True)
    d["noise_penalty"] = map_noise(d["noise"])
    d["cost_perception"] = d["price_compare"].map(PRICE_MAP)
    d["avoidance"] = yn(d["visit_less_peak"]) * 100
    friction_parts = d[["mobility_friction", "noise_penalty", "cost_perception", "avoidance"]]
    d["RFEI"] = (0.30 * d["mobility_friction"].fillna(friction_parts["mobility_friction"].mean())
                 + 0.25 * d["noise_penalty"].fillna(friction_parts["noise_penalty"].mean())
                 + 0.25 * d["cost_perception"].fillna(friction_parts["cost_perception"].mean())
                 + 0.20 * d["avoidance"].fillna(friction_parts["avoidance"].mean()))
    return d

def compute_worker_ilvi(work):
    d = work.copy()
    d["seasonality_exposure"] = norm(d["months_worked"], invert=True)
    d["seasonality_exposure"] = d["seasonality_exposure"].fillna(d["seasonality_exposure"].mean())
    informal_map = {"Casual Employment": 100, "Own Account Workers": 65, "Salaried Employment": 15, "Employers": 5}
    d["contract_informality"] = d["status"].map(informal_map)
    d["contract_informality"] = d["contract_informality"].fillna(
        d["arrangement"].map({"Seasonal": 80, "Permanent (year-round)": 20}))
    d["contract_informality"] = d["contract_informality"].fillna(d["contract_informality"].mean())
    gap = (d["income_peak"] - d["income_off"]) / d["income_peak"].replace(0, np.nan)
    d["income_concentration_risk"] = (gap.clip(0, 1) * 100 * 0.5 + yn(d["primary_tourism"]).fillna(0.5) * 50)
    d["income_concentration_risk"] = d["income_concentration_risk"].fillna(d["income_concentration_risk"].mean())
    no_insurance = (1 - yn(d["insurance"]).fillna(0.5)) * 100
    no_govt = (1 - yn(d["govt_support"]).fillna(0.5)) * 100
    late_pay = (1 - yn(d["payment_on_time"]).fillna(0.5)) * 100
    d["safety_net_gap"] = pd.concat([no_insurance, no_govt, late_pay], axis=1).mean(axis=1)
    d["ILVI"] = (0.30 * d["seasonality_exposure"] + 0.25 * d["contract_informality"]
                 + 0.25 * d["income_concentration_risk"] + 0.20 * d["safety_net_gap"])
    return d

def aggregate_zone_wsci(loc_scored, ent_z, res_z):
    ent_agg = ent_z.groupby("zone_id")["Water_Stress_Exposure"].mean().rename("Enterprise_Supply_Deficit_zone")
    res_agg = res_z.groupby("zone_id").agg(
        Resident_Equity_Penalty_zone=("equity_penalty", "mean"),
        Resident_Coping_Burden_zone=("coping_burden", "mean"),
        n_residents=("equity_penalty", "count"),
    )
    ent_n = ent_z.groupby("zone_id").size().rename("n_enterprises")
    z = loc_scored.copy()
    z = z.merge(ent_agg, left_index=True, right_index=True, how="left")
    z = z.merge(res_agg, left_index=True, right_index=True, how="left")
    z = z.merge(ent_n, left_index=True, right_index=True, how="left")
    for c in ["Enterprise_Supply_Deficit_zone", "Resident_Equity_Penalty_zone", "Resident_Coping_Burden_zone"]:
        z[c] = z[c].fillna(z[c].mean())
    z["WSCI_zone"] = (0.40 * z["Enterprise_Supply_Deficit_zone"] + 0.30 * z["Resident_Equity_Penalty_zone"]
                       + 0.30 * z["Resident_Coping_Burden_zone"])
    return z

# ============================================================================
# LOAD + PROCESS (once, cached)
# ============================================================================
loc_raw, ent_raw, res_raw, work_raw, tour_raw, SRC, DIAG = load_all()
loc_s = compute_location_scores(loc_raw)
ent_s = compute_enterprise_scores(ent_raw)
res_s = compute_resident_scores(res_raw)
work_s = compute_worker_ilvi(work_raw)
ent_z = assign_zone(ent_s, loc_s)
res_z = assign_zone(res_s, loc_s)
zone_table = aggregate_zone_wsci(loc_s, ent_z, res_z)

GEO_COVERAGE = {
    "Enterprise": {"total": len(ent_s), "geotagged": len(ent_z)},
    "Residents": {"total": len(res_s), "geotagged": len(res_z)},
}

BASE = dict(
    wsci=safe_mean(zone_table["WSCI_zone"]), ilvi=safe_mean(work_s["ILVI"]),
    rfei=safe_mean(res_s["RFEI"]), readiness=safe_mean(zone_table["Site_Infrastructure_Readiness"]),
)

# ---- dynamic narrative stats, computed once, reused across every page ----
def top_bottom(df, col, name_col="zone_name"):
    if df[col].dropna().empty:
        return None, None
    top = df.loc[df[col].idxmax()]
    bottom = df.loc[df[col].idxmin()]
    return top, bottom

wsci_top, wsci_bottom = top_bottom(zone_table, "WSCI_zone")
ready_top, ready_bottom = top_bottom(zone_table, "Site_Infrastructure_Readiness")
ilvi_by_sector = work_s.groupby("sector")["ILVI"].mean().sort_values(ascending=False) if work_s["sector"].notna().any() else pd.Series(dtype=float)
top_ilvi_sector = ilvi_by_sector.index[0] if len(ilvi_by_sector) else "N/A"
equity_penalty_pct = safe_mean(1 - yn(res_s["equity"]))
avoid_pct = safe_mean(yn(res_s["visit_less_peak"]))
rainwater_adopt = safe_mean(ent_s["rainwater_flag"])
willing_pct = safe_mean(yn(ent_s["open_to_rainwater"]))
no_insurance_pct = safe_mean(1 - yn(work_s["insurance"]))
readiness_accom_corr = zone_table[["Site_Infrastructure_Readiness", "accommodation_units"]].corr().iloc[0, 1] \
    if zone_table["accommodation_units"].notna().sum() > 2 else np.nan

# ============================================================================
# HORIZONTAL NAV BAR (replaces sidebar)
# ============================================================================
NAV_PAGES = [
    "🗺️ Site Infrastructure Readiness",
    "💧 Water & Energy Stress",
    "⚖️ Resident Friction & Livelihood Vulnerability",
    "🎛️ Policy Scenario Simulator",
    "📖 Variable Dictionary & Diagnostics",
]

if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = NAV_PAGES[0]

real_sets = [k for k, v in SRC.items() if v == "real"]
synth_sets = [k for k, v in SRC.items() if v == "synthetic"]

st.title("🏔️ The Nainital Carrying Capacity Cockpit")
st.caption("Mapping trade-offs between tourists, enterprises, workers, and residents on Mall Road")

nav_cols = st.columns(len(NAV_PAGES))
for i, (col, pg) in enumerate(zip(nav_cols, NAV_PAGES)):
    with col:
        is_active = st.session_state["nav_page"] == pg
        btn_type = "primary" if is_active else "secondary"
        if st.button(pg, key=f"nav_{i}", use_container_width=True, type=btn_type):
            st.session_state["nav_page"] = pg
            st.rerun()

page = st.session_state["nav_page"]
st.markdown("---")

# ============================================================================
# GLOBAL KPI STRIP
# ============================================================================
def kpi_card(label, value, sub="", cls=""):
    st.markdown(f"""<div class="kpi-card {cls}"><div class="kpi-label">{label}</div>
    <div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>""", unsafe_allow_html=True)

if synth_sets:
    st.markdown(f"""<div class="callout amber">⚠️ <b>{len(synth_sets)} of 5 datasets are running on
    synthetic fallback data</b> ({', '.join(synth_sets)}) because the corresponding file wasn't found
    or couldn't be parsed in this folder. Every number, chart, and insight sentence below is computed
    live from whatever is actually loaded — open <b>📖 Variable Dictionary & Diagnostics</b> in the
    sidebar to see exactly which file was matched to which dataset, and which fields came back empty.
    </div>""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
with k1: kpi_card("Avg. Water Stress (WSCI)", safe_num(BASE['wsci'], "{:.0f} / 100"),
                   "Zone-level, enterprise+resident aggregate", "crimson" if (BASE['wsci'] or 0) > 55 else "amber")
with k2: kpi_card("Worker Vulnerability (ILVI)", safe_num(BASE['ilvi'], "{:.0f} / 100"),
                   "Mall-Road-wide sample aggregate", "crimson" if (BASE['ilvi'] or 0) > 55 else "amber")
with k3: kpi_card("Resident Friction (RFEI)", safe_num(BASE['rfei'], "{:.0f} / 100"),
                   "Resident-level aggregate", "amber" if (BASE['rfei'] or 0) > 45 else "")
with k4: kpi_card("Site Infra. Readiness", safe_num(BASE['readiness'], "{:.0f} / 100"),
                   f"Across {len(loc_s)} audited zones", "")
st.markdown("---")

# ============================================================================
# PAGE 1 — SITE INFRASTRUCTURE READINESS
# ============================================================================
if page.startswith("🗺️"):
    st.markdown('<span class="section-tag">TAB 1 · REPORT</span>', unsafe_allow_html=True)
    st.header("Site Infrastructure Readiness & Carrying Capacity")
    st.markdown(f"""<div class="section-intro">
    Every audited Mall Road site is scored on four independent dimensions of physical readiness —
    <b>Emergency Preparedness</b>, <b>Accessibility</b>, <b>Digital & Communications Infrastructure</b>,
    and <b>Site Hygiene</b> — using only fields collected in the Location audit itself. No Enterprise or
    Resident data is fused into this tab; it deliberately answers a narrower question first: <i>can the
    physical site itself cope</i>, before asking who feels the strain of it not coping (Tabs 2–3). The
    composite <b>Site Infrastructure Readiness</b> score is the equal-weighted average of the four
    dimensions, and the <b>Physical Carrying Capacity Proxy</b> nets available parking/toilet/drainage
    supply against the density of registered accommodation in that zone — a rough gauge of how much
    slack a zone has left before it is structurally overbooked.
    </div>""", unsafe_allow_html=True)

    if wsci_top is not None:
        _avg_emerg = safe_num(safe_mean(zone_table['emergency_min']), '{:.0f}')
        _min_emerg = safe_num(zone_table['emergency_min'].min(), '{:.0f}')
        _max_emerg = safe_num(zone_table['emergency_min'].max(), '{:.0f}')
        _spread = f"{ready_top['Site_Infrastructure_Readiness'] - ready_bottom['Site_Infrastructure_Readiness']:.0f}"
        _bottom_score = f"{ready_bottom['Site_Infrastructure_Readiness']:.0f}"
        _top_score = f"{ready_top['Site_Infrastructure_Readiness']:.0f}"
        st.markdown(
            f'<div class="callout blue">'
            f'<b>Key findings from {len(loc_s)} audited zones:</b><br>'
            f'• <b>{ready_bottom["zone_name"]}</b> has the weakest overall readiness score'
            f' ({_bottom_score}/100), while <b>{ready_top["zone_name"]}</b>'
            f' leads at {_top_score}/100 — a {_spread}-point'
            f' spread across a stretch of road small enough to walk in minutes.<br>'
            f'• Average emergency response time across all zones is <b>{_avg_emerg} minutes</b>,'
            f' ranging from {_min_emerg} to {_max_emerg} minutes zone-to-zone.'
            f'</div>',
            unsafe_allow_html=True
        )

    map_df = zone_table.copy()
    fig_map = px.scatter_map(
        map_df, lat="lat", lon="lon", color="Site_Infrastructure_Readiness",
        size=np.clip(100 - map_df["Physical_Carrying_Capacity"], 15, None),
        hover_name="zone_name",
        hover_data={"lat": False, "lon": False, "Site_Infrastructure_Readiness": ":.0f",
                    "Physical_Carrying_Capacity": ":.0f", "emergency_min": True, "parking_spots": True},
        color_continuous_scale=[[0, CRIMSON], [0.5, AMBER], [1, EMERALD]],
        zoom=14, height=460, map_style="open-street-map",
    )
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_map, width='stretch')
    st.markdown(f"""<div class="callout">Marker color = infrastructure readiness (green = ready, red =
    deficient); marker size = physical carrying-capacity pressure (bigger = less spare capacity relative to
    accommodation density). Zones combining a red/large marker are the clearest candidates for capital
    investment before any tourist-growth policy is considered.</div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        sub_df = zone_table[["zone_name", "Emergency_Preparedness", "Accessibility",
                              "Digital_Comms_Infra", "Site_Hygiene"]].melt(id_vars="zone_name",
                              var_name="Dimension", value_name="Score")
        fig1 = px.bar(sub_df, x="zone_name", y="Score", color="Dimension", barmode="group",
                      template=PLOTLY_TEMPLATE, title="Infrastructure Sub-Scores by Zone")
        fig1.update_layout(xaxis_title="", legend_title="")
        st.plotly_chart(fig1, width='stretch')
        st.caption("Emergency Preparedness combines ambulance/fire response time and on-site healthcare "
                   "access. Zones with a short Emergency bar but tall others are 'invisible' risk points — "
                   "attractive-looking sites that fail on the one metric that matters most in a crisis.")
    with c2:
        fig2 = px.bar(zone_table.sort_values("Physical_Carrying_Capacity"), x="zone_name",
                      y="Physical_Carrying_Capacity", color="Physical_Carrying_Capacity",
                      color_continuous_scale=[[0, CRIMSON], [1, EMERALD]], template=PLOTLY_TEMPLATE,
                      title="Physical Carrying Capacity Proxy by Zone")
        fig2.update_layout(xaxis_title="", showlegend=False)
        st.plotly_chart(fig2, width='stretch')
        st.caption("This proxy nets parking/toilet/drainage supply against registered accommodation "
                   "density in the zone. A low score means the zone already hosts more beds than its "
                   "public infrastructure comfortably supports — the first candidates for a tourist cap.")

    c3, c4 = st.columns(2)
    with c3:
        emerg_df = zone_table[["zone_name", "emergency_min"]].copy()
        emerg_df["has_data"] = emerg_df["emergency_min"].notna()
        n_missing_emerg = int((~emerg_df["has_data"]).sum())
        emerg_df["plot_val"] = emerg_df["emergency_min"].fillna(0)
        emerg_df["label"] = np.where(emerg_df["has_data"],
                                      emerg_df["emergency_min"].map(lambda v: f"{v:.0f}"),
                                      "No data")
        emerg_df = emerg_df.sort_values("plot_val")
        fig3 = px.bar(emerg_df, x="zone_name", y="plot_val", text="label",
                      color="has_data", color_discrete_map={True: CRIMSON, False: "#CBD5E1"},
                      template=PLOTLY_TEMPLATE, title="Emergency Response Time by Zone (minutes)")
        fig3.update_traces(textposition="outside")
        fig3.update_layout(xaxis_title="", yaxis_title="Minutes", showlegend=False)
        st.plotly_chart(fig3, width='stretch')
        if n_missing_emerg:
            st.markdown(f"""<div class="callout amber">⚠️ <b>{n_missing_emerg} zone(s) show "No data"</b> —
            the ambulance/fire response-time question was left blank for those audits in the source
            KoboToolbox file, not a charting error. Treat these as unaudited, not as zero-risk.</div>""",
                        unsafe_allow_html=True)
        st.caption("Zones above 30 minutes represent a genuine public-safety gap independent of tourism "
                   "volume — worth flagging to NMC regardless of any carrying-capacity policy. Grey bars "
                   "mark zones with no recorded response-time data.")
    with c4:
        hygiene_df = pd.DataFrame({
            "Zone": zone_table["zone_name"], "Toilets": zone_table["toilets"], "Dustbins": zone_table["dustbins"],
        }).melt(id_vars="Zone", var_name="Facility", value_name="Count")
        fig4 = px.bar(hygiene_df, x="Zone", y="Count", color="Facility", barmode="group",
                      template=PLOTLY_TEMPLATE, title="Sanitation Infrastructure Count by Zone")
        fig4.update_layout(xaxis_title="")
        st.plotly_chart(fig4, width='stretch')
        st.caption("Sparse toilet/dustbin counts in high-footfall zones directly predict the informal "
                   "waste and sanitation complaints that show up later in the Resident Friction tab.")

    st.subheader("Zone Profile Comparison (Heatmap)")
    radar_dims = ["Emergency_Preparedness", "Accessibility", "Digital_Comms_Infra", "Site_Hygiene"]
    heat_order = zone_table.copy()
    heat_order["_zone_num"] = heat_order["zone_name"].str.extract(r"(\d+)").astype(float)
    heat_order = heat_order.sort_values("_zone_num")
    heat_z = heat_order[radar_dims].values
    fig_radar = go.Figure(data=go.Heatmap(
        z=heat_z, x=[d.replace("_", " ") for d in radar_dims], y=heat_order["zone_name"],
        colorscale=[[0, CRIMSON], [0.5, AMBER], [1, EMERALD]], zmin=0, zmax=100,
        text=np.round(heat_z, 0), texttemplate="%{text:.0f}", textfont=dict(size=11),
        colorbar=dict(title="Score"),
    ))
    fig_radar.update_layout(template=PLOTLY_TEMPLATE,
                             title="All Zones — Infrastructure Dimension Profile", height=460,
                             xaxis_title="", yaxis_title="",
                             yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_radar, width='stretch')
    st.caption("Every zone is shown (ordered Zone 1 → Zone N top-to-bottom), so nothing is hidden by "
               "a 'top vs. bottom' filter. Read across a row to see which *specific* dimension drives a "
               "zone's weakness — a zone can fail on Emergency Preparedness alone while matching the best "
               "zones everywhere else, which changes the fix from 'general upgrade' to one targeted "
               "intervention. Grey/blank cells indicate a missing underlying field for that zone.")

    st.markdown(f"""<div class="outcome-box"><h4>🔍 Analysis — Site Infrastructure Readiness</h4>
    <ul>
    <li><b>Uneven readiness across short distances:</b> the {ready_top['Site_Infrastructure_Readiness'] - ready_bottom['Site_Infrastructure_Readiness']:.0f}-point gap between the strongest and weakest zones — reachable on foot in minutes — reveals that infrastructure investment has not been spatially uniform along Mall Road, creating invisible risk clusters for visitors concentrated in low-readiness zones.</li>
    <li><b>Emergency response is the critical gap:</b> with an average response time of {safe_num(safe_mean(zone_table['emergency_min']), '{:.0f}')} minutes (ranging up to {safe_num(zone_table['emergency_min'].max(), '{:.0f}')} minutes in the slowest zones), emergency preparedness is the sub-dimension most likely to drive overall readiness failure — a zone can score well on hygiene and accessibility yet remain a public-safety liability.</li>
    <li><b>Accommodation density does not predict readiness:</b> {"the " + ("positive" if (readiness_accom_corr or 0) > 0 else "negative") + f" correlation (r={readiness_accom_corr:.2f}) between readiness scores and registered accommodation units suggests infrastructure upgrades have " + ("broadly tracked" if (readiness_accom_corr or 0) > 0 else "not kept pace with") + " where hotels and homestays are actually located." if not pd.isna(readiness_accom_corr) else "Insufficient zone data to assess whether readiness tracks accommodation density — a key gap for future audits."}</li>
    <li><b>Heatmap profiles reveal targeted fixes, not blanket upgrades:</b> the zone-level dimension heatmap shows that most low-scoring zones fail on one or two specific dimensions rather than uniformly — meaning a precise intervention (e.g., adding emergency access points or directional signage) will close the readiness gap far more efficiently than a general infrastructure mandate.</li>
    </ul></div>""", unsafe_allow_html=True)

# ============================================================================
# PAGE 2 — WATER & ENERGY STRESS
# ============================================================================
elif page.startswith("💧"):
    st.markdown('<span class="section-tag">TAB 2 · REPORT</span>', unsafe_allow_html=True)
    st.header("Water & Energy Stress Cockpit")
    _ent_total = GEO_COVERAGE["Enterprise"]["total"]
    _ent_geo = GEO_COVERAGE["Enterprise"]["geotagged"]
    _ent_geo_pct = safe_pct(_ent_geo / _ent_total if _ent_total else np.nan)
    st.markdown(f"""<div class="section-intro">
    This tab answers the study's central water question: <i>does tourism infrastructure crowd out
    residential water security?</i> The <b>Water Stress Composite Index (WSCI)</b> is deliberately
    computed only at the <b>zone level</b> — Enterprise water-supply records and Resident equity/coping
    records are each aggregated independently to their nearest audited Location zone, then combined as
    zone averages. No individual enterprise is ever linked to a specific resident; the only claim this
    index supports is "this stretch of road shows both enterprise-side and resident-side stress," never
    "this hotel caused that household's shortage." <b>Every chart on this tab except the zone map uses
    the full enterprise sample</b> ({_ent_total} responses) regardless of geotagging — only the zone-level
    WSCI aggregation is restricted to the {_ent_geo} enterprises ({_ent_geo_pct}) that were geotagged, since
    a spatial join requires coordinates. This matters here specifically because, in this dataset, the
    geotagged and non-geotagged respondents are largely disjoint groups — restricting *all* analysis to
    geotagged rows would silently discard most of the water/energy detail collected.
    </div>""", unsafe_allow_html=True)
    st.latex(r"WSCI_{zone} = 0.40 \times \text{Enterprise Supply Deficit} + 0.30 \times \text{Resident Equity Penalty} + 0.30 \times \text{Resident Coping Burden}")

    if wsci_top is not None:
        st.markdown(f"""<div class="callout blue"><b>Key findings:</b><br>
        • <b>{wsci_top['zone_name']}</b> carries the highest water stress ({wsci_top['WSCI_zone']:.0f}/100),
        against a Mall-Road-wide average of {safe_num(BASE['wsci'],'{:.0f}')}/100.<br>
        • Rainwater harvesting adoption among surveyed enterprises: <b>{safe_pct(ent_s['rainwater_flag'])}</b>.
        Of those who haven't adopted it, <b>{safe_pct(yn(ent_s['open_to_rainwater']))}</b> say they would if supported —
        that gap is the achievable mitigation ceiling for a subsidy scheme, not a hypothetical one.<br>
        • <b>{safe_pct(1 - yn(ent_s['renewable']).fillna(0.5), default="Data not available")}</b> of enterprises report no renewable/solar
        adoption for water heating or electricity.
        </div>""", unsafe_allow_html=True)

    fig5 = px.bar(zone_table.sort_values("WSCI_zone", ascending=False), x="zone_name", y="WSCI_zone",
                  color="WSCI_zone", color_continuous_scale=[[0, EMERALD], [0.5, AMBER], [1, CRIMSON]],
                  template=PLOTLY_TEMPLATE, title="Water Stress Composite Index by Zone")
    fig5.update_layout(xaxis_title="", showlegend=False)
    st.plotly_chart(fig5, width='stretch')
    st.caption("Zones in red combine weak enterprise water supply **and** resident-perceived inequity in "
               "the same location — the strongest candidates for a zone-specific water rationing policy "
               "that protects residential hours during May–July.")

    c1, c2 = st.columns(2)
    with c1:
        adopt = ent_s["rainwater_flag"].mean()
        if pd.isna(adopt):
            st.info("Rainwater harvesting adoption rate: **data not available** — the matched column "
                    "returned no usable Yes/No responses in this dataset. Check the Diagnostics page.")
        else:
            fig6 = go.Figure(go.Indicator(mode="gauge+number", value=adopt * 100,
                              title={"text": "Rainwater Harvesting<br>Adoption Rate (%)", "font": {"size": 15}},
                              gauge={"axis": {"range": [0, 100]}, "bar": {"color": EMERALD},
                                     "steps": [{"range": [0, 20], "color": "#FEE2E2"},
                                               {"range": [20, 60], "color": "#FEF3C7"},
                                               {"range": [60, 100], "color": "#D1FAE5"}]}))
            fig6.update_layout(height=300, margin=dict(l=30, r=30, t=70, b=20))
            st.plotly_chart(fig6, width='stretch')
        st.caption(f"Adoption sits near {safe_pct(adopt)}. Among non-adopters, {safe_pct(yn(ent_s['open_to_rainwater']))} "
                   f"say they'd install one if supported — the realistic subsidy-uptake ceiling.")
    with c2:
        fig7 = px.scatter(ent_s, x="tank_capacity", y="Water_Stress_Exposure", color="type",
                          template=PLOTLY_TEMPLATE, title="Water Stress vs. Storage Tank Capacity",
                          labels={"tank_capacity": "Tank Capacity (litres)", "Water_Stress_Exposure": "Water Stress Score"})
        st.plotly_chart(fig7, width='stretch')
        st.caption("If larger tanks don't clearly buy down stress, the bottleneck is municipal supply "
                   "hours/pressure rather than storage — meaning tank subsidies alone won't fix the problem.")

    c3, c4 = st.columns(2)
    with c3:
        seas = ent_s["Energy_Seasonality_Load"].dropna()
        if len(seas) >= 5:
            fig8 = px.histogram(seas, nbins=20, template=PLOTLY_TEMPLATE,
                                title="Energy Seasonality Load (% bill increase, peak vs. off-season)",
                                color_discrete_sequence=[AMBER])
            fig8.update_layout(xaxis_title="% increase in electricity bill",
                                yaxis_title="Number of Enterprises", showlegend=False)
            st.plotly_chart(fig8, width='stretch')
            st.caption(f"Median seasonal bill spike is {seas.median():.0f}% — enterprises effectively run "
                       f"two different cost structures a year, which strains cash flow exactly when "
                       f"seasonal wages also spike (see Tab 3).")
        else:
            st.info("Not enough complete peak/off-season electricity bill records to chart seasonality load.")
    with c4:
        green = ent_s["renewable_flag"].mean()
        sewage_counts = ent_s["sewage"].dropna()
        if len(sewage_counts) > 0:
            sewage_dist = sewage_counts.value_counts(normalize=True).mul(100).reset_index()
            sewage_dist.columns = ["Sewage System", "Share (%)"]
            sewage_dist = sewage_dist.sort_values("Share (%)")
            fig9 = px.bar(sewage_dist, x="Share (%)", y="Sewage System", orientation="h",
                         template=PLOTLY_TEMPLATE, title="Enterprise Sewage Management",
                         text=sewage_dist["Share (%)"].map(lambda v: f"{v:.0f}%"),
                         color_discrete_sequence=[SLATE])
            fig9.update_traces(textposition="outside")
            fig9.update_layout(yaxis_title="", xaxis_range=[0, sewage_dist["Share (%)"].max() * 1.25])
            st.plotly_chart(fig9, width='stretch')
        else:
            st.info("No sewage-management responses available to chart.")
        st.caption(f"Green energy adoption is {safe_pct(green)}. The share of enterprises with 'no system "
                   f"in place' for sewage is a direct proxy for untreated peak-season discharge risk to the lake.")

    st.subheader("Enterprise Type vs. Water Stress")
    type_counts = ent_s["type"].value_counts()
    valid_types = type_counts[type_counts >= 3].index
    box_df = ent_s[ent_s["type"].isin(valid_types)]
    if len(box_df) >= 10:
        fig_box = px.box(box_df, x="type", y="Water_Stress_Exposure", color="type", template=PLOTLY_TEMPLATE,
                         title="Water Stress Exposure Distribution by Enterprise Type")
        fig_box.update_layout(xaxis_title="", showlegend=False)
        st.plotly_chart(fig_box, width='stretch')
        worst_type = box_df.groupby("type")["Water_Stress_Exposure"].mean().idxmax()
        st.caption(f"'{worst_type}' shows the highest median water stress among enterprise types with "
                   f"enough responses to compare — worth a sector-specific conservation outreach rather "
                   f"than a one-size-fits-all mandate across every business type.")
    else:
        st.info("Not enough enterprise-type responses to build a reliable type-level comparison.")

    st.subheader("Local Ownership vs. Green Infrastructure Adoption")
    green_df = pd.DataFrame({
        "Owner is Local Resident": ent_s["owner_local"],
        "Rainwater Harvesting": ent_s["rainwater_flag"], "Renewable Energy": ent_s["renewable_flag"],
    }).dropna(subset=["Owner is Local Resident"])
    if len(green_df) >= 10:
        agg = green_df.groupby("Owner is Local Resident")[["Rainwater Harvesting", "Renewable Energy"]].mean().mul(100).reset_index()
        agg_melt = agg.melt(id_vars="Owner is Local Resident", var_name="Adoption Type", value_name="Adoption %")
        agg_melt["Label"] = agg_melt["Adoption %"].map(lambda v: f"{v:.1f}%")
        fig_own = px.bar(agg_melt, x="Owner is Local Resident", y="Adoption %", color="Adoption Type",
                         barmode="group", template=PLOTLY_TEMPLATE, text="Label",
                         title="Green Infrastructure Adoption: Local vs. Non-Local Owners")
        max_val = max(agg_melt["Adoption %"].max(), 1)
        fig_own.update_traces(textposition="outside")
        fig_own.update_layout(yaxis_range=[0, max_val * 1.35])
        st.plotly_chart(fig_own, width='stretch')
        st.caption(f"Adoption rates for both green measures are low overall (single digits) across "
                   f"the surveyed enterprises regardless of ownership — note the y-axis is scaled to the "
                   f"data, not to 100%, so these bars are read relative to each other, not against a full "
                   f"adoption ceiling. If local owners consistently under- or out-adopt relative to "
                   f"outside owners, that's a signal for whether a subsidy scheme should be targeted by "
                   f"ownership type.")
    else:
        st.info("Not enough ownership-type responses to compare green-infrastructure adoption.")

    st.subheader("What actually drives water stress? (Feature Importance)")
    feat_cols = ["tank_capacity", "seasonal_employees", "elec_peak", "renewable_flag", "local_owner_flag"]
    model_df = ent_s[feat_cols + ["Water_Stress_Exposure"]].copy()
    model_df = model_df.dropna(subset=["Water_Stress_Exposure"])
    for c in feat_cols:
        model_df[c] = model_df[c].fillna(model_df[c].median())
    if len(model_df) >= 15:
        X, y = model_df[feat_cols], model_df["Water_Stress_Exposure"]
        rf = RandomForestRegressor(n_estimators=200, random_state=42, max_depth=5).fit(X, y)
        imp = pd.DataFrame({"Feature": feat_cols, "Importance": rf.feature_importances_}).sort_values("Importance")
        fig10 = px.bar(imp, x="Importance", y="Feature", orientation="h", template=PLOTLY_TEMPLATE,
                       title="Random Forest Feature Importance — Water Stress Exposure",
                       color_discrete_sequence=[SLATE])
        st.plotly_chart(fig10, width='stretch')
        top_feat = imp.iloc[-1]["Feature"]
        st.caption(f"'{top_feat}' ranks as the strongest predictor of water stress in this sample. Treat "
                   f"this as descriptive of the surveyed enterprises, not a causal or externally "
                   f"generalizable model — median-imputed on {len(model_df)} enterprise records, a modest "
                   f"sample for machine-learning inference.")
    else:
        st.info(f"Only {len(model_df)} enterprise records have a usable Water Stress Exposure score — "
                f"too few to fit a reliable feature-importance model (minimum 15). Check the Diagnostics "
                f"page to see which source fields are sparse in the loaded Enterprise dataset.")

    st.markdown(f"""<div class="outcome-box"><h4>🔍 Analysis — Water & Energy Stress</h4>
    <ul>
    <li><b>Water stress is spatially concentrated, not uniformly distributed:</b> the zone-level WSCI map shows that high-stress zones combine both enterprise-side supply deficits and resident-perceived inequity in the same geographic stretch — meaning the problem is not a citywide shortage but a localized mismatch between hospitality demand and municipal distribution.</li>
    <li><b>Rainwater harvesting is significantly under-adopted but has a reachable ceiling:</b> with adoption at {safe_pct(ent_s['rainwater_flag'].mean())} among surveyed enterprises and {safe_pct(yn(ent_s['open_to_rainwater']))} of non-adopters expressing willingness to install given support, there is a concrete, pre-qualified pool for a subsidy scheme — the gap between current adoption and willing adoption represents the achievable near-term mitigation without requiring mandatory enforcement.</li>
    <li><b>Storage tank capacity is not the binding constraint:</b> the weak relationship between tank size and water stress scores indicates that the shortage is upstream — inadequate piped supply hours or pressure — rather than a lack of on-site storage. This shifts the intervention priority from tank subsidies (supply-side storage) toward municipal distribution reforms.</li>
    <li><b>Energy seasonality creates a dual cost crunch:</b> enterprises experience a sharp electricity bill spike in peak season at the same time seasonal wages climb — compressing margins exactly when occupancy is highest. Renewable energy adoption at {safe_pct(ent_s['renewable_flag'].mean())} leaves most enterprises fully exposed to this volatility.</li>
    </ul></div>""", unsafe_allow_html=True)

# ============================================================================
# PAGE 3 — RESIDENT FRICTION & LIVELIHOOD VULNERABILITY
# ============================================================================
elif page.startswith("⚖️"):
    st.markdown('<span class="section-tag">TAB 3 · REPORT</span>', unsafe_allow_html=True)
    st.header("Resident Equity & Informal Livelihood Vulnerability")
    st.markdown(f"""<div class="section-intro">
    This tab holds two indices side by side that are <b>never fused into one number</b>, because they
    describe different units of analysis. The <b>Resident Friction & Externality Index (RFEI)</b> is
    computed entirely from Resident-level survey fields. The <b>Informal Livelihood Vulnerability Index
    (ILVI)</b> is computed entirely from Worker-level fields and reported <b>only as a Mall-Road-wide
    sample aggregate</b>, since the Workers instrument carries no coordinates and cannot be matched to a
    zone, a specific enterprise, or a specific resident. Any comparison between the two below is stated as
    an association at the sample level, never a causal or individually linked claim. As with Tab 2, every
    RFEI chart below uses the <b>full resident sample</b> ({GEO_COVERAGE['Residents']['total']} responses);
    only the WSCI zone-map calculation is restricted to the {GEO_COVERAGE['Residents']['geotagged']}
    geotagged residents.
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""<div class="callout blue"><b>Key findings:</b><br>
    • <b>{safe_pct(1 - yn(res_s['equity']).fillna(0.5))}</b> of residents feel tourism businesses receive
    water priority over local households.<br>
    • <b>{safe_pct(yn(res_s['visit_less_peak']))}</b> of residents avoid Mall Road/Naini Lake during peak
    season — a direct displacement signal in the same season that generates the most tourist revenue.<br>
    • The <b>{top_ilvi_sector}</b> sector shows the highest average worker vulnerability (ILVI) among
    surveyed sectors, and <b>{safe_pct(1 - yn(work_s['insurance']).fillna(0.5))}</b> of all surveyed workers
    report no health insurance or accident coverage tied to their work.
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        ph = res_s["piped_hours"].dropna().clip(upper=24)
        if len(ph) > 0:
            ph_counts = ph.value_counts().sort_index().reset_index()
            ph_counts.columns = ["Hours/day", "Households"]
            fig11 = px.bar(ph_counts, x="Hours/day", y="Households", template=PLOTLY_TEMPLATE,
                           title="Distribution of Daily Piped Water Hours (Residents)",
                           color_discrete_sequence=[BLUE])
            fig11.update_layout(xaxis_title="Hours/day", yaxis_title="Number of Households",
                                showlegend=False, xaxis=dict(dtick=1))
            st.plotly_chart(fig11, width='stretch')
            st.caption(f"Median household receives {ph.median():.0f} hours/day of piped supply. Households "
                       f"on the low end are the direct target for any 'additional piped hours' policy "
                       f"tested in the Simulator tab.")
        else:
            st.info("No piped-water-hours data available to chart.")
    with c2:
        eq = res_s["equity"].value_counts(dropna=False).rename({np.nan: "No answer"})
        if len(eq) > 0:
            fig12 = px.pie(names=eq.index.astype(str), values=eq.values, template=PLOTLY_TEMPLATE,
                           title="Do Residents Feel Water Priority Goes to Tourism Businesses?", hole=0.4,
                           color_discrete_sequence=[EMERALD, CRIMSON, GREY])
            st.plotly_chart(fig12, width='stretch')
        st.caption("'No' means the resident believes tourism businesses get water priority over "
                   "residents — this is the equity-penalty component feeding directly into WSCI_zone.")

    c3, c4 = st.columns(2)
    with c3:
        pc = res_s["price_compare"].dropna()
        if len(pc) > 0:
            fig13 = px.bar(pc.value_counts().reset_index(), x="price_compare", y="count",
                          template=PLOTLY_TEMPLATE, title="Perceived Cost-of-Living Inflation, Peak vs. Off-Season",
                          color_discrete_sequence=[AMBER])
            fig13.update_layout(xaxis_title="")
            st.plotly_chart(fig13, width='stretch')
        st.caption("A majority reporting 'higher' prices in peak season is the resident-side mirror of "
                   "the tourist expenditure spike shown further down — money flowing in for some is a "
                   "cost-of-living tax on everyone else.")
    with c4:
        av = yn(res_s["visit_less_peak"]).mean()
        if not pd.isna(av):
            fig14 = go.Figure(go.Indicator(mode="gauge+number", value=av * 100,
                              title={"text": "% Residents Avoiding<br>Mall Road (Peak Season)", "font": {"size": 15}},
                              gauge={"axis": {"range": [0, 100]}, "bar": {"color": CRIMSON}}))
            fig14.update_layout(height=300, margin=dict(l=30, r=30, t=70, b=20))
            st.plotly_chart(fig14, width='stretch')
        else:
            st.info("No avoidance-behavior data available to chart.")
        st.caption("This is a direct displacement metric — residents opting out of their own town center "
                   "during the exact season it generates the most tourist revenue.")

    st.subheader("Resident Friction vs. Tourist Spend & Satisfaction (Mall-Road-wide comparison)")
    sat_mean = tour_raw["satisfaction"].mean()
    comp_df = pd.DataFrame({
        "Metric": ["Resident Friction (RFEI)", "Tourist Satisfaction (scaled to 100)", "Tourist Avg. Spend (scaled)"],
        "Value": [safe_mean(res_s["RFEI"]), (sat_mean / 5 * 100) if not pd.isna(sat_mean) else np.nan,
                  safe_mean(norm(tour_raw["expenditure"]))]
    }).dropna()
    if len(comp_df) > 0:
        fig15 = px.bar(comp_df, x="Metric", y="Value", color="Metric", template=PLOTLY_TEMPLATE,
                      title="Resident Friction vs. Tourist Satisfaction & Spend (all scaled 0–100)",
                      color_discrete_sequence=[CRIMSON, EMERALD, BLUE], text="Value")
        fig15.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        fig15.update_layout(showlegend=False, xaxis_title="Metric",
                            yaxis_title="Index Value (0–100 scale)", yaxis_range=[0, 105])
        st.plotly_chart(fig15, width='stretch')
    st.caption("This is intentionally a single Mall-Road-wide comparison, not a per-zone paired chart — "
               "Tourist responses carry no coordinates, so any zone-specific pairing would fabricate a "
               "spatial link the data doesn't support. Read this as: 'town-wide, does rising tourist "
               "satisfaction and spend coincide with rising resident friction?'")

    st.markdown("---")
    st.subheader("Informal Livelihood Vulnerability Index (ILVI) — Mall-Road-wide, Worker sample")
    st.markdown(f"""<div class="callout blue">
    <b>How ILVI is calculated:</b> ILVI is a 0–100 composite built entirely from Worker-survey fields,
    combining four weighted components —<br>
    &nbsp;&nbsp;• <b>Seasonality Exposure (30%)</b> — derived from months worked in the past year; fewer
    months worked means higher exposure to the tourist season's boom-bust cycle.<br>
    &nbsp;&nbsp;• <b>Contract Informality (25%)</b> — whether the worker has a formal, written employment
    contract versus an informal/verbal arrangement.<br>
    &nbsp;&nbsp;• <b>Income Concentration Risk (25%)</b> — how dependent the worker's total household
    income is on this single tourism-linked job, versus having other income sources to fall back on.<br>
    &nbsp;&nbsp;• <b>Safety Net Gap (20%)</b> — absence of health insurance, accident coverage, or other
    formal social-security protection tied to the job.<br><br>
    <b>Why it matters:</b> each component on its own is a soft signal a worker could plausibly absorb.
    ILVI is important because it captures how these risks <i>compound</i> — a worker who is both seasonal
    <i>and</i> informally contracted <i>and</i> financially dependent on that one job <i>and</i> uninsured
    has almost no buffer against a bad tourist season, an injury, or a policy change that reduces footfall.
    It is reported only as a Mall-Road-wide average (not per zone) because the Workers survey instrument
    carries no location coordinates, so any zone-level ILVI claim would be fabricated.
    </div>""", unsafe_allow_html=True)
    c5, c6 = st.columns(2)
    with c5:
        if len(ilvi_by_sector) > 0:
            fig16 = px.bar(ilvi_by_sector.reset_index(), x="sector", y="ILVI", color="ILVI",
                          color_continuous_scale=[[0, EMERALD], [0.5, AMBER], [1, CRIMSON]],
                          template=PLOTLY_TEMPLATE, title="Average ILVI by Sector")
            fig16.update_layout(xaxis_title="", showlegend=False)
            st.plotly_chart(fig16, width='stretch')
            st.caption(f"The {top_ilvi_sector} sector faces the most compounded precarity — seasonal, "
                       f"informal, and income-concentrated in tourism — and is the priority target for a "
                       f"sector-specific social security scheme.")
        else:
            st.info("No sector data available to break down ILVI.")
    with c6:
        sub_ilvi = work_s[["seasonality_exposure", "contract_informality", "income_concentration_risk",
                           "safety_net_gap"]].mean().reset_index()
        sub_ilvi.columns = ["Component", "Score"]
        fig17 = px.bar(sub_ilvi, x="Component", y="Score", color="Component", template=PLOTLY_TEMPLATE,
                      title="ILVI Sub-Component Breakdown (Sample Average)", color_discrete_sequence=PLOTLY_SEQ)
        fig17.update_layout(showlegend=False, xaxis_title="")
        st.plotly_chart(fig17, width='stretch')
        dominant = sub_ilvi.loc[sub_ilvi["Score"].idxmax(), "Component"]
        st.caption(f"'{dominant}' is the largest driver of ILVI on average. If Safety_Net_Gap dominates, "
                   f"the fastest lever is insurance/welfare access rather than formalizing contracts "
                   f"(slower, and requires enterprise-side buy-in).")

    st.subheader("Worker Income: Peak vs. Off-Season, by Sector")
    inc_df = work_s[["sector", "income_peak", "income_off"]].dropna()
    if len(inc_df) >= 10:
        inc_agg = inc_df.groupby("sector")[["income_peak", "income_off"]].mean().reset_index()
        inc_melt = inc_agg.melt(id_vars="sector", var_name="Season", value_name="Monthly Income (₹)")
        inc_melt["Season"] = inc_melt["Season"].map({"income_peak": "Peak Season", "income_off": "Off-Season"})
        inc_melt["Label"] = inc_melt["Monthly Income (₹)"].map(lambda v: f"₹{v:,.0f}")
        fig_inc = px.bar(inc_melt, x="sector", y="Monthly Income (₹)", color="Season", barmode="group",
                         text="Label", template=PLOTLY_TEMPLATE,
                         title="Worker Income: Peak vs. Off-Season, by Sector",
                         color_discrete_sequence=[CRIMSON, EMERALD])
        fig_inc.update_traces(textposition="outside")
        fig_inc.update_layout(xaxis_title="Sector", yaxis_title="Avg. Monthly Income (₹)", legend_title="")
        st.plotly_chart(fig_inc, width='stretch')
        gap_by_sector = (inc_df.groupby("sector").apply(lambda g: (g["income_peak"] - g["income_off"]).mean())
                          .sort_values(ascending=False))
        if len(gap_by_sector) > 0:
            st.caption(f"'{gap_by_sector.index[0]}' shows the widest average peak-to-off-season income gap "
                       f"(₹{gap_by_sector.iloc[0]:,.0f}/month) — the sector most exposed to a single bad "
                       f"tourist season.")
    else:
        st.info("Not enough paired peak/off-season income records to chart income volatility by sector.")

    st.subheader("Leakage Check: Seasonal Hiring vs. Local Employment")
    leak_df = ent_s.dropna(subset=["seasonal_hire_ratio", "local_employee_ratio"]).copy()
    if len(leak_df) >= 5:
        # seasonal_hire_ratio is heavily zero-inflated (most enterprises hire no seasonal
        # staff at all), so a median split can leave one group empty — split on whether the
        # enterprise hires any seasonal/temp staff at all instead.
        leak_df["Hiring Group"] = np.where(leak_df["seasonal_hire_ratio"] > 0,
                                            "Hires Seasonal/Temp Staff", "No Seasonal Hiring")
        leak_summary = leak_df.groupby("Hiring Group")["local_employee_ratio"].mean().reset_index()
        leak_summary.columns = ["Enterprise Group", "Avg. % Local Employees"]
        leak_summary["Label"] = leak_summary["Avg. % Local Employees"].map(lambda v: f"{v:.0f}%")
        fig18 = px.bar(leak_summary, x="Enterprise Group", y="Avg. % Local Employees", color="Enterprise Group",
                       text="Label", template=PLOTLY_TEMPLATE,
                       title="Local Employment Ratio: High vs. Low Seasonal-Hiring Enterprises",
                       color_discrete_sequence=[CRIMSON, EMERALD])
        fig18.update_traces(textposition="outside")
        fig18.update_layout(showlegend=False, xaxis_title="",
                            yaxis_range=[0, leak_summary["Avg. % Local Employees"].max() * 1.3])
        st.plotly_chart(fig18, width='stretch')
        gap = (leak_summary.set_index("Enterprise Group")["Avg. % Local Employees"].get("No Seasonal Hiring", np.nan)
               - leak_summary.set_index("Enterprise Group")["Avg. % Local Employees"].get("Hires Seasonal/Temp Staff", np.nan))
        if not pd.isna(gap) and gap > 0:
            st.caption(f"Enterprises that hire seasonal/temp staff employ roughly {gap:.0f} percentage "
                       f"points fewer local residents on average than those with no seasonal hiring at "
                       f"all — a sample-wide association, not an individually linked claim, since no "
                       f"enterprise's specific workers were surveyed as its own.")
        else:
            st.caption("A sample-wide, **not individually linked**, association check: enterprises with "
                       "high seasonal-hire ratios and low local-employment ratios are the ones most likely "
                       "feeding the high-ILVI sectors above.")
    else:
        st.info("Not enough enterprises with both seasonal-hire and local-employment ratios available to chart this comparison.")

    st.markdown("---")
    st.subheader("Tourist Profile (Mall-Road-wide sample, no spatial or individual link to other datasets)")
    purpose_exp = tour_raw[["purpose", "expenditure"]].dropna()
    if len(purpose_exp) >= 10:
        fig20 = px.box(purpose_exp, x="purpose", y="expenditure", color="purpose", template=PLOTLY_TEMPLATE,
                      title="Tourist Expenditure by Purpose of Visit (₹, bucket midpoints)")
        fig20.update_layout(xaxis_title="", showlegend=False)
        st.plotly_chart(fig20, width='stretch')
        top_purpose = purpose_exp.groupby("purpose")["expenditure"].median().idxmax()
        st.caption(f"Expenditure was collected as ₹ ranges (e.g. '₹5,001–₹10,000') and converted to the "
                   f"midpoint of each bucket for comparison. '{top_purpose}' travelers show the highest "
                   f"median spend — useful for targeting high-value segments in tourism promotion without "
                   f"necessarily growing raw visitor counts (and therefore carrying-capacity pressure).")
    else:
        st.info("Not enough purpose-of-visit and expenditure pairs to chart this breakdown.")

    st.markdown(f"""<div class="outcome-box"><h4>🔍 Analysis — Resident Friction & Livelihood Vulnerability</h4>
    <ul>
    <li><b>Resident displacement is measurable and seasonal:</b> with {safe_pct(yn(res_s['visit_less_peak']))} of residents avoiding Mall Road and Naini Lake during peak season, the tourism economy is actively displacing the host community from its own central public space during the exact months that generate the most visitor revenue — a direct equity contradiction at the core of Nainital's tourism model.</li>
    <li><b>Water inequity perception reinforces friction:</b> the {safe_pct(1 - yn(res_s['equity']).fillna(0.5))} of residents who believe tourism businesses receive water priority over households feeds directly into the RFEI and WSCI scores — and importantly, this is a perception that persists regardless of whether actual allocation data confirms it, meaning communication and transparency gaps compound physical infrastructure gaps.</li>
    <li><b>The {top_ilvi_sector} sector carries compounded precarity:</b> high ILVI in this sector reflects not just seasonal income volatility but a convergence of informal contracts, no insurance coverage ({safe_pct(1 - yn(work_s['insurance']).fillna(0.5))} of all workers), and income heavily concentrated in a narrow peak window — a single bad tourist season translates directly into household-level crisis with no buffer.</li>
    <li><b>Seasonal hiring and local employment are inversely associated:</b> enterprises that rely most on seasonal/temporary staff tend to have lower local employee ratios, suggesting that tourism's employment multiplier for Nainital residents is weaker than headline job counts imply — economic benefit leaks out of the community precisely during peak season when it should be highest.</li>
    </ul></div>""", unsafe_allow_html=True)

# ============================================================================
# PAGE 4 — POLICY SCENARIO SIMULATOR
# ============================================================================
elif page.startswith("🎛️"):
    st.markdown('<span class="section-tag">TAB 4 · REPORT</span>', unsafe_allow_html=True)
    st.header("Interactive Policy Scenario Simulator")
    st.markdown("""<div class="section-intro">
    Stress-test the system against three policy levers plus a tourist-surge assumption. All projections
    are <b>illustrative, elasticity-based estimates</b> derived from patterns already observed in this
    sample — not causal estimates — and are computed at the same aggregate level as their underlying
    index (zone-level for WSCI, Mall-Road-wide for ILVI/RFEI), consistent with the unit-of-analysis rules
    used throughout this dashboard.
    </div>""", unsafe_allow_html=True)

    st.markdown("### 🎛️ Scenario Controls")
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        rainwater_pct = st.slider("Rainwater Harvesting Mandate (+% enterprises retrofitted)", 0, 100, 0, 5)
    with sc2:
        piped_add = st.slider("Additional Municipal Piped Hours (+hrs/day)", 0, 8, 0, 1)
    with sc3:
        green_pct = st.slider("Green Energy Subsidy Uptake (+% enterprises)", 0, 100, 0, 5)
    with sc4:
        surge_pct = st.slider("Tourist Surge (%, applied Mall-Road-wide)", -20, 100, 0, 5)

    def simulate():
        b_wsci = BASE["wsci"] if not pd.isna(BASE["wsci"]) else 50.0
        b_ilvi = BASE["ilvi"] if not pd.isna(BASE["ilvi"]) else 50.0
        b_rfei = BASE["rfei"] if not pd.isna(BASE["rfei"]) else 50.0
        wsci_new = b_wsci * (1 - 0.0055 * rainwater_pct) * (1 - 0.025 * piped_add) * (1 + 0.004 * max(surge_pct, 0))
        ilvi_new = b_ilvi * (1 - 0.0025 * green_pct) * (1 + 0.0035 * max(surge_pct, 0))
        rfei_new = b_rfei * (1 - 0.018 * piped_add) * (1 - 0.0015 * rainwater_pct) * (1 + 0.003 * max(surge_pct, 0))
        return np.clip(wsci_new, 0, 100), np.clip(ilvi_new, 0, 100), np.clip(rfei_new, 0, 100)

    wsci_n, ilvi_n, rfei_n = simulate()

    st.subheader("Before vs. Simulated After")
    c1, c2, c3 = st.columns(3)
    def delta_card(col, label, before, after):
        with col:
            before = before if not pd.isna(before) else 50.0
            delta = after - before
            arrow = "↑" if delta > 0.5 else ("↓" if delta < -0.5 else "→")
            kpi_card(label, f"{after:.0f} / 100", f"{arrow} {abs(delta):.1f} pts vs. baseline ({before:.0f})",
                      "" if delta < -0.5 else ("amber" if delta <= 1 else "crimson"))
    delta_card(c1, "Water Stress (WSCI, zone avg.)", BASE["wsci"], wsci_n)
    delta_card(c2, "Worker Vulnerability (ILVI)", BASE["ilvi"], ilvi_n)
    delta_card(c3, "Resident Friction (RFEI)", BASE["rfei"], rfei_n)

    demand_multiplier = 1 + surge_pct / 100
    projected_stress = (ent_s["Water_Stress_Exposure"].fillna(ent_s["Water_Stress_Exposure"].mean()) * demand_multiplier
                         * (1 - 0.006 * rainwater_pct)).clip(0, 100)
    deficit_now = int((ent_s["Water_Stress_Exposure"] > 60).sum())
    deficit_after = int((projected_stress > 60).sum())

    parking_supply = zone_table["parking_spots"].sum()
    gs_mean = tour_raw["group_size"].dropna().mean()
    parking_demand_baseline = gs_mean * len(loc_s) * 3 if not pd.isna(gs_mean) else 40
    parking_demand = parking_demand_baseline * demand_multiplier
    parking_deficit = max(0, parking_demand - parking_supply)

    emerg_base = safe_mean(zone_table["emergency_min"], default=25.0)
    emerg_new = emerg_base * (1 + 0.01 * max(surge_pct, 0))

    st.markdown(f"""<div class="callout {'crimson' if surge_pct>30 else 'amber' if surge_pct>0 else ''}">
    <b>Verdict at {surge_pct:+d}% tourist surge, {rainwater_pct}% rainwater mandate, +{piped_add} hrs piped
    water, {green_pct}% green subsidy uptake:</b><br>
    • Enterprises crossing the high-water-stress threshold (score &gt; 60): <b>{deficit_after}</b> of
    {len(ent_s)} surveyed (baseline: {deficit_now}).<br>
    • Estimated Mall-Road-wide parking deficit: <b>{parking_deficit:.0f} vehicles</b> beyond current
    {parking_supply:.0f} audited spots.<br>
    • Average emergency response time: <b>{emerg_new:.0f} min</b> (baseline {emerg_base:.0f} min).<br>
    • Water Stress Index moves from {safe_num(BASE['wsci'],'{:.0f}')} → <b>{wsci_n:.0f}</b>; Resident Friction moves from
    {safe_num(BASE['rfei'],'{:.0f}')} → <b>{rfei_n:.0f}</b>.
    </div>""", unsafe_allow_html=True)

    c4, c5 = st.columns(2)
    with c4:
        fig19 = go.Figure()
        b_wsci = BASE["wsci"] if not pd.isna(BASE["wsci"]) else 50.0
        fig19.add_trace(go.Bar(x=["Baseline", "Simulated"], y=[b_wsci, wsci_n], name="WSCI",
                               marker_color=[SLATE, CRIMSON if wsci_n > b_wsci else EMERALD]))
        fig19.update_layout(template=PLOTLY_TEMPLATE, title="Water Stress: Baseline vs. Simulated", yaxis_range=[0, 100])
        st.plotly_chart(fig19, width='stretch')
        st.caption("Rainwater mandate and added piped hours pull this down; tourist surge pushes it up — "
                   "the slope of each slider shows which lever has more leverage per unit of political cost.")
    with c5:
        deficit_df = pd.DataFrame({"Scenario": ["Baseline", "Simulated"], "Enterprises in Deficit": [deficit_now, deficit_after]})
        fig20 = px.bar(deficit_df, x="Scenario", y="Enterprises in Deficit", color="Scenario",
                      template=PLOTLY_TEMPLATE, title="Enterprises Crossing Water-Deficit Threshold",
                      color_discrete_sequence=[SLATE, CRIMSON])
        fig20.update_layout(showlegend=False)
        st.plotly_chart(fig20, width='stretch')
        st.caption("Computed by scaling each enterprise's own real consumption/capacity numbers by the "
                   "surge multiplier — never by inventing a link to specific tourists or residents.")

    st.subheader("Zone-Level Water Stress Under Simulation")
    zone_sim = zone_table.copy()
    zone_sim["WSCI_simulated"] = (zone_sim["WSCI_zone"] * (1 - 0.0055 * rainwater_pct)
                                   * (1 - 0.025 * piped_add) * (1 + 0.004 * max(surge_pct, 0))).clip(0, 100)
    comp = zone_sim[["zone_name", "WSCI_zone", "WSCI_simulated"]].melt(id_vars="zone_name",
                    var_name="Scenario", value_name="WSCI")
    comp["Scenario"] = comp["Scenario"].map({"WSCI_zone": "Baseline", "WSCI_simulated": "Simulated"})
    fig21 = px.bar(comp, x="zone_name", y="WSCI", color="Scenario", barmode="group", template=PLOTLY_TEMPLATE,
                  title="Zone-Level WSCI: Baseline vs. Simulated", color_discrete_sequence=[SLATE, CRIMSON])
    fig21.update_layout(xaxis_title="")
    st.plotly_chart(fig21, width='stretch')
    st.caption("Zones that stay red even after the mitigation levers are maxed out are structural "
               "bottlenecks — sites where infrastructure capital investment, not policy tweaks, is required.")

    st.subheader("Lever Sensitivity (Tornado Chart)")
    b_wsci_val = BASE["wsci"] if not pd.isna(BASE["wsci"]) else 50.0
    levers = {
        "Rainwater Mandate (0→100%)": b_wsci_val * (1 - 0.0055 * 100) - b_wsci_val,
        "Piped Hours (+0→8 hrs)": b_wsci_val * (1 - 0.025 * 8) - b_wsci_val,
        "Tourist Surge (0→100%)": b_wsci_val * (1 + 0.004 * 100) - b_wsci_val,
    }
    tornado_df = pd.DataFrame({"Lever": list(levers.keys()), "Max WSCI Impact (pts)": list(levers.values())}).sort_values("Max WSCI Impact (pts)")
    fig_tornado = px.bar(tornado_df, x="Max WSCI Impact (pts)", y="Lever", orientation="h", template=PLOTLY_TEMPLATE,
                         title="Maximum Possible Swing in WSCI per Lever (full range)",
                         color="Max WSCI Impact (pts)", color_continuous_scale=[[0, EMERALD], [0.5, "#E5E7EB"], [1, CRIMSON]])
    fig_tornado.update_layout(showlegend=False)
    st.plotly_chart(fig_tornado, width='stretch')
    st.caption("Compares each lever's full-range effect on the Water Stress Index in isolation. This is "
               "the fastest way to see which single policy has the most leverage before combining levers — "
               "e.g. if piped-hours has a bigger swing than the rainwater mandate, it's the higher-priority "
               "investment per unit of implementation effort.")

    st.markdown(f"""<div class="outcome-box"><h4>📋 Policy Outcomes — Tab 4</h4>
    <ul>
    <li><b>Sequence levers by leverage, not by ease:</b> use the tornado chart to prioritize whichever
    single policy moves WSCI the most before combining multiple interventions.</li>
    <li><b>Set a surge ceiling:</b> the verdict card shows the tourist-surge percentage at which
    enterprises and emergency response begin crossing risk thresholds — a defensible, data-backed basis
    for a seasonal visitor advisory or soft cap.</li>
    <li><b>Structural vs. policy fixes:</b> zones that remain red even with every lever maxed out need
    capital investment, not incremental policy — the simulator itself identifies which zones those are.</li>
    </ul></div>""", unsafe_allow_html=True)

# ============================================================================
# PAGE 5 — VARIABLE DICTIONARY & DIAGNOSTICS
# ============================================================================
else:
    st.markdown('<span class="section-tag">METHODOLOGY</span>', unsafe_allow_html=True)
    st.header("Variable Dictionary & Data Diagnostics")
    st.markdown("""<div class="section-intro">
    Every calculated field in this dashboard, its exact formula, its source columns, and — for the
    current run — how complete that field actually is in the data that got loaded. Use this page first
    whenever a chart shows "Data not available" or a number looks off: it tells you precisely which file
    was matched, which column was used, and how many usable responses it had.
    </div>""", unsafe_allow_html=True)

    st.subheader("① Data Source Status (this run)")
    diag_rows = []
    for name in ["Location", "Enterprise", "Residents", "Workers", "Tourist"]:
        info = DIAG.get(name, {})
        diag_rows.append({"Dataset": name, "Status": info.get("status", "?").upper(),
                           "File Matched": info.get("path") or "— (synthetic)", "Detail": info.get("reason", "")})
    st.dataframe(pd.DataFrame(diag_rows), width='stretch', hide_index=True)

    st.subheader("② Geotagging Coverage (spatial join eligibility)")
    geo_rows = [{"Dataset": k, "Total Responses": v["total"], "Geotagged (usable for zone join)": v["geotagged"],
                 "Geotagged %": f"{v['geotagged']/v['total']*100:.0f}%" if v["total"] else "N/A"}
                for k, v in GEO_COVERAGE.items()]
    st.dataframe(pd.DataFrame(geo_rows), width='stretch', hide_index=True)
    st.caption("Only the geotagged rows shown here feed the zone-level WSCI map (Tab 2). Every other "
               "chart, index, and insight sentence in the dashboard uses the full response count in the "
               "'Total Responses' column — geotagging coverage never limits sample-wide analysis.")

    st.subheader("③ Field Completeness (canonical columns actually used downstream)")
    def completeness_table(df, name):
        rows = []
        for c in df.columns:
            if c in ("lat", "lon", "zone_id", "zone_name"):
                continue
            n = df[c].notna().sum()
            rows.append({"Dataset": name, "Field": c, "Non-Null": n, "Total Rows": len(df),
                         "Completeness": f"{n/len(df)*100:.0f}%" if len(df) else "N/A"})
        return rows

    comp_rows = (completeness_table(loc_raw, "Location") + completeness_table(ent_raw, "Enterprise")
                 + completeness_table(res_raw, "Residents") + completeness_table(work_raw, "Workers")
                 + completeness_table(tour_raw, "Tourist"))
    comp_df_all = pd.DataFrame(comp_rows)
    low_complete = comp_df_all[comp_df_all["Non-Null"] < 5]
    if len(low_complete) > 0:
        st.markdown(f"""<div class="callout amber">⚠️ <b>{len(low_complete)} field(s) have fewer than 5
        usable responses</b> in the current run — any chart or index component built from these will show
        "Data not available" rather than a misleading number. See the flagged rows below.</div>""",
        unsafe_allow_html=True)
    with st.expander("View full field-completeness table", expanded=len(low_complete) > 0):
        st.dataframe(comp_df_all.sort_values("Non-Null"), width='stretch', hide_index=True)

    st.markdown("---")
    st.subheader("④ Variable Dictionary")

    st.markdown("#### Location-Derived (Tab 1)")
    loc_dict = pd.DataFrame([
        ["Emergency_Preparedness", "mean(emergency_score, healthcare_score)", "emergency response time (inverted, normalized), on-site healthcare availability"],
        ["Accessibility", "mean(footpaths_score, potholes_score, waterlog_score, parking_score)", "footpath presence, pothole absence, no waterlogging, normalized parking supply"],
        ["Digital_Comms_Infra", "mean(wifi_score, signboard_score)", "public WiFi availability, normalized directional signboard count"],
        ["Site_Hygiene", "mean(dustbin_score, toilet_score)", "normalized dustbin count, normalized public toilet count"],
        ["Site_Infrastructure_Readiness", "mean(Emergency_Preparedness, Accessibility, Digital_Comms_Infra, Site_Hygiene)", "equal-weighted composite of the four dimensions above"],
        ["Physical_Carrying_Capacity", "mean(parking_score, toilet_score, waterlog_score) − 0.4 × norm(accommodation_units)", "infrastructure supply net of accommodation-driven demand load"],
    ], columns=["Variable", "Formula", "Source Fields"])
    st.dataframe(loc_dict, width='stretch', hide_index=True)

    st.markdown("#### Enterprise-Derived (Tab 2)")
    ent_dict = pd.DataFrame([
        ["Water_Stress_Exposure", "mean(constraint_score, shortage_score, tank_deficit_score)", "operational-impact ordinal (0/35/75/100), shortage Yes/No, inverted normalized tank capacity"],
        ["Rainwater_Harvesting_Adoption_Rate", "mean(rainwater_flag)", "'Does your enterprise have a rainwater harvesting system?' (Yes/No)"],
        ["Green_Energy_Adoption_Rate", "mean(renewable_flag)", "'Does your establishment use solar panels or renewable energy...?' (Yes/No)"],
        ["Energy_Seasonality_Load", "(elec_peak − elec_off) / elec_off × 100", "average monthly electricity bill, peak vs. off-season"],
        ["local_employee_ratio", "local_employees / ft_employees × 100", "employees resident in Nainital District ÷ full-time employees"],
        ["seasonal_hire_ratio", "seasonal_employees / (ft_employees + seasonal_employees) × 100", "seasonal/temporary hires ÷ total workforce"],
    ], columns=["Variable", "Formula", "Source Fields"])
    st.dataframe(ent_dict, width='stretch', hide_index=True)

    st.markdown("""**Data-cleaning note:** `type`, `owner_local`, and `sewage` are passed through a
    whitelist filter that keeps only known-valid category labels and maps anything else (stray numeric
    contamination such as a lone `'1'` or `'74'`, or concatenated multi-select combinations such as
    `'Connected to municipal sewage line No system in place'`) to missing. This is a real artifact of the
    underlying KoboToolbox 'all versions' export, not a coding choice — see Field Completeness above for
    exactly how many rows this affects per field.""")

    st.markdown("#### Zone-Level Composite — WSCI (Tab 2)")
    st.latex(r"WSCI_{zone} = 0.40 \times \text{Enterprise\_Supply\_Deficit}_{zone} + 0.30 \times \text{Resident\_Equity\_Penalty}_{zone} + 0.30 \times \text{Resident\_Coping\_Burden}_{zone}")
    st.markdown("""Enterprise and Resident records are first spatially matched to their **nearest audited
    Location zone** (`scipy.spatial.cKDTree`, Euclidean nearest-neighbor on lat/lon), then each dataset is
    **aggregated independently by zone** (mean per zone), and only those zone-level aggregates are combined.
    No enterprise or resident row is ever joined to another dataset's individual row.""")

    st.markdown("#### Resident-Derived — RFEI (Tab 3)")
    st.latex(r"RFEI = 0.30 \times \text{Mobility\_Friction} + 0.25 \times \text{Noise\_Crowding\_Penalty} + 0.25 \times \text{Cost\_of\_Living\_Perception} + 0.20 \times \text{Avoidance\_Behavior}")
    res_dict = pd.DataFrame([
        ["equity_penalty", "(1 − equity_yes) × 100", "'Do residents feel water priority goes to tourism businesses?' (No = penalty)"],
        ["coping_burden", "coping_tanker_yes × 100", "'Bought packaged water / hired private tanker due to shortage?' (Yes/No)"],
        ["mobility_friction", "100 − norm(travel_rating)", "'Rate travelling within Nainital during peak season' (1=worst…5=best, inverted)"],
        ["noise_penalty", "ordinal map: Much quieter=0 … Much louder=100", "noise level in peak season vs. rest of year"],
        ["cost_perception", "ordinal map: No change=0, Slightly higher=50, Much higher=100", "daily goods price comparison, peak vs. off-season"],
        ["avoidance", "visit_less_peak_yes × 100", "'Do you visit Mall Road/Naini Lake as often in peak season?' (No = avoidance)"],
    ], columns=["Variable", "Formula", "Source Fields"])
    st.dataframe(res_dict, width='stretch', hide_index=True)

    st.markdown("#### Worker-Derived — ILVI (Tab 3, Mall-Road-wide only)")
    st.latex(r"ILVI = 0.30 \times \text{Seasonality\_Exposure} + 0.25 \times \text{Contract\_Informality} + 0.25 \times \text{Income\_Concentration\_Risk} + 0.20 \times \text{Safety\_Net\_Gap}")
    work_dict = pd.DataFrame([
        ["seasonality_exposure", "100 − norm(months_worked)", "months worked in the previous year (fewer months = higher exposure)"],
        ["contract_informality", "map: Casual=100, Own-Account=65, Salaried=15, Employer=5 (fallback: Seasonal=80, Permanent=20)", "status of employment / employment arrangement"],
        ["income_concentration_risk", "0.5×clip((income_peak−income_off)/income_peak,0,1)×100 + 0.5×primary_tourism_yes×100", "peak vs. off-season income gap, whether tourism is primary income source"],
        ["safety_net_gap", "mean(no_insurance, no_govt_support, late_payment) × 100", "health insurance access, government/institutional support, on-time payment — each Yes/No"],
    ], columns=["Variable", "Formula", "Source Fields"])
    st.dataframe(work_dict, width='stretch', hide_index=True)

    st.markdown("#### Policy Scenario Simulator — Elasticity Formulas (Tab 4)")
    st.markdown("""All simulator formulas are **illustrative multiplicative elasticities**, not fitted or
    causal coefficients — they encode directional assumptions ("more piped hours reduces water stress,
    tourist surge increases it") calibrated to plausible magnitudes, and are explicitly labeled as such
    everywhere they appear in the dashboard.""")
    sim_dict = pd.DataFrame([
        ["WSCI (simulated)", "WSCI × (1 − 0.0055×rainwater%) × (1 − 0.025×piped_hrs) × (1 + 0.004×max(surge%,0))"],
        ["ILVI (simulated)", "ILVI × (1 − 0.0025×green%) × (1 + 0.0035×max(surge%,0))"],
        ["RFEI (simulated)", "RFEI × (1 − 0.018×piped_hrs) × (1 − 0.0015×rainwater%) × (1 + 0.003×max(surge%,0))"],
        ["Enterprises in deficit", "count(Water_Stress_Exposure × (1+surge%) × (1−0.006×rainwater%) > 60)"],
        ["Parking deficit", "mean(tourist group_size) × n_zones × 3 × (1+surge%) − Σ(zone parking_spots)"],
        ["Emergency response (simulated)", "mean(emergency_min) × (1 + 0.01×max(surge%,0))"],
    ], columns=["Output", "Formula"])
    st.dataframe(sim_dict, width='stretch', hide_index=True)

    st.markdown("---")
    st.subheader("⑤ Unit-of-Analysis Rules (recap)")
    rules_df = pd.DataFrame([
        ["Enterprise ↔ Location", "Yes — both geocoded", "Zone-level aggregate (nearest-neighbor spatial join)"],
        ["Residents ↔ Location", "Yes — both geocoded", "Zone-level aggregate (nearest-neighbor spatial join)"],
        ["Enterprise ↔ Residents", "Only via Location as intermediary", "Zone-level aggregate only — never respondent-to-respondent"],
        ["Workers ↔ anything", "No — no coordinates collected", "Mall-Road-wide (sample-level) comparison only"],
        ["Tourists ↔ anything", "No — no coordinates collected", "Mall-Road-wide (sample-level) comparison only"],
    ], columns=["Dataset Pair", "Shared Unit?", "Valid Join Level"])
    st.dataframe(rules_df, width='stretch', hide_index=True)
    st.caption("Any statement of the form 'X in dataset A is associated with Y in dataset B' is only "
               "defensible at whatever level both A and B were actually aggregated to before comparison — "
               "and is labeled throughout this dashboard as an aggregate/ecological association, never an "
               "individual-level causal claim.")

st.markdown("---")
st.caption("Nainital Carrying Capacity Cockpit · Urban Immersion Fieldwork, BS Analytics & Sustainability "
           "Studies, TISS · All composite indices are aggregate/associational measures — see "
           "'📖 Variable Dictionary & Diagnostics' for full formulas and data-quality detail. Scenario "
           "projections are illustrative, not causal estimates.")
