"""Extracts from the raw CSV files what the method audit needs (a single pass).

Output: data/derived/audit.pkl with
  rows_per_day[platform][utc_date]          rows of any kind (to detect outages)
  solar_hour[platform][year]                local solar hours of accepted daytime detections
  cell_day[sensor][(i, j, local_date)]      (detections, summed FRP, minimum scan) of accepted daytime detections
"""

import csv
import pickle
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import cells as c

PLATFORM = {"Terra": "Terra", "T": "Terra", "Aqua": "Aqua", "A": "Aqua", "N": "SNPP", "N20": "NOAA20"}


def main():
    rows_per_day = defaultdict(lambda: defaultdict(int))
    solar_hour = defaultdict(lambda: defaultdict(list))
    cell_day = defaultdict(dict)
    for source, sensor, _ in c.SOURCES:
        for path in sorted(c.RAW.glob(f"{source}_*_Peru.csv")):
            with path.open(newline="") as f:
                for row in csv.DictReader(f):
                    platform = PLATFORM[row["satellite"]]
                    rows_per_day[platform][row["acq_date"]] += 1
                    if platform == "Terra" or not c.accept(source, row):
                        continue
                    utc = datetime.strptime(row["acq_date"] + row["acq_time"].zfill(4), "%Y-%m-%d%H%M")
                    local = utc - timedelta(hours=5)
                    solar = (utc.hour + utc.minute / 60 + float(row["longitude"]) / 15) % 24
                    solar_hour[platform][local.year].append(solar)
                    k = (c.cell_index(row["latitude"], 90), c.cell_index(row["longitude"], 180), local.date())
                    n, frp, scan = cell_day[sensor].get(k, (0, 0.0, 99.0))
                    cell_day[sensor][k] = (n + 1, frp + float(row["frp"] or 0), min(scan, float(row["scan"])))
    output = {
        "rows_per_day": {p: dict(d) for p, d in rows_per_day.items()},
        "solar_hour": {p: dict(d) for p, d in solar_hour.items()},
        "cell_day": dict(cell_day),
    }
    with (c.DERIVED / "audit.pkl").open("wb") as f:
        pickle.dump(output, f)
    print({s: len(d) for s, d in cell_day.items()})


if __name__ == "__main__":
    main()
