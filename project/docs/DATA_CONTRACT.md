# Data contract for the web app

The pipeline writes four files to `web/data/`. The web app only reads them. If a field needs to change, change it in
`pipeline/export.py`, run `make export verify`, and tell the team.

Serve the folder over HTTP (browsers block `fetch` on `file://`):

```sh
make serve        # http://localhost:8000
```

## `areas.json`

The 30 selectable areas, in display order.

```json
[{"id": "PE", "name": "Peru", "level": "country"},
 {"id": "R-coast", "name": "Coast", "level": "region"},
 {"id": "PE-JUN", "name": "Junín", "level": "department"}]
```

| Field | Values |
|---|---|
| `id` | `PE`; `R-coast`, `R-highlands`, `R-rainforest`; or the department's ISO 3166-2 code (`PE-JUN`, `PE-LMA*`, …) |
| `name` | display name |
| `level` | `country`, `region` or `department` |

## `departments.geojson`

The 26 department polygons (geoBoundaries, public domain). `properties.shapeISO` equals the `id` in `areas.json`.
Regions have no polygon: they are sets of 0.05° cells classified by elevation.

## `series.json`

An object keyed by area `id`. Every area has the same structure.

```json
{
  "PE-JUN": {
    "has_data": true,
    "months":  [ {month row}, … 276 rows, 2003-01 to 2025-12 ],
    "normal":  [ {"month": 1, "median": 12.0, "p10": 4.1, "p90": 30.2}, … 12 rows ],
    "season":  {"years": [ {period row}, … ], "normal": {"median": …, "p10": …, "p90": …}},
    "annual":  {"years": [ {period row}, … ], "normal": {"median": …, "p10": …, "p90": …}}
  }
}
```

### Month row

| Field | Meaning |
|---|---|
| `year`, `month` | calendar month (local time, UTC−5) |
| `value` | **the number to plot**: harmonized activity in Suomi NPP cell-days |
| `low`, `high` | P10–P90 band. Equal to `value` for observed months |
| `source` | `aqua_converted` (2003-01 to 2012-01), `snpp`, or `snpp_filled` (some days filled from NOAA-20) |
| `low_activity` | `true` if `value` < 20: show dimmed, the relative error is large |
| `aqua` | raw Aqua cell-days (not converted), for the "how it works" view |
| `aqua_converted` | Aqua converted with the model, every month: compare with `snpp` to show the overlap |
| `aqua_reliable` | `false` for Aqua outage months and from 2022 on (orbital drift) |
| `snpp` | Suomi NPP cell-days with outages filled; `null` before 2012 |
| `noaa20` | raw NOAA-20 cell-days; `null` before 2018 |

### Period row (`season` = July–October, `annual` = January–December)

| Field | Meaning |
|---|---|
| `year` | year |
| `value` | total of the period's months |
| `low`, `high` | P10–P90 band for the total |
| `source` | `aqua_converted`, `snpp` or `mixed` (only 2012: January converted, the rest observed) |
| `anomaly_pct` | `100 · (value / normal.median − 1)`; `null` if the median is 0 |

`normal` (both monthly and per period) uses 2003–2024.

## `method.json`

Everything a "How it works" page needs: scale, segments, outages, model and parameters, comparison of the 13
candidate models, band method and coverage, filters, sources. Display text can quote it directly.

## Function shared by the map and the charts

```js
// The map (and the area dropdown) call it; the charts implement it.
function showArea(id) { /* draw the season bars, the calendar and the "this year vs normal" chart for this area */ }
```

## Suggested views

1. **Main**: `season.years` as bars with the `low`–`high` band, a vertical line at 2012 (sensor change).
2. **Calendar**: `months` as a year × month heatmap; `aqua_converted` months hatched or outlined, `low_activity`
   dimmed.
3. **This year vs normal**: `normal` as median line and P10–P90 band, the chosen year on top.
