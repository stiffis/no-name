"""Error floor and aggregation: how low can the conversion error go?

1. Floor: predict Suomi NPP from NOAA-20 (same instrument, same orbit, ~50 min apart) with a single
   ratio, 2019-2021. No MODIS -> VIIRS method can beat the disagreement between two identical sensors.
2. The chosen model's test error (2018-2022) at five aggregation levels.
3. The chosen model's monthly department error split by activity size.
Writes docs/floor.txt.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import model as m

LEVELS = {
    "department-month": lambda dep, y, month: (dep, y, month),
    "country-month": lambda dep, y, month: (y, month),
    "department-season": lambda dep, y, month: (dep, y) if month in (7, 8, 9, 10) else None,
    "department-year": lambda dep, y, month: (dep, y),
    "country-year": lambda dep, y, month: (y,),
}


def wape_at(pairs_of_values, level):
    totals = defaultdict(lambda: [0.0, 0.0])
    for (dep, y, month), (p, o) in pairs_of_values.items():
        key = LEVELS[level](dep, y, month)
        if key is not None:
            totals[key][0] += p
            totals[key][1] += o
    return 100 * sum(abs(p - o) for p, o in totals.values()) / sum(o for _, o in totals.values())


def main():
    count, pieces = m.load()
    excluded = m.excluded_months()
    out = []

    snpp, n20 = defaultdict(float), defaultdict(float)
    for dep, reg in pieces:
        for y in (2019, 2020, 2021):
            for month in m.MONTHS:
                snpp[dep, y, month] += count.get(("SNPP", dep, reg, y, month), 0)
                n20[dep, y, month] += count.get(("NOAA20", dep, reg, y, month), 0)
    rho = sum(snpp.values()) / sum(n20.values())
    floor = {k: (rho * n20[k], snpp[k]) for k in snpp}
    out.append(f"1. Floor: Suomi NPP predicted from NOAA-20 x {rho:.3f}, 2019-2021 (no gap filling)")
    out.append("   " + "  ".join(f"{lvl} {wape_at(floor, lvl):.1f} %" for lvl in LEVELS))

    info = json.loads((m.DERIVED / "model.json").read_text())
    _, predict = m.CANDIDATES[info["chosen"]](m.pairs(count, pieces, m.CALIBRATION, excluded))
    test = defaultdict(lambda: [0.0, 0.0])
    for (dep, reg, y, month), (a, v) in m.pairs(count, pieces, m.TEST, excluded).items():
        test[dep, y, month][0] += predict(dep, reg, month, a)
        test[dep, y, month][1] += v
    test_pairs = {k: tuple(v) for k, v in test.items()}
    out.append(f'\n2. Chosen model ({info["chosen"]}), test 2018-2022')
    out.append("   " + "  ".join(f"{lvl} {wape_at(test_pairs, lvl):.1f} %" for lvl in LEVELS))

    out.append("\n3. Department-month test error by observed activity")
    total_error = sum(abs(p - o) for p, o in test_pairs.values())
    for lo, hi in ((0, 20), (20, 100), (100, 500), (500, float("inf"))):
        subset = [(p, o) for p, o in test_pairs.values() if lo <= o < hi]
        error = sum(abs(p - o) for p, o in subset)
        label = f"{lo}-{hi:.0f}" if hi != float("inf") else f"{lo}+"
        out.append(
            f"   {label:>8s} cell-days: n={len(subset):4d}  WAPE {100 * error / max(1, sum(o for _, o in subset)):5.1f} %"
            f"  share of total error {100 * error / total_error:4.1f} %"
        )

    (ROOT / "docs" / "floor.txt").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
