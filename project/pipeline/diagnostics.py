"""Step 4: continuity figure across the 2012 splice (docs/continuity_2012.png)."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main():
    series = json.loads((ROOT / "web" / "data" / "series.json").read_text())
    areas = [("PE", "Peru"), ("PE-JUN", "Junín"), ("R-coast", "Coast (approximate)")]
    fig, axes = plt.subplots(len(areas), 1, figsize=(13, 10))
    for ax, (area, title) in zip(axes, areas):
        rows = series[area]["months"]
        t = [r["year"] + (r["month"] - 0.5) / 12 for r in rows]
        conv = [(x, r) for x, r in zip(t, rows) if r["source"] == "aqua_converted"]
        ax.plot(t, [r["aqua"] for r in rows], color="#999999", lw=0.8, label="Aqua, not converted")
        ax.fill_between(
            [x for x, _ in conv],
            [r["low"] for _, r in conv],
            [r["high"] for _, r in conv],
            color="#1F5A8A",
            alpha=0.2,
            label="P10-P90 band",
        )
        ax.plot(t, [r["aqua_converted"] for r in rows], color="#1F5A8A", lw=1, label="Aqua converted")
        ax.plot(
            [x for x, r in zip(t, rows) if r["snpp"] is not None],
            [r["snpp"] for r in rows if r["snpp"] is not None],
            color="#C8421C",
            lw=1,
            label="Suomi NPP (outages filled)",
        )
        ax.axvline(2012 + 1 / 12, color="black", ls="--", lw=0.8)
        ax.set_title(title, loc="left")
        ax.set_ylabel("cell-days per month")
        ax.legend(loc="upper left", fontsize=8, ncol=4, frameon=False)
    fig.suptitle("Continuity of the MODIS -> VIIRS splice (Peru, daytime overpasses)")
    fig.tight_layout()
    fig.savefig(ROOT / "docs" / "continuity_2012.png", dpi=110)


if __name__ == "__main__":
    main()
