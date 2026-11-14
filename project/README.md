# Harmonized burning calendar for Peru (MODIS + VIIRS)

Project for the _Harmonization of MODIS and VIIRS Hot Spots_ challenge of the NASA Space Apps Challenge 2026.

It merges the active-fire records of MODIS/Aqua (since 2002) and VIIRS/Suomi NPP (since 2012) into a single scale,
from 2003 to 2025, for Peru, its three natural regions and its 26 departments, by month, burning season and year.

## What it does

1. **`pipeline/cells.py`**: reads the NASA FIRMS yearly CSV files and counts, per 0.05° cell and month, the days with
   at least one detection (cell-days). Fills Suomi NPP outage days from NOAA-20 and assigns every cell to its
   department and natural region.
2. **`pipeline/model.py`**: chooses the Aqua → VIIRS conversion among 13 candidates.
3. **`pipeline/export.py`**: builds the harmonized series of every area (monthly, season and year), their
   uncertainty bands and their "normal" reference, and writes the JSON files in `web/data/`.
4. **`pipeline/verify.py`**: checks that the web data are consistent (sums, months, bands, totals).
5. **`pipeline/diagnostics.py`**: draws `docs/continuity_2012.png`, the check of the 2012 splice.
6. **`research/`**: the method audit (`extract.py`, `audit.py`) and the error-floor analysis (`floor.py`), which write
   `docs/audit.txt` and `docs/floor.txt`.

```sh
make all         # download what is missing and recompute everything (~1 minute plus the download)
make audit       # reproduce the audit and the error floor (~1 minute)
make serve       # serve web/ on http://localhost:8000
```

Requires Python 3 with NumPy, Pillow and Matplotlib, plus `curl`.

- **[`docs/METHODS.md`](docs/METHODS.md)**: formulas, parameters, audit findings, validation and limits.
- **[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)**: the format of the JSON files the web app reads.

## Decisions

| Decision | Value | Why |
|---|---|---|
| Unit | daytime cell-days, 0.05° cell, local date UTC−5 | removes duplicates across pixels and satellites |
| Sensors | Aqua and Suomi NPP | same overpass time (13:30) |
| Filters | `type=0`; Aqua confidence ≥ 30; VIIRS nominal or high | excludes static sources and weak detections |
| Common scale | Suomi NPP | the record that continues (NOAA-20 extends it) |
| Calibration | 2013–2017 | same MODIS label (`6.2`) as 2003–2011, and before Aqua's orbital drift |
| Selection | leave-one-year-out cross-validation, department-month error | the scale the web uses |
| Test | 2018–2022, not used to choose or fit | |
| Fitting unit | department × natural region | every level is a sum, so all levels agree |
| Uncertainty | block-wise conformal bands (2018–2020), coverage checked on 2021–2022 | calibrated outside the fitting period, like 2003–2011 |

## Result

Model chosen by cross-validation: **Poisson regression by region with a factor per department**,
E[V] = f·exp(a + b·ln(1 + A)).

| Test 2018–2022 | Single ratio | Chosen model |
|---|---|---|
| Department-month error (WAPE) | 34.5 % | **20.5 %** |
| Country-month error (WAPE) | 23.9 % | **9.3 %** |
| Department-season error (WAPE) | | **10.6 %** |
| Bias of the total | +3.7 % | **+1.6 %** |

Three corrections that came out of auditing the data:

- **Service outages.** Aqua had no data from 16 August to 2 September 2020 and from 31 March to 16 April 2022; those
  months are excluded from fitting and testing. Suomi NPP has 46 missing days between 2020 and 2025 (15 in a row in
  July–August 2022), filled from NOAA-20.
- **Aqua's drift.** Its overpass time moves from 13:34 to 14:50 between 2021 and 2025; that is why no year after
  2017 is used for calibration.
- **Aggregates only.** Cell by cell, Aqua and VIIRS agree on the same day only 55 % of the time. The series is valid
  per department and month or larger, not for locating fires.

## Limits

- It measures **activity detected at 13:30 on clear days**, not burned area or number of fires.
- No cloud or coverage correction.
- The natural regions are approximated from elevation, not the official map.
- 2003 to January 2012 are estimates, with their band; the department-month error is about 20 %.
- 2000–2002 are left out: only Terra exists, and it passes at a different time.

## Sources

- NASA FIRMS yearly country files: MODIS Collection 6.x and VIIRS 375 m Collection 2.
  SHA-256 fingerprints in `data/derived/provenance.json`.
- geoBoundaries, gbOpen PER ADM1 (public domain).
- Terrarium elevation tiles (AWS Open Data).
- Giglio et al. (2016) and Schroeder et al. (2014), detection algorithms.
