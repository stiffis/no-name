# Harmonization methods: audit, corrections and final formulas

Scope: Peru, daytime detections, 2003–2025.
Everything below is reproduced by `make all` (pipeline) and `make audit` (research). The audit numbers are in
`docs/audit.txt` and `docs/floor.txt`; the model numbers in `data/derived/model.json` and `web/data/method.json`.

## 1. What is being merged

Three NASA FIRMS active-fire records that measure the same thing with different instruments:

| Record | Sensor | Pixel | Years used | Role |
|---|---|---|---|---|
| Aqua | MODIS | 1 km (up to 2 × 4.8 km at the swath edge) | 2003–2011 | converted |
| Suomi NPP | VIIRS | 375 m (up to 0.8 km) | 2012–2025 | common scale |
| NOAA-20 | VIIRS | 375 m | 2018–2025 | fills Suomi NPP outages |

All three cross the equator at 13:30. Terra (10:30) is not used: it samples a different part of the daily fire cycle.

## 2. What the audit found

### 2.1 Service outages during the burning season (corrected)

The files do not flag days when a satellite was not observing. Three cases distorted the method:

| Satellite | Period | Cause | Effect measured in our data |
|---|---|---|---|
| Aqua | 16 Aug – 2 Sep 2020 | formatter (FMU/SSR) anomaly | the VIIRS/Aqua ratio for that fortnight is 26, against 3.2–4.3 in every other year |
| Aqua | 31 Mar – 16 Apr 2022 | spacecraft safe mode | 0 Aqua cell-days against 199 for Suomi NPP |
| Suomi NPP | 26 Jul – 10 Aug 2022 | spacecraft safe mode | 15 days without a single row; NOAA-20 has 204 rows per day |

Suomi NPP also has 31 other isolated missing days between 2020 and 2025, mostly in 2024.

The 2020 Aqua outage leaves no empty days, because NASA reprocessed that period with partial coverage. It only shows
up when compared with another sensor.

**Correction applied:**
- *Suomi NPP*: a day is an outage if Suomi NPP has no cell-day anywhere in Peru while NOAA-20 has at least 30.
  Those 46 days are filled with NOAA-20 cell-days times 0.964 (the 2019–2021 Suomi NPP / NOAA-20 ratio). The affected
  months are flagged `snpp_filled`.
- *Aqua*: the four affected months (2020-08, 2020-09, 2022-03, 2022-04) are excluded from calibration,
  cross-validation, band estimation and testing. They do not affect the final series, which only uses Aqua up to
  January 2012.
- No Aqua outage was found during the season between 2003 and 2011 (checked against Terra).

### 2.2 Aqua's orbital drift (confirmed; the design already avoided it)

Mean local solar time of Aqua's daytime detections: 13:34 between 2002 and 2021; 13:40 in 2022; 13:52 in 2023;
14:17 in 2024; 14:50 in 2025. Suomi NPP and NOAA-20 stay at 13:30 every year. This matches NASA's statement that Aqua
stopped maintaining its orbit in 2021.

Consequence: **Aqua data from 2023 onwards must not be used for calibration**. Our calibration (2013–2017) and test
(2018–2022) are before the strong drift. On the 2023–2025 contrast the model underestimates by 4 %, which is the
expected sign of a change in the input sensor.

### 2.3 The difference between sensors is not a size threshold (changes the interpretation)

Cell by cell, on the same day, 2013–2017:

- Only **55 %** of Aqua cell-days also appear in Suomi NPP (76 % counting neighbouring cells).
- The probability that Aqua records a cell-day that Suomi NPP recorded grows with fire power but **saturates near
  50 %**: 4 % at 2–5 MW, 22 % at 20–50 MW, 44 % at 100–200 MW, 54 % above 500 MW.

If the only difference were that MODIS misses small fires, that probability would reach 100 % for large fires. It
does not. The two satellites pass up to an hour apart and see each place from different angles: much of the
disagreement is **sampling**, not sensitivity.

Consequences:
- The harmonization is **only valid for aggregates** (department and month, or larger). It cannot say which
  particular cell burned in 2005.
- The alternative method of "keeping only VIIRS fires above a power threshold" performs worse. With the best
  threshold (20 MW) the national error is 17 % and the department error 26 %, against 9.3 % and 20.5 % for the
  statistical model. Rejected.

### 2.4 The log-linear model fails on zeros (corrected earlier, documented)

The power law fitted on logarithms, which works at national scale, overestimates by 40 % to 141 % at department
scale: half of the months have zero or very few detections and the retransformation correction inflates. It was
replaced by a Poisson regression, which models the expected value directly and handles zeros.

