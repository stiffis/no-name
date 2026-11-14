"""Figuras vectoriales del caso peruano, calculadas desde las tablas del libro.

Requiere Matplotlib y NumPy. No descarga ni modifica las observaciones originales.
"""
from pathlib import Path
import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.ticker import FuncFormatter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figuras"
BLUE, ORANGE, GREEN = "#1F5A8A", "#C8421C", "#2F6B3C"
INK, MUTED, GRID = "#24313A", "#58636B", "#E3E7EA"
MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": "#AFB8BF", "axes.linewidth": .65,
    "lines.linewidth": 1.8, "lines.markersize": 4,
    "legend.fontsize": 8, "legend.frameon": False,
    "pdf.fonttype": 42, "svg.fonttype": "none",
})


def rows(name):
    with (ROOT / "datos" / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", "\u202f").replace(".", ",")


def heading(fig, title, subtitle):
    fig.text(.13, .965, title, fontsize=11, weight="bold", va="top")
    fig.text(.13, .913, subtitle, fontsize=8, color=MUTED, va="top")


def axes_style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=3, width=.65)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, linewidth=.6)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: number(value)))


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", metadata={
        "Title": name, "Creator": "scripts/generar_graficos.py",
        "CreationDate": None, "ModDate": None,
    })
    fig.savefig(OUT / f"{name}.svg", metadata={"Date": None})
    fig.savefig(OUT / f"{name}.png", dpi=180)
    plt.close(fig)


def calendar():
    data = rows("peru_calendario.csv")
    values = np.full((12, 12), np.nan)
    for row in data:
        values[int(row["fila"]), int(row["mes"]) - 1] = float(row["actividad"])
    assert np.isfinite(values).all()
    cmap = LinearSegmentedColormap.from_list("actividad", ["#FFF8E9", "#F7C875", "#E28735", "#B13C22", "#70251D"])
    norm = Normalize(0, 18000)
    fig, ax = plt.subplots(figsize=(6.3, 5.7))
    fig.subplots_adjust(left=.13, right=.98, top=.83, bottom=.21)
    heading(fig, "Qué meses concentran la actividad", "Perú · VIIRS/Suomi NPP diurno · 2013–2024")
    im = ax.imshow(values, cmap=cmap, norm=norm, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(12), MONTHS)
    ax.set_yticks(range(12), range(2013, 2025))
    ax.set_xticks(np.arange(-.5, 12, 1), minor=True)
    ax.set_yticks(np.arange(-.5, 12, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.1)
    ax.tick_params(which="both", length=0, pad=6)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for y, row in enumerate(values):
        for x, value in enumerate(row):
            rgb = np.array(cmap(norm(value))[:3])
            linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
            luminance = float(linear @ np.array([.2126, .7152, .0722]))
            ax.text(x, y, number(value), ha="center", va="center", fontsize=7.4,
                    color="white" if luminance < .179 else "#241710")
    bar = fig.colorbar(im, cax=fig.add_axes([.25, .10, .61, .024]), orientation="horizontal",
                       ticks=[0, 6000, 12000, 18000])
    bar.ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: number(value)))
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=2, labelsize=8)
    bar.set_label("Celdas-día con detección · misma escala para todos los años", fontsize=8)
    save(fig, "peru_calendario")


def seasonal():
    data = rows("peru_climatologia.csv")
    x = np.arange(1, 13)
    get = lambda key: np.array([float(row[key]) for row in data])
    median, actual = get("mediana"), get("actual2024")
    fig, ax = plt.subplots(figsize=(6.3, 3.9))
    fig.subplots_adjust(left=.13, right=.98, bottom=.13, top=.77)
    heading(fig, "Comparar cada mes con su historia", "Perú · VIIRS diurno · referencia 2013–2023 frente a 2024")
    axes_style(ax)
    ax.fill_between(x, get("q10"), get("q90"), color=BLUE, alpha=.16, linewidth=0, label="P10–P90 histórico")
    ax.plot(x, median, color=BLUE, marker="o", label="Mediana 2013–2023")
    ax.plot(x, actual, color=ORANGE, marker="s", label="2024")
    ax.set(xlim=(.7, 12.3), ylim=(0, 18000), ylabel="Celdas-día con detección")
    ax.set_xticks(x, MONTHS)
    ax.set_yticks([0, 4000, 8000, 12000, 16000])
    ax.legend(loc="lower left", bbox_to_anchor=(-.015, 1.005), ncols=3, handlelength=1.6, columnspacing=1.3)
    anomaly = 100 * (actual[8] / median[8] - 1)
    ax.annotate(f"Septiembre de 2024\n{number(actual[8])} · +{number(anomaly, 1)} % sobre la mediana",
                xy=(9, actual[8]), xytext=(1.1, 15100), fontsize=8, color=ORANGE,
                arrowprops={"arrowstyle": "-", "color": ORANGE, "lw": .8},
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 2})
    save(fig, "peru_perfil")


