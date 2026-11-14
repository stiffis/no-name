"""Step 1: from FIRMS CSV files to monthly cell-days on a 0.05-degree grid.

Filters (same as the study book): daytime overpass, type=0, no repeated identical rows,
MODIS Aqua only with confidence >= 30, VIIRS with nominal or high confidence.
Local date UTC-5. Cell: integer indices from (-90, -180) in 0.05-degree steps.

Service outages:
  Suomi NPP: a local day is an outage if SNPP has no cell-day anywhere in the country while
  NOAA-20 has at least 30. Those days are filled with NOAA-20 cell-days times the 2019-2021
  SNPP/NOAA-20 ratio. The result is the "VIIRS" sensor (Suomi NPP, gap-filled).
  Aqua: outages documented by NASA (they leave no empty days because the period was reprocessed
  with partial coverage); their months are excluded from calibration and testing in model.py.

Outputs in data/derived/:
  cell_months.csv   sensor, i, j, year, month, days   (days with at least one detection)
  outages.json      filled Suomi NPP days, ratio used, and excluded Aqua months
  cells.csv         i, j, department, region          (for every cell that appears)
  provenance.json   SHA-256 fingerprints and row counts of every raw file
"""

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
SOURCES = [
    ("modis", "Aqua", range(2002, 2026)),
    ("viirs-snpp", "SNPP", range(2012, 2026)),
    ("viirs-jpss1", "NOAA20", range(2018, 2026)),
]
ZOOM, TILES_X, TILES_Y = 6, range(17, 20), range(31, 36)
HIGHLANDS_THRESHOLD_M = 2000
AQUA_OUTAGES = [
    {
        "from": "2020-08-16",
        "to": "2020-09-02",
        "cause": "formatter-multiplexer unit (FMU/SSR) anomaly",
        "source": "https://ladsweb.modaps.eosdis.nasa.gov/alerts-and-issues/171856",
    },
    {
        "from": "2022-03-31",
        "to": "2022-04-16",
        "cause": "spacecraft safe mode",
        "source": "https://mcst.gsfc.nasa.gov/news",
    },
]
REFERENCE_MINIMUM = 30
NOAA20_RATIO_YEARS = (2019, 2020, 2021)


def cell_index(value, origin):
    return int(((Decimal(value) + origin) * 20).to_integral_value(rounding=ROUND_FLOOR))


def accept(source, row):
    if row["daynight"] != "D" or row["type"] != "0":
        return False
    if source == "modis":
        return row["satellite"] in ("Aqua", "A") and float(row["confidence"]) >= 30
    return row["confidence"].lower() in ("n", "h")


def read_raw():
    days = defaultdict(set)
    provenance = []
    for source, sensor, years in SOURCES:
        for year in years:
            name = f"{source}_{year}_Peru.csv"
            path = RAW / name
            read = accepted = repeated = 0
            versions, seen = Counter(), set()
            with path.open(newline="") as f:
                for row in csv.DictReader(f):
                    read += 1
                    versions[row["version"]] += 1
                    assert "NRT" not in row["version"].upper(), name
                    if not accept(source, row):
                        continue
                    key = tuple(row.values())
                    if key in seen:
                        repeated += 1
                        continue
                    seen.add(key)
                    local = datetime.strptime(row["acq_date"] + row["acq_time"].zfill(4), "%Y-%m-%d%H%M") - timedelta(
                        hours=5
                    )
                    i, j = cell_index(row["latitude"], 90), cell_index(row["longitude"], 180)
                    days[sensor, i, j, local.year, local.month].add(local.day)
                    accepted += 1
            provenance.append(
                {
                    "file": name,
                    "sensor": sensor,
                    "url": f"https://firms.modaps.eosdis.nasa.gov/data/country/{source}/{year}/{name}",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                    "downloaded_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                    "raw_rows": read,
                    "accepted_rows": accepted,
                    "repeated_rows_dropped": repeated,
                    "versions": dict(versions),
                }
            )
    return days, provenance


def fill_snpp(days):
    per_day = defaultdict(lambda: defaultdict(int))
    for (sensor, _, _, y, month), ds in days.items():
        for d in ds:
            per_day[sensor][date(y, month, d)] += 1
    outages = sorted(
        d for d, n in per_day["NOAA20"].items() if n >= REFERENCE_MINIMUM and per_day["SNPP"].get(d, 0) == 0
    )
    ratio = sum(n for d, n in per_day["SNPP"].items() if d.year in NOAA20_RATIO_YEARS) / sum(
        n for d, n in per_day["NOAA20"].items() if d.year in NOAA20_RATIO_YEARS
    )
    outage_month = defaultdict(set)
    for d in outages:
        outage_month[d.year, d.month].add(d.day)
    counts: dict[tuple[str, int, int, int, int], float] = {k: len(v) for k, v in days.items()}
    for (sensor, i, j, y, month), ds in days.items():
        if sensor == "SNPP":
            counts["VIIRS", i, j, y, month] = counts.get(("VIIRS", i, j, y, month), 0) + len(ds)
        elif sensor == "NOAA20" and (y, month) in outage_month:
            n = len(ds & outage_month[y, month])
            if n:
                counts["VIIRS", i, j, y, month] = counts.get(("VIIRS", i, j, y, month), 0) + ratio * n
    aqua_months = set()
    for outage in AQUA_OUTAGES:
        d = date.fromisoformat(outage["from"])
        while d <= date.fromisoformat(outage["to"]):
            aqua_months.add((d.year, d.month))
            d += timedelta(days=1)
    info: dict[str, Any] = {
        "snpp_filled_days": [d.isoformat() for d in outages],
        "snpp_filled_months": sorted(f"{y}-{m:02d}" for y, m in outage_month),
        "snpp_over_noaa20_ratio": ratio,
        "ratio_years": list(NOAA20_RATIO_YEARS),
        "aqua_outages": AQUA_OUTAGES,
        "aqua_excluded_months": sorted(f"{y}-{m:02d}" for y, m in aqua_months),
    }
    return counts, info