### 2.5 Each department has its own level (improvement added)

With a single curve per natural region, some departments were systematically high or low. A factor was added for
each department × region piece, shrunk towards 1 so that pieces with little data do not blow up. Cross-validation
selected it, and the department error drops from 25.5 % to 20.5 %.

### 2.6 MODIS version labels (unresolved)

The `version` field of the MODIS files reads `6.2` from 2000 to 2017, `6.03` from 2018 to 2022 and `61.03` from 2023.
The FIRMS documentation explains the general format (collection and processing stream) but **I did not find what
these three specific values mean**. As a precaution, calibration uses 2013–2017, which carries the same label as the
years being converted (2003–2011). The 2018–2022 test crosses into the `6.03` label and the error does not get
worse, which suggests the change is minor, but does not prove it.

### 2.7 In-period bands were too narrow (corrected)

The first uncertainty bands came from cross-validation errors inside 2013–2017. On the 2018–2022 test they covered
the observed season total in only 61 % of departments, against the nominal 80 %: errors are smaller inside the
fitting period than outside it, and the bands are applied outside it (2003–2011). Replaced by block-wise conformal
bands (section 3.5).

## 3. The final method

### 3.1 Unit

For every 0.05° × 0.05° cell (indices `i = ⌊(lat + 90)·20⌋`, `j = ⌊(lon + 180)·20⌋`) and every local day (UTC−5):

```
I(sensor, cell, day) = 1 if there is at least one accepted detection; 0 otherwise
```

Accepted detection: daytime overpass, `type = 0`, no repeated identical rows; Aqua with confidence ≥ 30; VIIRS with
nominal or high confidence.

The activity of a piece `t` (department × natural region) in a month is the sum of `I` over its cells and days:
`A` for Aqua, `V` for VIIRS. The unit is the cell-day.

### 3.2 Suomi NPP gap filling

```
V(t, month) = S(t, non-outage days) + ρ · N(t, outage days),      ρ = 0.9641
```

`S` and `N` are the Suomi NPP and NOAA-20 cell-days. `ρ` is the ratio of national sums for 2019–2021.

### 3.3 Converting Aqua to the VIIRS scale

```
E[V] = f_t · exp( a_r + b_r · ln(1 + A) )
```

with `r` the natural region of the piece. `a_r`, `b_r` are estimated by Poisson maximum likelihood (Newton–Raphson)
on the months of 2013–2017:

| Region | a | b |
|---|---|---|
| Coast | 1.497 | 1.115 |
| Andean highlands | 1.588 | 0.982 |
| Amazon rainforest | 2.057 | 0.878 |

The factor of each piece is

```
f_t = ( V_t + k ) / ( P_t + k ),      k = 50
```

where `V_t` is the piece's observed sum in 2013–2017 and `P_t` the sum predicted by the regional curve. With
`k = 50`, a piece with thousands of cell-days uses its own level and one with few stays close to 1. There are 47
pieces; the median `f_t` is 0.94 and the range 0.16 to 1.58.

The value of a department, a region or the country is the **sum** of its converted pieces, so every level adds up.

### 3.4 The series

```
2003-01 to 2012-01:  value = converted Aqua (3.3), with a band
2012-02 to 2025-12:  value = VIIRS (3.2)
```

Suomi NPP starts on 20 January 2012, so January 2012 still uses Aqua. Besides months, the series is published for the
**burning season** (July–October) and for the **full year**.

### 3.5 Uncertainty: block-wise conformal bands

The model is fitted on 2013–2017. Its predictions for **2018–2020**, years it never saw (just as it never saw
2003–2011), give the observed/predicted ratios whose 10th and 90th percentiles define the band:
`[P10 · prediction, P90 · prediction]`. Monthly bands are grouped by area level and prediction size; season and year
bands are measured on the totals themselves (pooling levels, by size) rather than by adding monthly bands, which
would overstate them.

Coverage is checked on **2021–2022**, which is used for nothing else (target ≈ 80 %):

| | Monthly | Season | Year |
|---|---|---|---|
| Department | 81.1 % | 78.8 % | 69.2 % |
| Region | 75.8 % | 100 % | 83.3 % |
| Country | 90.9 % | 100 % | 100 % |

The annual department figure is low, but with 52 cases (26 departments × 2 years) its uncertainty is about ±6 points.
Region and country figures rest on very few cases (6 and 2 in total).

### 3.6 Normal and anomaly

For every area and every month of the year (and for the season and the year), over 2003–2024: median, 10th and 90th
percentile. The anomaly is `100 · (value / median − 1)`.

