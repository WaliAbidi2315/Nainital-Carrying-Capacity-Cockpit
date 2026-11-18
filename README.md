# Nainital Carrying Capacity Cockpit

**An interactive decision-support dashboard for understanding the pressures of tourism on infrastructure, water and energy systems, residents, workers and local enterprises along Nainital's Mall Road.**

This repository's Streamlit application is the portfolio experience. It is designed to be explored directly: navigate the five dashboard sections, inspect the underlying variable definitions and data diagnostics, and test illustrative policy scenarios.

## Explore the live dashboard

<https://nainital-fw-dashboard.streamlit.app/>

The hosted Streamlit application is the primary portfolio experience. Open it to explore the interactive carrying-capacity cockpit.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

For a hosted portfolio, deploy this repository using [Streamlit Community Cloud](https://share.streamlit.io/): select the repository, branch `main`, and main file `app.py`.

## What the cockpit contains

| Section | What to explore |
|---|---|
| Site Infrastructure Readiness | Emergency preparedness, accessibility, digital communications, hygiene and a physical carrying-capacity proxy |
| Water & Energy Stress | Enterprise water constraints, supply deficits, water harvesting and energy indicators |
| Resident Friction & Livelihood Vulnerability | Resident mobility/noise/cost friction and worker livelihood vulnerability |
| Policy Scenario Simulator | Illustrative changes to tourism surge, piped water, rainwater harvesting and green energy |
| Variable Dictionary & Diagnostics | Formula definitions, source-field completeness, dataset status and geotagging coverage |

## Analytical design

- Five fieldwork datasets: Location, Enterprise, Residents, Workers and Tourist.
- Question-text-based column resolution for KoboToolbox exports.
- Nearest-neighbour zone assignment for geotagged enterprise and resident records using `scipy.spatial.cKDTree`.
- Separate zone-level aggregation before combining enterprise and resident indicators.
- Composite indices documented in the app: Site Infrastructure Readiness, Physical Carrying Capacity Proxy, WSCI, RFEI and ILVI.
- Explicit synthetic-data fallback for demonstration when source files are absent or cannot be parsed.

## Data privacy — read before deployment

The survey exports are respondent-level fieldwork data. **Do not publish raw XLSX/CSV exports in a public repository or deploy them in a public app.** Use an approved anonymised dataset or a private data source, and remove direct identifiers and precise household/business coordinates where appropriate. A `.gitignore` rule does not remove files that are already tracked in Git history.

Configure private data using `APP_DATA_DIR` in the hosting environment if the deployment supports a protected data mount. Do not put secrets or private data in source code, Git history, public app logs, or public Streamlit secrets.

## Interpretation and limitations

- Composite indices are aggregate/associational measures, not causal estimates.
- The policy simulator uses illustrative multiplicative elasticities, not fitted causal coefficients.
- Enterprise and resident records are associated only after independent aggregation to the nearest audited location zone; this is not respondent-to-respondent matching.
- Workers and tourists remain Mall-Road-wide where equivalent coordinates are unavailable.
- Synthetic fallback values are demonstrations, not observed fieldwork findings. Always inspect Data Diagnostics and verify that the intended datasets report `REAL` before interpreting outputs.

## Tech stack

Python · Streamlit · pandas · NumPy · Plotly · SciPy · scikit-learn · openpyxl

## Project context

Urban Immersion fieldwork · BS Analytics & Sustainability Studies · Tata Institute of Social Sciences (TISS), 2024–28.

---

*The dashboard is the primary portfolio artifact; this README provides context, setup instructions, methodology and responsible-use notes.*