def load_elevation():
    mosaic = np.zeros((256 * len(TILES_Y), 256 * len(TILES_X)))
    for a, x in enumerate(TILES_X):
        for b, y in enumerate(TILES_Y):
            rgb = np.asarray(
                Image.open(ROOT / "data" / "elevation" / f"{ZOOM}_{x}_{y}.png").convert("RGB"), dtype=float
            )
            mosaic[256 * b : 256 * (b + 1), 256 * a : 256 * (a + 1)] = (
                rgb[:, :, 0] * 256 + rgb[:, :, 1] + rgb[:, :, 2] / 256 - 32768
            )
    return mosaic


def elevation(mosaic, lat, lon):
    n = 2**ZOOM
    px = (lon + 180) / 360 * n * 256 - TILES_X[0] * 256
    s = math.sin(math.radians(lat))
    py = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n * 256 - TILES_Y[0] * 256
    return mosaic[int(py), int(px)]


def region_classifier():
    mosaic = load_elevation()
    high = {}
    for i in range(int((-19 + 90) * 20), int((0.5 + 90) * 20)):
        row = [
            j
            for j in range(int((-82 + 180) * 20), int((-68 + 180) * 20))
            if elevation(mosaic, i / 20 - 90 + 0.025, j / 20 - 180 + 0.025) >= HIGHLANDS_THRESHOLD_M
        ]
        if row:
            high[i] = (min(row), max(row), set(row))
    rows = sorted(high)

    def region(i, j):
        k = i if i in high else min(rows, key=lambda r: abs(r - i))
        west, east, peaks = high[k]
        if i in high and j in peaks:
            return "highlands"
        if j < west:
            return "coast"
        if j > east:
            return "rainforest"
        return "highlands"

    return region


def rings(geometry):
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return [ring for polygon in polygons for ring in polygon]


def inside(x, y, rings_):
    result = False
    for ring in rings_:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                result = not result
    return result


def department_classifier():
    data = json.loads((ROOT / "data" / "boundaries" / "peru_adm1_simplified.geojson").read_text())
    departments = []
    for f in data["features"]:
        r = rings(f["geometry"])
        xs = [p[0] for a in r for p in a]
        ys = [p[1] for a in r for p in a]
        departments.append((f["properties"]["shapeISO"], min(xs), max(xs), min(ys), max(ys), r))

    def department(i, j):
        x, y = j / 20 - 180 + 0.025, i / 20 - 90 + 0.025
        for iso, x0, x1, y0, y1, r in departments:
            if x0 <= x <= x1 and y0 <= y <= y1 and inside(x, y, r):
                return iso
        nearest = min(departments, key=lambda d: min((p[0] - x) ** 2 + (p[1] - y) ** 2 for a in d[5] for p in a))
        return nearest[0]

    return department


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    days, provenance = read_raw()
    counts, outages = fill_snpp(days)
    region, department = region_classifier(), department_classifier()
    cells = sorted({(i, j) for _, i, j, _, _ in counts})
    attributes = {(i, j): (department(i, j), region(i, j)) for i, j in cells}

    with (DERIVED / "cell_months.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sensor", "i", "j", "year", "month", "days"])
        for key in sorted(counts):
            w.writerow([*key, round(counts[key], 3)])
    with (DERIVED / "cells.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["i", "j", "department", "region"])
        for (i, j), (d, r) in attributes.items():
            w.writerow([i, j, d, r])
    (DERIVED / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    (DERIVED / "outages.json").write_text(json.dumps(outages, ensure_ascii=False, indent=2) + "\n")

    total: defaultdict[str, float] = defaultdict(float)
    for (sensor, *_), v in counts.items():
        total[sensor] += v
    print("distinct cells:", len(cells), " cell-days per sensor:", {k: round(v) for k, v in total.items()})
    print(
        "Suomi NPP days filled:",
        len(outages["snpp_filled_days"]),
        outages["snpp_filled_months"],
        " SNPP/NOAA-20 ratio:",
        round(outages["snpp_over_noaa20_ratio"], 4),
    )
    print("cells per region:", Counter(r for _, r in attributes.values()))
    print("cells per department:", Counter(d for d, _ in attributes.values()).most_common(5), "...")


if __name__ == "__main__":
    main()
