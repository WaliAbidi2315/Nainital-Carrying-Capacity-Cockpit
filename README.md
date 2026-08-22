# Nainital Carrying Capacity Cockpit

A Streamlit decision-support dashboard for sustainable mountain tourism governance in Nainital/Mall Road, built from Urban Immersion fieldwork.

## What is included

- Site Infrastructure Readiness & Physical Carrying Capacity Proxy
- Water & Energy Stress Cockpit
- Resident Friction & Livelihood Vulnerability
- Policy Scenario Simulator
- Variable Dictionary & Data Diagnostics
- Nearest-neighbour zone aggregation for geotagged enterprise/resident records
- Explicit synthetic-data fallback for demonstration mode

The dashboard's own documentation states that its composite indices are aggregate/associational measures and that scenario projections are illustrative rather than causal.

## Project structure

```text
nainital-carrying-capacity-cockpit/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── .streamlit/
│   └── config.toml
└── data/
    └── <private KoboToolbox exports>
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export ALLOW_SYNTHETIC_FALLBACK=0
streamlit run app.py
```

On Windows PowerShell:

```powershell
$env:ALLOW_SYNTHETIC_FALLBACK="0"
streamlit run app.py
```

## Publishing safely

### Recommended: private data + private repository

Keep respondent-level XLSX files out of a public GitHub repository. The current repository is configured to ignore `data/*.xlsx`.

For a production deployment, point the app at a private data directory using:

```text
APP_DATA_DIR=/path/to/private/data
ALLOW_SYNTHETIC_FALLBACK=0
```

If the hosting platform cannot provide a private filesystem/data mount, use a private repository or replace the file loader with a protected data source.

### Public demo

For a public showcase, publish a version containing only synthetic/anonymized data. Do not expose raw survey exports, respondent identifiers, exact household/business coordinates, or other potentially identifying fields.

## Data assumptions

The app expects KoboToolbox "all versions" exports and resolves fields by question text rather than relying on fixed column positions. The dashboard uses five source datasets:

1. Location
2. Enterprise
3. Residents
4. Workers
5. Tourist

Enterprise and resident records are spatially joined to the nearest audited location zone when coordinates are available. Workers and tourists remain Mall-Road-wide because they do not provide the same coordinate basis.

## Production checklist

- [ ] Confirm the deployed dataset is the intended, cleaned version.
- [ ] Keep raw respondent-level data private.
- [ ] Set `ALLOW_SYNTHETIC_FALLBACK=0`.
- [ ] Check the Data Diagnostics page after deployment.
- [ ] Verify all five datasets report `real`.
- [ ] Verify geotagging coverage before interpreting zone maps.
- [ ] Review the Variable Dictionary before presenting composite indices.
- [ ] Clearly label scenario outputs as illustrative, not causal.
- [ ] Add a project/contact page if this is being shared publicly.
