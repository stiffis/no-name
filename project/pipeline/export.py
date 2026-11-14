"""Step 3: harmonized series per area and the JSON files for the web app.

Common scale: daytime Suomi NPP cell-days.
  2003-01 to 2012-01: Aqua converted with the model chosen in model.py, with an uncertainty band.
  2012-02 to 2025-12: observed Suomi NPP (its data start on 20 January 2012); outage days are filled
                      from NOAA-20 (cells.py) and the month is flagged.
Areas: country, three approximate natural regions and 26 departments, all sums of pieces.
Aggregates: besides every month, the burning season (July to October) and the full year.
Bands (block-wise conformal calibration): the model is fitted on 2013-2017; the bands are the
10th and 90th percentiles of the observed/predicted ratio in 2018-2020, years the model never saw,
just as it never saw 2003-2011; their coverage is checked on 2021-2022, which is used for nothing
else. Monthly: by area level and prediction size. Season and year: by size, pooling levels,
measured on the totals themselves rather than by adding monthly bands.
A first scheme, using the cross-validation errors inside 2013-2017, gave season bands that were too
narrow (61 % coverage per department in 2018-2022): errors are smaller inside the fitting period
than outside it.
Reference "normal": 2003-2024, median and 10th and 90th percentiles.
Outputs in web/data/: areas.json, series.json, method.json, departments.geojson.
"""

import bisect
import json
import shutil
import statistics as st
from collections import defaultdict
from pathlib import Path

import model as m

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
START, END = (2003, 1), (2025, 12)
SNPP_START = (2012, 2)
REFERENCE = range(2003, 2025)
REGION_NAMES = {"coast": "Coast", "highlands": "Andean highlands", "rainforest": "Amazon rainforest"}
SIZE_LIMITS = [10, 50, 200, 1000]
AGGREGATE_SIZE_LIMITS = [100, 500, 2000, 8000]
SEASON = (7, 8, 9, 10)
BAND_YEARS = [2018, 2019, 2020]
COVERAGE_YEARS = [2021, 2022]
LOW_ACTIVITY = 20


def months():
    y, month = START
    while (y, month) <= END:
        yield y, month
        y, month = (y + 1, 1) if month == 12 else (y, month + 1)


def areas_of(dep, reg):
    return ["PE", f"R-{reg}", dep]


def percentile(values, p):
    s = sorted(values)
    h = (len(s) - 1) * p
    i = int(h)
    return s[i] + (h - i) * (s[min(i + 1, len(s) - 1)] - s[i])


def level(area):
    return "country" if area == "PE" else ("region" if area.startswith("R-") else "department")


def by_area(predict, data):
    pred, obs = defaultdict(float), defaultdict(float)
    for (dep, reg, y, month), (a, v) in data.items():
        p = predict(dep, reg, month, a)
        for area in areas_of(dep, reg):
            pred[area, y, month] += p
            obs[area, y, month] += v
    return pred, obs


def aggregate(pred, obs, period):
    p, o = defaultdict(float), defaultdict(float)
    for (area, y, month), v in pred.items():
        if period == "annual" or month in SEASON:
            p[area, y] += v
            o[area, y] += obs[area, y, month]
    return p, o


def quantile_table(pred, obs, key, minimum=20):
    groups = defaultdict(list)
    for k, p in pred.items():
        if p > 0:
            groups[key(k, p)].append(obs[k] / p)
    return {g: (percentile(c, 0.1), percentile(c, 0.9), len(c)) for g, c in groups.items() if len(c) >= minimum}


def monthly_key(k, p):
    return level(k[0]), bisect.bisect(SIZE_LIMITS, p)


def aggregate_key(_k, p):
    return "aggregate", bisect.bisect(AGGREGATE_SIZE_LIMITS, p)


def bands(predict, conformal_data):
    pred, obs = by_area(predict, conformal_data)
    tables = {"monthly": quantile_table(pred, obs, monthly_key)}
    for period in ("season", "annual"):
        tables[period] = quantile_table(*aggregate(pred, obs, period), aggregate_key)
    return tables


def band(tables, period, area, p):
    table = tables[period]
    key = monthly_key if period == "monthly" else aggregate_key
    group, size = key((area,), p)
    while (group, size) not in table and size > 0:
        size -= 1
    lo, hi, _ = table.get((group, size), (0.0, 3.0, 0))
    return round(p * lo, 1), round(p * hi, 1)


