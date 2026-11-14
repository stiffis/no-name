"""Step 2: choose and fit the Aqua -> VIIRS conversion (Suomi NPP with outages filled).

Fitting unit: department x natural region piece, per month. Departments, regions and the country
are sums of converted pieces, so every level is consistent with the others.

Design:
  calibration 2013-2017 (MODIS label 6.2, the same as 2003-2011, and before Aqua's orbital drift);
  model selection by leave-one-year-out cross-validation within 2013-2017;
  independent test 2018-2022; contrast 2023-2025 (Aqua is drifting: a worse fit is expected).
  Months with a documented Aqua outage (outages.json) are excluded everywhere.

Candidates, with V the VIIRS count and A the Aqua count of a piece in a month:
  ratio          V = r A                      (single r, per region, or per region and season)
  log-linear     log(1+V) = a + b log(1+A)    with Duan's retransformation correction
  Poisson        log E[V] = a + b log(1+A)    by maximum likelihood
  Poisson+piece  E[V] = f_t exp(a + b log(1+A)), with f_t = (V_t + k)/(P_t + k): each piece's own
                 factor, shrunk towards 1 with k pseudo-observations
Season: July-October versus the rest. The log-linear models are kept to document why they fail
on zero-heavy counts: Duan's correction inflates and the totals become biased.
Output: data/derived/model.json
"""

import csv
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
CALIBRATION = [2013, 2014, 2015, 2016, 2017]
TEST = [2018, 2019, 2020, 2021, 2022]
CONTRAST = [2023, 2024, 2025]
MONTHS = range(1, 13)
REGIONS = ["coast", "highlands", "rainforest"]
TARGET = "VIIRS"


def season(month):
    return "dry" if month in (7, 8, 9, 10) else "rest"


def load():
    attributes = {}
    with (DERIVED / "cells.csv").open() as f:
        for r in csv.DictReader(f):
            attributes[int(r["i"]), int(r["j"])] = (r["department"], r["region"])
    count = defaultdict(float)
    with (DERIVED / "cell_months.csv").open() as f:
        for r in csv.DictReader(f):
            dep, reg = attributes[int(r["i"]), int(r["j"])]
            count[r["sensor"], dep, reg, int(r["year"]), int(r["month"])] += float(r["days"])
    pieces = sorted({(d, r) for d, r in attributes.values()})
    return count, pieces


def excluded_months():
    outages = json.loads((DERIVED / "outages.json").read_text())
    return frozenset((int(t[:4]), int(t[5:])) for t in outages["aqua_excluded_months"])


def ratio(group):
    def fit(data):
        num, den = defaultdict(float), defaultdict(float)
        for (_, reg, _, m), (a, v) in data.items():
            num[group(reg, m)] += v
            den[group(reg, m)] += a
        r = {k: num[k] / den[k] for k in num if den[k] > 0}
        total = sum(num.values()) / sum(den.values())
        return {"r": {str(k): v for k, v in r.items()}}, lambda dep, reg, m, a: r.get(group(reg, m), total) * a

    return fit


def log_linear(group):
    def fit(data):
        points = defaultdict(list)
        for (_, reg, _, m), (a, v) in data.items():
            points[group(reg, m)].append((math.log1p(a), math.log1p(v)))
        params = {}
        for k, p in points.items():
            xs, ys = [x for x, _ in p], [y for _, y in p]
            mx, my = st.mean(xs), st.mean(ys)
            b = sum((x - mx) * (y - my) for x, y in p) / sum((x - mx) ** 2 for x in xs)
            a = my - b * mx
            duan = st.mean(math.exp(y - (a + b * x)) for x, y in p)
            params[k] = (a, b, duan)

        def predict(dep, reg, m, aqua_count):
            a, b, duan = params[group(reg, m)]
            return max(0.0, math.exp(a + b * math.log1p(aqua_count)) * duan - 1)

        return {"params": {str(k): {"a": a, "b": b, "duan": d} for k, (a, b, d) in params.items()}}, predict

    return fit


def poisson(group):
    def fit(data):
        points = defaultdict(list)
        for (_, reg, _, m), (a, v) in data.items():
            points[group(reg, m)].append((math.log1p(a), v))
        params = {}
        for k, p in points.items():
            a, b = math.log(max(st.mean(v for _, v in p), 1e-9)), 0.0
            for _ in range(100):
                ga = gb = haa = hab = hbb = 0.0
                for x, v in p:
                    mu = math.exp(a + b * x)
                    ga += v - mu
                    gb += (v - mu) * x
                    haa += mu
                    hab += mu * x
                    hbb += mu * x * x
                det = haa * hbb - hab * hab
                da = (hbb * ga - hab * gb) / det
                db = (haa * gb - hab * ga) / det
                a, b = a + da, b + db
                if abs(da) + abs(db) < 1e-12:
                    break
            params[k] = (a, b)

        def predict(dep, reg, m, aqua_count):
            a, b = params[group(reg, m)]
            return math.exp(a + b * math.log1p(aqua_count))

        return {"params": {str(k): {"a": a, "b": b} for k, (a, b) in params.items()}}, predict

    return fit