def cumulative():
    data = rows("peru_climatologia.csv")
    x = np.arange(1, 13)
    values = np.array([float(row["acumulado"]) for row in data])
    fig, ax = plt.subplots(figsize=(6.3, 3.7))
    fig.subplots_adjust(left=.13, right=.98, bottom=.15, top=.81)
    heading(fig, "Cuándo se acumula la actividad del año", "Perú · perfil medio de 2013–2023 · cada año tiene el mismo peso")
    axes_style(ax)
    ax.fill_between(x, values, color=GREEN, alpha=.07, linewidth=0)
    ax.plot(x, values, color=GREEN, marker="o")
    ax.set(xlim=(.7, 12.3), ylim=(0, 104), ylabel="Actividad anual acumulada (%)")
    ax.set_xticks(x, MONTHS)
    ax.set_yticks([0, 25, 50, 75, 100])
    for threshold in [10, 90]:
        ax.axhline(threshold, color="#A57736", ls=(0, (4, 3)), lw=.9)
        ax.text(.9, threshold + 2, f"{threshold} %", color="#835D28", fontsize=8,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": .5})
    for threshold, label, position in [(10, "Junio", (3.2, 35)), (90, "Octubre", (6.2, 78))]:
        i = int(np.flatnonzero(values >= threshold)[0])
        ax.plot(x[i], values[i], "o", color=GREEN, markersize=7, markerfacecolor="white", markeredgewidth=1.6)
        ax.annotate(f"{label} · {number(values[i], 1)} %", xy=(x[i], values[i]), xytext=position,
                    fontsize=8, color=GREEN,
                    arrowprops={"arrowstyle": "-", "color": GREEN, "lw": .8})
    save(fig, "peru_acumulado")


def validation():
    data = rows("peru_validacion.csv")
    report = json.loads((ROOT / "datos/resultados_peru.json").read_text())
    x = np.arange(1, 25)
    actual = np.array([float(row["viirs"]) for row in data])
    predicted = np.array([float(row["aqua_convertido"]) for row in data])
    error = predicted - actual
    fig, (ax, residual) = plt.subplots(2, 1, figsize=(6.3, 5.1), sharex=True,
                                      gridspec_kw={"height_ratios": [2.2, 1], "hspace": .12})
    fig.subplots_adjust(left=.13, right=.98, top=.80, bottom=.15)
    heading(fig, "La coincidencia estacional no elimina el error", "Perú · ajuste 2018–2020 · prueba independiente en 2021–2022")
    for panel in [ax, residual]:
        axes_style(panel)
        panel.axvspan(12.5, 24.5, color="#F4F6F7", zorder=-2)
        panel.axvline(12.5, color="#B5BEC4", ls=(0, (3, 3)), lw=.8)
        panel.set_xlim(.5, 24.5)
    ax.plot(x, actual, color=ORANGE, marker="o", label="VIIRS observado")
    ax.plot(x, predicted, color=BLUE, marker="s", ls="--", label="Aqua × razón de ajuste")
    ax.set_ylim(0, 18500)
    ax.set_yticks([0, 5000, 10000, 15000])
    ax.set_ylabel("Actividad (celdas-día o equivalente)", fontsize=8)
    ax.legend(loc="lower left", bbox_to_anchor=(-.015, 1.005), ncols=2, handlelength=2.2)
    residual.bar(x, error, color=BLUE, width=.65, alpha=.8)
    residual.axhline(0, color=INK, lw=.8)
    residual.set_ylabel("Error", fontsize=9)
    residual.set_xticks([1, 4, 7, 10, 13, 16, 19, 22],
                        ["Ene\n2021", "Abr", "Jul", "Oct", "Ene\n2022", "Abr", "Jul", "Oct"])
    residual.text(.015, .96, "Estimación − VIIRS", transform=residual.transAxes, fontsize=7.5,
                  va="top", color=MUTED)
    fig.text(.13, .025, f"24 meses de prueba · MAE: {number(report['mae_prueba'], 1)} · WAPE: {number(report['wape_prueba_porcentaje'], 1)} %",
             fontsize=8, color=MUTED)
    save(fig, "peru_validacion")


if __name__ == "__main__":
    calendar()
    seasonal()
    cumulative()
    validation()
    print("Cuatro gráficos reproducidos en PDF vectorial, SVG y PNG.")