def coverage(tables, pred, obs):
    result = {}
    for period in ("monthly", "season", "annual"):
        p, o = (pred, obs) if period == "monthly" else aggregate(pred, obs, period)
        tally = defaultdict(lambda: [0, 0])
        for k, v in p.items():
            lo, hi = band(tables, period, k[0], v)
            tally[level(k[0])][0] += lo <= o[k] <= hi
            tally[level(k[0])][1] += 1
        result[period] = {lvl: round(100 * a / b, 1) for lvl, (a, b) in tally.items()}
    return result


def period_summary(rows, tables, period, area):
    per_year = defaultdict(lambda: {"value": 0.0, "converted": 0.0, "observed": 0.0, "months": 0})
    for r in rows:
        if period == "season" and r["month"] not in SEASON:
            continue
        t = per_year[r["year"]]
        t["value"] += r["value"]
        t["months"] += 1
        if r["source"] == "aqua_converted":
            t["converted"] += r["value"]
        else:
            t["observed"] += r["value"]
    output = []
    for y, t in sorted(per_year.items()):
        if t["converted"] == 0 and t["observed"] == 0 and t["months"] == 0:
            continue
        if t["observed"] == 0:
            lo, hi = band(tables, period, area, t["converted"])
            source = "aqua_converted"
        elif t["converted"] == 0:
            lo = hi = round(t["observed"], 1)
            source = "snpp"
        else:
            lo_c, hi_c = band(tables, "monthly", area, t["converted"])
            lo, hi = round(t["observed"] + lo_c, 1), round(t["observed"] + hi_c, 1)
            source = "mixed"
        output.append({"year": y, "value": round(t["value"], 1), "low": lo, "high": hi, "source": source})
    history = [r["value"] for r in output if r["year"] in REFERENCE]
    normal = {
        "median": round(st.median(history), 1),
        "p10": round(percentile(history, 0.1), 1),
        "p90": round(percentile(history, 0.9), 1),
    }
    for r in output:
        r["anomaly_pct"] = round(100 * (r["value"] / normal["median"] - 1), 1) if normal["median"] > 0 else None
    return {"years": output, "normal": normal}


