# NASA Space Apps Challenge 2026

Hackathon: 14–15 November 2026. Challenge: **Harmonization of MODIS and VIIRS Hot Spots**.
Official challenge resource: FIRMS (https://www.earthdata.nasa.gov/data/tools/firms).

## Layout

```
space-apps-2026/
├── project/                 the submission: data pipeline, method and web app
│   ├── pipeline/            download, cell-days, model choice, export, verification, diagnostics
│   ├── research/            method audit and error-floor analysis
│   ├── data/raw/            48 FIRMS CSV files for Peru: MODIS 2000–2025, Suomi NPP 2012–2025, NOAA-20 2018–2025
│   ├── data/derived/        cell-days, model, outages, provenance
│   ├── data/boundaries/     Peru departments (geoBoundaries)
│   ├── data/elevation/      elevation tiles used for coast, highlands and rainforest
│   ├── docs/                METHODS.md, DATA_CONTRACT.md, audit and floor reports, continuity figure
│   ├── web/                 static web app; its data are in web/data/
│   └── README.md            how to run it and the main results
├── libro-hotspots/          study book "Fuego desde el espacio" (in Spanish), with its own scripts and data
├── archive/                 material no longer in use; nothing was deleted
│   ├── lunar-navigator-challenge/   brief and study guide of the discarded lunar challenge
│   ├── backups/                     tar.gz of the book before the 9 November continuation
│   └── stray-venv-copy/             copy of a .venv that appeared as .venv~
└── .venv/                   Python environment with skyfield, scipy and rasterio (from the lunar challenge)
```

## Main results (Peru, daytime cell-days on a 0.05° grid)

Harmonized series 2003–2025 for Peru, 3 natural regions and 26 departments, by month, season and year.
Details in [`project/docs/METHODS.md`](project/docs/METHODS.md).

| Step | Model | Fit | Test | Test WAPE |
|---|---|---|---|---|
| Aqua → VIIRS | Poisson by region + department factor | 2013–2017 | 2018–2022 | 20.5 % department-month, 9.3 % country-month, 10.6 % department-season |
| NOAA-20 → Suomi NPP | ratio 0.964 (β = 1.00) | 2019–2021 | 2022–2024 | 6.5 % country-month |

Suomi NPP stopped delivering data on 2 November 2026; the series continues with NOAA-20.

## Commands

```sh
cd project && make all          # recompute the whole pipeline and verify it
cd project && make serve        # web app on http://localhost:8000
cd libro-hotspots && make pdf   # build the study book
```
