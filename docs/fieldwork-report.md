# Nainital Fieldwork Dashboard — AI Report

**Live dashboard:** https://nainital-fw-dashboard.streamlit.app/

This report summarises the dashboard findings and illustrative policy scenarios from the uploaded *Dashboard Group 7 Fieldwork Assignment*.

## Objective

The scenario simulation suggests that the Mall Road belt has limited remaining capacity to absorb additional tourist pressure without worsening infrastructure stress.

Among 158 surveyed firms, 45 (28.5%) currently exceed the water-stress deficiency threshold. In the illustrative scenarios, this rises to 36.7% (58 firms) with a 30% tourist increase and 63.9% (101 firms) with a 60% increase.

Average emergency response time across audited zones is 30 minutes at baseline. Under illustrative tourist surges of 30%, 60% and 100%, the report projects response times of 39, 48 and 60 minutes respectively. These projections use illustrative elasticity assumptions, not causal or time-series models.

Sensitivity analysis identifies rainwater harvesting as the strongest of the three modelled WSCI levers: a potential reduction of up to 25.0 index points, compared with 9.1 points for additional municipal piped-water hours.

Across the ten audited zones, WSCI ranges from 35.7 to 65.5, against a corridor average of 45.5. Even the best modelled policy scenarios leave the highest-scoring zone above the corridor average, indicating that the variables represented in the simulator do not explain all local stress.

The baseline Resident Friction and Externality Index (RFEI) is 68.9, higher than baseline WSCI (45.5) and Informal Livelihood Vulnerability Index (ILVI, 39.1). The report therefore identifies socio-spatial friction experienced by residents as a particularly urgent concern.

## Dashboard indicators

The fieldwork indicators cover:

- **Location and infrastructure:** geolocation, Mall Road zones, ambulance response time, healthcare availability, parking, public toilets, dustbins, footpaths, potholes, waterlogging, public Wi-Fi and directional signboards.
- **Enterprises and resource use:** enterprise type, water storage capacity, operational water constraints, rainwater harvesting, solar/renewable energy, local ownership, peak/off-season electricity bills, sewage arrangements and seasonal/full-time/local employment.
- **Residents:** piped-water supply hours, perceived priority of tourism businesses over household water needs, peak-season prices and changes in visits to Mall Road/Naini Lake.
- **Workers:** work sector, seasonality, employment arrangement, months worked, income gaps, tourism dependence, insurance, government support and payment regularity.
- **Tourists:** visit satisfaction, approximate expenditure and main purpose of visit.

## Findings

### Site infrastructure readiness

Emergency response is identified as the sharpest infrastructure concern. Response times range from 10 to 60 minutes; Zones 7 and 8 have response times of one hour. The average across audited zones is 30 minutes. The infrastructure sub-score combines a normalised and inverted emergency-response measure with reported availability of healthcare facilities.

### Water and energy stress

The report identifies peak electricity load as the leading feature associated with water stress in its Random Forest analysis, followed by tank capacity and seasonal employee count. Zone 10 is an outlier, with WSCI around 65; the lowest four zones cluster around 36–39. The report finds little relationship between tank capacity and water-stress score, suggesting that storage alone may not address the underlying supply constraint.

Rainwater harvesting adoption is approximately 4% overall (4.2% among locally owned enterprises and 4.1% among non-local owners). The report also notes that 85% of enterprises are connected to municipal sewage, while 12% report having no sewage system. Restaurants/cafes have the highest median water-stress score among enterprise types, followed by hotels/resorts.

### Residents and informal livelihoods

The report states that 61% of residents believe tourism businesses receive water priority over local households. Median household piped-water supply is four hours per day. Around 49% of residents report avoiding Mall Road/Naini Lake during peak season.

Street vendors are identified as the most vulnerable worker group in the ILVI analysis, with gaps in insurance and welfare access as important contributors. Overall, 77% of surveyed workers report having no health insurance or accident coverage.

### Spatial variation and carrying-capacity pressure

Public toilets are reported in only three zones, with one in each. Zone 3 has the weakest overall readiness score (14/100), while the report notes a 38-point gap with Zone 4. Digital and communications infrastructure scores are low across all zones (0–50), while accessibility scores are comparatively stronger (30–82).

Carrying-capacity pressure is tightest in Zones 3 and 5 relative to accommodation density; Zone 10 has the most slack. The report identifies Mallital and upper Mall Road as priority areas for infrastructure investment based on the mapped concentration of poor readiness and high capacity pressure.

## Policy scenario simulation

The scenario analysis tests tourist surge, additional municipal piped-water hours and rainwater-harvesting adoption. Its outputs should be interpreted as illustrative scenario results rather than causal forecasts.

| Measure | Baseline / comparison | Scenario result |
|---|---:|---:|
| Firms above water-stress deficiency threshold | 28.5% (45 of 158) | 36.7% at +30% tourists; 63.9% at +60% |
| Average emergency response time | 30 minutes | 39 minutes at +30%; 48 at +60%; 60 at +100% |
| WSCI sensitivity to rainwater harvesting | — | Up to 25.0 index-point reduction |
| WSCI sensitivity to additional piped-water hours | — | 9.1 index-point reduction |
| Corridor average WSCI | 45.5 | Zone range: 35.7–65.5 |
| Baseline RFEI / WSCI / ILVI | 68.9 / 45.5 / 39.1 | RFEI is highest |

## Limitations

The dashboard is based on convenience sampling over a five-day fieldwork period. Findings may not represent the wider population of tourism businesses and tourism-linked workers in Nainital; they are preliminary insights, not a basis for major policy decisions or generalised conclusions.

Some raw variables contained inconsistent entries and missing values. The dashboard uses processed and cleaned data, and those processing choices may affect results. The report also explicitly notes that the emergency-response projections rely on illustrative elasticity rather than causal or time-series models.

## Contributions

The source document lists the following dashboard and documentation contributions:

| Contributor | Contribution |
|---|---|
| Aditi Sharma | Dashboard refinement; documentation report |
| Divy Gauba | Dashboard preparation |
| Prabudh Singh | Dashboard refinement |
| Wali Abidi | Dashboard preparation |

---

*Prepared as a readable Markdown companion to the uploaded Word report. The live Streamlit dashboard remains the interactive project artifact.*