def main():
    count, pieces = m.load()
    info = json.loads((m.DERIVED / "model.json").read_text())
    chosen = info["chosen"]
    fit = m.CANDIDATES[chosen]
    excluded = m.excluded_months()
    calibration = m.pairs(count, pieces, m.CALIBRATION, excluded)
    _, predict = fit(calibration)
    tables = bands(predict, m.pairs(count, pieces, BAND_YEARS, excluded))
    outages = json.loads((m.DERIVED / "outages.json").read_text())
    filled = {(int(t[:4]), int(t[5:])) for t in outages["snpp_filled_months"]}

    pred_c, obs_c = by_area(predict, m.pairs(count, pieces, COVERAGE_YEARS, excluded))
    band_coverage = coverage(tables, pred_c, obs_c)

    aqua, snpp, n20, conv = (defaultdict(float) for _ in range(4))
    for dep, reg in pieces:
        for y, month in months():
            a = count.get(("Aqua", dep, reg, y, month), 0)
            p = predict(dep, reg, month, a)
            for area in areas_of(dep, reg):
                aqua[area, y, month] += a
                snpp[area, y, month] += count.get((m.TARGET, dep, reg, y, month), 0)
                n20[area, y, month] += count.get(("NOAA20", dep, reg, y, month), 0)
                conv[area, y, month] += p

    geo = json.loads((ROOT / "data" / "boundaries" / "peru_adm1_simplified.geojson").read_text())
    names = {f["properties"]["shapeISO"]: f["properties"]["shapeName"] for f in geo["features"]}
    names["PE-LMA*"] = "Metropolitan Lima"
    names["PE-LIM"] = "Lima (provinces)"
    names["PE-CAL"] = "Callao"
    area_list = [{"id": "PE", "name": "Peru", "level": "country"}]
    area_list += [{"id": f"R-{r}", "name": REGION_NAMES[r], "level": "region"} for r in m.REGIONS]
    area_list += sorted(({"id": d, "name": names[d], "level": "department"} for d in names), key=lambda x: x["name"])
    present = {a for a, _, _ in conv}

    series = {}
    for area in (x["id"] for x in area_list):
        rows = []
        for y, month in months():
            k = (area, y, month)
            if (y, month) < SNPP_START:
                value, source = conv[k], "aqua_converted"
                lo, hi = band(tables, "monthly", area, conv[k])
            else:
                source = "snpp_filled" if (y, month) in filled else "snpp"
                value, lo, hi = snpp[k], round(snpp[k], 1), round(snpp[k], 1)
            rows.append(
                {
                    "year": y,
                    "month": month,
                    "value": round(value, 1),
                    "source": source,
                    "low": lo,
                    "high": hi,
                    "low_activity": round(value, 1) < LOW_ACTIVITY,
                    "aqua": int(aqua[k]),
                    "aqua_converted": round(conv[k], 1),
                    "aqua_reliable": (y, month) not in excluded and y <= 2021,
                    "snpp": round(snpp[k], 1) if (y, month) >= (2012, 1) else None,
                    "noaa20": int(n20[k]) if y >= 2018 else None,
                }
            )
        normal = []
        for month in m.MONTHS:
            history = [r["value"] for r in rows if r["month"] == month and r["year"] in REFERENCE]
            normal.append(
                {
                    "month": month,
                    "median": round(st.median(history), 1),
                    "p10": round(percentile(history, 0.1), 1),
                    "p90": round(percentile(history, 0.9), 1),
                }
            )
        series[area] = {
            "months": rows,
            "normal": normal,
            "has_data": area in present,
            "season": period_summary(rows, tables, "season", area),
            "annual": period_summary(rows, tables, "annual", area),
        }

    method = {
        "scale": "daytime Suomi NPP cell-days (0.05-degree cells, local date UTC-5)",
        "segments": {
            "aqua_converted": "2003-01 to 2012-01",
            "snpp": "2012-02 to 2025-12",
            "snpp_filled": "months with Suomi NPP outage days filled from NOAA-20",
        },
        "outages": outages,
        "band_method": "block-wise conformal: fit 2013-2017, bands from 2018-2020, coverage checked on 2021-2022",
        "band_coverage_2021_2022_pct": band_coverage,
        "season": "July to October",
        "low_activity": f"months below {LOW_ACTIVITY} cell-days: high relative error, show them dimmed",
        "chosen_model": chosen,
        "parameters": info["candidates"][chosen]["parameters"],
        "model_comparison": {
            n: {
                "cv_wape_department": round(r["cv_wape_department"], 1),
                "test_wape_department": round(r["test_2018_2022"]["wape_department"], 1),
                "test_wape_country": round(r["test_2018_2022"]["wape_country"], 1),
                "test_bias_country": round(r["test_2018_2022"]["bias_country_pct"], 1),
            }
            for n, r in info["candidates"].items()
        },
        "design": info["design"],
        "bands": {
            period: {
                f'{g}|size>{([0] + (SIZE_LIMITS if period == "monthly" else AGGREGATE_SIZE_LIMITS))[s]}': {
                    "p10": round(lo, 3),
                    "p90": round(hi, 3),
                    "n": n,
                }
                for (g, s), (lo, hi, n) in sorted(tables[period].items())
            }
            for period in tables
        },
        "normal_reference": [REFERENCE[0], REFERENCE[-1]],
        "filters": "daytime; type=0; Aqua confidence >= 30; VIIRS nominal or high; no repeated rows",
        "regions": "approximated from elevation (highlands >= 2000 m or between peaks); not the official map",
        "sources": [
            "NASA FIRMS yearly country files (MODIS C6.x and VIIRS 375 m C2)",
            "geoBoundaries gbOpen PER ADM1 (public domain)",
            "Terrarium elevation tiles (AWS Open Data)",
        ],
    }
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "areas.json").write_text(json.dumps(area_list, ensure_ascii=False) + "\n")
    (WEB / "series.json").write_text(json.dumps(series, ensure_ascii=False, separators=(",", ":")) + "\n")
    (WEB / "method.json").write_text(json.dumps(method, ensure_ascii=False, indent=2) + "\n")
    shutil.copyfile(ROOT / "data" / "boundaries" / "peru_adm1_simplified.geojson", WEB / "departments.geojson")

    pe = series["PE"]["months"]
    for y in (2005, 2010, 2012, 2013, 2024):
        print(y, round(sum(r["value"] for r in pe if r["year"] == y)))
    for period, t in tables.items():
        print("bands", period, {k: (round(v[0], 2), round(v[1], 2), v[2]) for k, v in sorted(t.items())})
    print("P10-P90 coverage on 2021-2022 (expected ~80 %):", method["band_coverage_2021_2022_pct"])
    print("Peru season:", [(r["year"], r["value"], r["low"], r["high"]) for r in series["PE"]["season"]["years"][:3]])
    print("series.json size:", (WEB / "series.json").stat().st_size // 1024, "KiB")


if __name__ == "__main__":
    main()
