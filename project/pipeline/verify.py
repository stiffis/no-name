"""Checks that the web data are consistent with each other and with the pipeline.

Run after export.py. Exits with an error if anything does not add up.
"""

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
DERIVED = ROOT / "data" / "derived"
TOLERANCE = 0.6


def close(a, b):
    return abs(a - b) <= TOLERANCE + 1e-6 * abs(b)


def main():
    areas = json.loads((WEB / "areas.json").read_text())
    series = json.loads((WEB / "series.json").read_text())
    method = json.loads((WEB / "method.json").read_text())
    geo = json.loads((WEB / "departments.geojson").read_text())
    model = json.loads((DERIVED / "model.json").read_text())
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    ids = [a["id"] for a in areas]
    departments = [a["id"] for a in areas if a["level"] == "department"]
    regions = [a["id"] for a in areas if a["level"] == "region"]
    check(len(ids) == len(set(ids)) == 30, f"expected 30 unique areas, found {len(set(ids))}")
    check(set(ids) == set(series), "areas.json and series.json do not list the same areas")
    check(
        {f["properties"]["shapeISO"] for f in geo["features"]} == set(departments),
        "geojson departments do not match areas.json",
    )

    expected = [(y, m) for y in range(2003, 2026) for m in range(1, 13)]
    for area, s in series.items():
        months = s["months"]
        check([(r["year"], r["month"]) for r in months] == expected, f"{area}: months missing or out of order")
        for r in months:
            label = f"{area} {r['year']}-{r['month']:02d}"
            check(
                all(
                    v is None or (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0)
                    for v in (r["value"], r["low"], r["high"], r["aqua"], r["snpp"], r["noaa20"])
                ),
                f"{label}: negative or non-finite value",
            )
            check(r["low"] <= r["high"], f"{label}: inverted band")
            if (r["year"], r["month"]) < (2012, 2):
                check(r["source"] == "aqua_converted", f'{label}: unexpected source {r["source"]}')
            else:
                check(r["source"] in ("snpp", "snpp_filled"), f'{label}: unexpected source {r["source"]}')
                check(
                    close(r["low"], r["value"]) and close(r["high"], r["value"]),
                    f"{label}: an observed month must not have a band",
                )
            check(r["low_activity"] == (r["value"] < 20), f"{label}: wrong low-activity flag")
        for period, period_months in (("season", (7, 8, 9, 10)), ("annual", range(1, 13))):
            for r in s[period]["years"]:
                total = sum(x["value"] for x in months if x["year"] == r["year"] and x["month"] in period_months)
                check(
                    abs(total - r["value"]) <= 0.1 * len(period_months),
                    f"{area} {period} {r['year']}: not the sum of its months",
                )
                check(r["low"] <= r["high"], f"{area} {period} {r['year']}: inverted band")
            n = s[period]["normal"]
            check(n["p10"] <= n["median"] <= n["p90"], f"{area} {period}: normal out of order")
        for n in s["normal"]:
            check(n["p10"] <= n["median"] <= n["p90"], f"{area} month {n['month']}: normal out of order")

    for i, (y, month) in enumerate(expected):
        country = series["PE"]["months"][i]
        for field in ("value", "aqua", "snpp"):
            if country[field] is None:
                continue
            dep_sum = sum(series[d]["months"][i][field] for d in departments)
            reg_sum = sum(series[r]["months"][i][field] for r in regions)
            check(
                abs(dep_sum - country[field]) <= TOLERANCE * len(departments),
                f"{y}-{month:02d} {field}: departments do not add up to the country",
            )
            check(
                abs(reg_sum - country[field]) <= TOLERANCE * len(regions),
                f"{y}-{month:02d} {field}: regions do not add up to the country",
            )

    totals = {}
    with (DERIVED / "cell_months.csv").open() as f:
        for r in csv.DictReader(f):
            key = (r["sensor"], int(r["year"]))
            totals[key] = totals.get(key, 0) + float(r["days"])
    check(
        round(sum(totals[("Aqua", y)] for y in (2018, 2019, 2020))) == 26508,
        "Aqua 2018-2020 total no longer matches the study book (26508)",
    )
    check(
        round(sum(totals[("SNPP", y)] for y in (2018, 2019, 2020))) == 124188,
        "Suomi NPP 2018-2020 total no longer matches the study book (124188)",
    )
    annual_aqua = {y: sum(r["aqua"] for r in series["PE"]["months"] if r["year"] == y) for y in range(2003, 2026)}
    for y, total in annual_aqua.items():
        check(abs(total - totals[("Aqua", y)]) <= 1, f"Aqua {y}: web data do not match cell_months.csv")

    check(method["chosen_model"] == model["chosen"], "method.json and model.json name different models")
    check(
        model["chosen"] == min(model["candidates"], key=lambda n: model["candidates"][n]["cv_wape_department"]),
        "the chosen model is not the one with the lowest cross-validation error",
    )

    if errors:
        print(f"{len(errors)} problems:")
        for e in errors[:30]:
            print(" -", e)
        raise SystemExit(1)
    print(
        "OK: 30 areas, 276 months each, country = departments = regions, seasons and years = sum of",
        "their months, valid bands, totals consistent with cell_months.csv and with the study book.",
    )


if __name__ == "__main__":
    main()
