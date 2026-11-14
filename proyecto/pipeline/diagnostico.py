"""Paso 4: figura de continuidad en el empalme de 2012 (docs/continuidad_2012.png)."""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RAIZ = Path(__file__).resolve().parents[1]


def main():
    series = json.loads((RAIZ / 'web' / 'datos' / 'series.json').read_text())
    areas = [('PE', 'Perú'), ('PE-JUN', 'Junín'), ('R-costa', 'Costa (aproximada)')]
    fig, ejes = plt.subplots(len(areas), 1, figsize=(13, 10))
    for eje, (area, titulo) in zip(ejes, areas):
        f = series[area]['meses']
        t = [x['anio'] + (x['mes'] - 0.5) / 12 for x in f]
        conv = [(a, x) for a, x in zip(t, f) if x['fuente'] == 'aqua_convertido']
        eje.plot(t, [x['aqua'] for x in f], color='#999999', lw=0.8, label='Aqua sin convertir')
        eje.fill_between([a for a, _ in conv], [x['bajo'] for _, x in conv], [x['alto'] for _, x in conv],
                         color='#1F5A8A', alpha=0.2, label='banda P10-P90')
        eje.plot(t, [x['aqua_convertido'] for x in f], color='#1F5A8A', lw=1, label='Aqua convertido')
        eje.plot([a for a, x in zip(t, f) if x['snpp'] is not None], [x['snpp'] for x in f if x['snpp'] is not None],
                 color='#C8421C', lw=1, label='Suomi NPP (cortes rellenados)')
        eje.axvline(2012 + 1 / 12, color='black', ls='--', lw=0.8)
        eje.set_title(titulo, loc='left')
        eje.set_ylabel('celdas-día por mes')
        eje.legend(loc='upper left', fontsize=8, ncol=4, frameon=False)
    fig.suptitle('Continuidad del empalme MODIS -> VIIRS (Perú, pasadas diurnas)')
    fig.tight_layout()
    fig.savefig(RAIZ / 'docs' / 'continuidad_2012.png', dpi=110)


if __name__ == '__main__':
    main()