Months with fewer than 20 cell-days are flagged `low_activity`: their relative error is 67 %, although they carry
only 6 % of the total error. The web should show them dimmed.

## 4. Validation

Design: calibration 2013–2017; model selection by leave-one-year-out cross-validation on the department-month error;
test on 2018–2022, which plays no part in anything above. Error: WAPE = 100 · Σ|pred − obs| / Σ obs.

| Model | Cross-validation (dep.) | Test: dep. | Test: country | Bias of the total |
|---|---|---|---|---|
| Single ratio | 30.7 | 34.5 | 23.9 | +3.7 % |
| Poisson by region | 25.9 | 25.5 | 9.6 | +1.8 % |
| **Poisson by region + piece factor (chosen)** | **20.5** | **20.5** | **9.3** | **+1.6 %** |
| Log-linear by region | 79.7 | 84.2 | 74.5 | +73.0 % |

Without excluding the Aqua outage months, the chosen model's national error would be 12.1 %: almost a third of the
apparent error came from the data, not from the model. All 13 candidates are in `data/derived/model.json`.

## 5. How low can the error go

Two identical instruments (Suomi NPP predicted from NOAA-20, 2019–2021) already disagree. That is the floor no
MODIS → VIIRS method can beat. Test error of the chosen model at each aggregation level (`docs/floor.txt`):

| Level | Floor (VIIRS vs VIIRS) | Chosen model (MODIS → VIIRS) |
|---|---|---|
| Department, month | 10.5 % | 20.5 % |
| Country, month | 6.0 % | 9.3 % |
| Department, season | 3.8 % | 10.6 % |
| Department, year | 3.1 % | 9.1 % |
| Country, year | 0.9 % | 5.2 % |

Adding Terra, Aqua's fire radiative power or its detection count as extra predictors improved the department-month
error by 1.3 points at best (tested ad hoc, not part of the pipeline), so they were not adopted. The biggest gain is
free: **report seasons and years**, where the error is half the monthly one. The largest remaining source of error is
clouds and coverage, which the FIRMS point files do not describe.

## 6. Assumptions and limits

1. **Stability.** The 2013–2017 relationship between Aqua and VIIRS is assumed to hold in 2003–2011. It cannot be
   checked: VIIRS did not exist. In favour: the August–September ratio stays between 3.3 and 4.4 across all thirteen
   years of overlap.
2. **Aggregates only.** Cell-level agreement is 55 %; the series cannot locate past fires.
3. **No cloud or coverage correction.** A very cloudy month shows little activity.
4. **13:30 only.** Burns at other times of day are not seen.
5. **Approximate natural regions** from elevation, not the official map.
6. **Department-month error of 20 %.** Low-activity months have very wide bands.
7. **MODIS version labels unexplained** (section 2.6).
8. **Annual department band coverage of 69 %**, below the 80 % target (section 3.5).
9. **2025 with care.** Suomi NPP has filled days and it was a very low-activity year with no identified cause.

## 7. Context in the literature

- I found no peer-reviewed method that harmonizes MODIS–VIIRS **detection counts** on a grid; published work focuses
  on fire radiative power and burned area.
- Li et al. (2018) compare fire radiative power from both sensors and describe MODIS duplicates at large view angles.
  A 2026 *Remote Sensing* paper proposes correcting each sensor before fusing them, rather than pooling detections.
- Vadrevu and Lasko (2018) find 4.8 times more VIIRS than MODIS detections in an agricultural region of India. In
  Peru we measure 4.6 in cell-days: the same order.
- Boschetti, Roy and Giglio are building a harmonized **burned-area** series on 0.25° cells, calibrated statistically
  by region. The same principle at a different scale.

## 8. Sources

- 2020 Aqua outage: https://ladsweb.modaps.eosdis.nasa.gov/alerts-and-issues/171856
- 2022 Aqua safe mode: https://mcst.gsfc.nasa.gov/news
- 2022 Suomi NPP safe mode: https://www.earthdata.nasa.gov/data/alerts-outages/suomi-npp-recovers-from-safe-mode
- Terra and Aqua orbital drift: https://modis-land.gsfc.nasa.gov/news.html
- FIRMS attribute fields: https://earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs
- Li et al. (2018): https://repository.library.noaa.gov/view/noaa/49896/noaa_49896_DS1.pdf
- Vadrevu and Lasko (2018): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6108185/
- FRP correction and fusion (2026): https://doi.org/10.3390/rs18101650
- Boschetti, Roy and Giglio, MODIS–VIIRS continuity: https://modis.gsfc.nasa.gov/sci_team/meetings/202204/presentations/session1/boschetti.pdf