def with_piece_factor(base, k):
    def fit(data):
        params, base_predict = base(data)
        obs, pred = defaultdict(float), defaultdict(float)
        for (dep, reg, _, m), (a, v) in data.items():
            obs[dep, reg] += v
            pred[dep, reg] += base_predict(dep, reg, m, a)
        factor = {t: (obs[t] + k) / (pred[t] + k) for t in pred}
        params = dict(params, k=k, factor={f"{d}|{r}": f for (d, r), f in factor.items()})
        return params, lambda dep, reg, m, a: factor.get((dep, reg), 1.0) * base_predict(dep, reg, m, a)

    return fit


CANDIDATES = {
    "ratio_single": ratio(lambda reg, m: "all"),
    "ratio_region": ratio(lambda reg, m: reg),
    "ratio_region_season": ratio(lambda reg, m: (reg, season(m))),
    "loglinear_single": log_linear(lambda reg, m: "all"),
    "loglinear_region": log_linear(lambda reg, m: reg),
    "loglinear_region_season": log_linear(lambda reg, m: (reg, season(m))),
    "poisson_single": poisson(lambda reg, m: "all"),
    "poisson_region": poisson(lambda reg, m: reg),
    "poisson_region_season": poisson(lambda reg, m: (reg, season(m))),
    "poisson_region_piece_k50": with_piece_factor(poisson(lambda reg, m: reg), 50),
    "poisson_region_piece_k200": with_piece_factor(poisson(lambda reg, m: reg), 200),
    "poisson_region_season_piece_k50": with_piece_factor(poisson(lambda reg, m: (reg, season(m))), 50),
    "poisson_region_season_piece_k200": with_piece_factor(poisson(lambda reg, m: (reg, season(m))), 200),
}


def pairs(count, pieces, years, excluded=frozenset()):
    return {
        (dep, reg, y, m): (count.get(("Aqua", dep, reg, y, m), 0), count.get((TARGET, dep, reg, y, m), 0))
        for dep, reg in pieces
        for y in years
        for m in MONTHS
        if (y, m) not in excluded
    }


def wape(errors, observed):
    return 100 * sum(abs(e) for e in errors) / sum(observed)


def evaluate(predict, data):
    by_dep, by_country = defaultdict(lambda: [0.0, 0.0]), defaultdict(lambda: [0.0, 0.0])
    e_piece, o_piece = [], []
    for (dep, reg, y, m), (a, v) in data.items():
        p = predict(dep, reg, m, a)
        e_piece.append(p - v)
        o_piece.append(v)
        by_dep[dep, y, m][0] += p
        by_dep[dep, y, m][1] += v
        by_country[y, m][0] += p
        by_country[y, m][1] += v
    return {
        "wape_piece": wape(e_piece, o_piece),
        "wape_department": wape([p - v for p, v in by_dep.values()], [v for _, v in by_dep.values()]),
        "wape_country": wape([p - v for p, v in by_country.values()], [v for _, v in by_country.values()]),
        "bias_country_pct": 100 * sum(p - v for p, v in by_country.values()) / sum(v for _, v in by_country.values()),
    }


def cross_validate(fit, calibration):
    pred, obs = defaultdict(float), defaultdict(float)
    for held_out in CALIBRATION:
        _, predict = fit({k: v for k, v in calibration.items() if k[2] != held_out})
        for (dep, reg, y, m), (a, v) in calibration.items():
            if y == held_out:
                pred[dep, y, m] += predict(dep, reg, m, a)
                obs[dep, y, m] += v
    return pred, obs


def main():
    count, pieces = load()
    excluded = excluded_months()
    calibration = pairs(count, pieces, CALIBRATION, excluded)
    results = {}
    for name, fit in CANDIDATES.items():
        pred, obs = cross_validate(fit, calibration)
        params, predict = fit(calibration)
        results[name] = {
            "cv_wape_department": wape([pred[k] - obs[k] for k in obs], list(obs.values())),
            "parameters": params,
            "test_2018_2022": evaluate(predict, pairs(count, pieces, TEST, excluded)),
            "test_2018_2022_without_excluding_outages": evaluate(predict, pairs(count, pieces, TEST)),
            "contrast_2023_2025": evaluate(predict, pairs(count, pieces, CONTRAST, excluded)),
        }
    chosen = min(results, key=lambda n: results[n]["cv_wape_department"])
    output = {
        "design": {
            "calibration": CALIBRATION,
            "test": TEST,
            "contrast": CONTRAST,
            "months_excluded_for_aqua_outages": sorted(f"{y}-{m:02d}" for y, m in excluded),
            "selection": "leave-one-year-out cross-validation, department-month WAPE",
            "unit": "department x natural region, monthly",
            "target": "Suomi NPP with outage days filled from NOAA-20",
        },
        "chosen": chosen,
        "pieces": [list(t) for t in pieces],
        "candidates": results,
    }
    (DERIVED / "model.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")

    print(
        f'{"model":36s} {"CV dep":>7s} | test: {"dep":>6s} {"ctry":>6s} {"bias":>6s} | contrast: {"dep":>6s} {"ctry":>6s} {"bias":>6s}'
    )
    for n, r in results.items():
        t, c = r["test_2018_2022"], r["contrast_2023_2025"]
        print(
            f'{n:36s} {r["cv_wape_department"]:7.1f} | {t["wape_department"]:12.1f} {t["wape_country"]:6.1f} '
            f'{t["bias_country_pct"]:+6.1f} | {c["wape_department"]:16.1f} {c["wape_country"]:6.1f} {c["bias_country_pct"]:+6.1f}'
        )
    print("chosen by cross-validation:", chosen)


if __name__ == "__main__":
    main()
