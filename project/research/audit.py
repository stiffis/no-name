"""Method audit: reproduces the checks reported in docs/METHODS.md.

Needs data/derived/audit.pkl (research/extract.py) and the pipeline outputs.
Writes docs/audit.txt.
"""

import bisect
import csv
import pickle
import statistics as st
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import model as m

FRP_LIMITS = [2, 5, 10, 20, 50, 100, 200, 500]


def main():
    data = pickle.loads((m.DERIVED / "audit.pkl").read_bytes())
    rows_per_day, solar_hour, cell_day = data["rows_per_day"], data["solar_hour"], data["cell_day"]
    attributes = {}
    with (m.DERIVED / "cells.csv").open() as f:
        for r in csv.DictReader(f):
            attributes[int(r["i"]), int(r["j"])] = (r["department"], r["region"])
    aqua, snpp = cell_day["Aqua"], cell_day["SNPP"]
    per_day = defaultdict(lambda: defaultdict(int))
    for sensor, d in cell_day.items():
        for _, _, day in d:
            per_day[sensor][day] += 1
    out = []

    out.append("1. Mean local solar time of accepted daytime detections, per year")
    for platform in ("Aqua", "SNPP", "NOAA20"):
        out.append(
            f"   {platform:7s} " + " ".join(f"{y}:{st.mean(v):.2f}" for y, v in sorted(solar_hour[platform].items()))
        )

    out.append("\n2. Runs of days without a single row in the file (>= 3 days), with the reference sensor mean")
    for platform, ref, since in (
        ("Aqua", "SNPP", "2012-01-20"),
        ("SNPP", "NOAA20", "2018-04-01"),
        ("NOAA20", "SNPP", "2018-04-01"),
    ):
        d, run = date.fromisoformat(since), []
        while d <= date(2025, 12, 31):
            if rows_per_day[platform].get(d.isoformat(), 0) == 0:
                run.append(d)
            else:
                if len(run) >= 3:
                    mean = st.mean(rows_per_day[ref].get(x.isoformat(), 0) for x in run)
                    out.append(f"   {platform:7s} {run[0]} to {run[-1]} ({len(run)} days); {ref}: {mean:.0f} rows/day")
                run = []
            d += timedelta(days=1)

    out.append("\n3. SNPP/Aqua cell-day ratio in three August-September windows")
    for y in range(2016, 2022):

        def total(sensor, a, b):
            d, t = date(y, *a), 0
            while d <= date(y, *b):
                t += per_day[sensor][d]
                d += timedelta(days=1)
            return t

        v = [
            (total("SNPP", a, b), total("Aqua", a, b))
            for a, b in (((8, 1), (8, 15)), ((8, 16), (9, 2)), ((9, 3), (9, 30)))
        ]
        out.append(
            f"   {y}: 1-15 Aug {v[0][0] / v[0][1]:.2f} | 16 Aug-2 Sep {v[1][0] / v[1][1]:.2f} | 3-30 Sep {v[2][0] / v[2][1]:.2f}"
        )
    april = [per_day["Aqua"][date(2022, 4, d)] for d in range(1, 17)]
    out.append(
        f'   Aqua, 1-16 April 2022: {sum(april)} cell-days; SNPP: {sum(per_day["SNPP"][date(2022, 4, d)] for d in range(1, 17))}'
    )

    out.append("\n4. Cell-by-cell agreement on the same local day, 2013-2017")
    in_range = lambda k: 2013 <= k[2].year <= 2017
    n_aqua = sum(1 for k in aqua if in_range(k))
    out.append(
        f"   Aqua cell-days that VIIRS also records: {100 * sum(1 for k in aqua if in_range(k) and k in snpp) / n_aqua:.0f} %"
    )
    neighbour = sum(
        1
        for k in aqua
        if in_range(k) and any((k[0] + a, k[1] + b, k[2]) in snpp for a in (-1, 0, 1) for b in (-1, 0, 1))
    )
    out.append(f"   ... also counting the eight neighbouring cells: {100 * neighbour / n_aqua:.0f} %")
    n, h = defaultdict(int), defaultdict(int)
    for k, (_, frp, _) in snpp.items():
        if in_range(k):
            b = bisect.bisect(FRP_LIMITS, frp)
            n[b] += 1
            h[b] += k in aqua
    out.append("   P(Aqua records the cell-day | total VIIRS FRP in MW):")
    out.append("   " + "  ".join(f">={([0] + FRP_LIMITS)[b]}: {100 * h[b] / n[b]:.0f} %" for b in sorted(n)))

    out.append(
        "\n5. Alternative: keep VIIRS cell-days with total FRP >= F0 and compare with Aqua (2018-2022, outage months removed)"
    )
    excluded = m.excluded_months() | {(2022, 7), (2022, 8)}
    for f0 in (0, 10, 15, 20, 25, 30):
        dep, country = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
        for sensor, pos, table in (("SNPP", 0, snpp), ("Aqua", 1, aqua)):
            for k, (_, frp, _) in table.items():
                y, month = k[2].year, k[2].month
                if 2018 <= y <= 2022 and (y, month) not in excluded and (sensor == "Aqua" or frp >= f0):
                    dep[attributes[k[0], k[1]][0], y, month][pos] += 1
                    country[y, month][pos] += 1
        a = sum(v[1] for v in country.values())
        out.append(
            f"   F0 = {f0:2d} MW: ratio {sum(v[0] for v in country.values()) / a:.2f}; department WAPE "
            f"{100 * sum(abs(v[0] - v[1]) for v in dep.values()) / a:.0f} %; country WAPE "
            f"{100 * sum(abs(v[0] - v[1]) for v in country.values()) / a:.0f} %"
        )

    (ROOT / "docs" / "audit.txt").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
