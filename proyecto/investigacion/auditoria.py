"""Auditoría del método: reproduce las comprobaciones de docs/METODOS.md.

Requiere datos/derivados/auditoria.pkl (investigacion/extraer.py) y los derivados del pipeline.
Escribe docs/auditoria.txt.
"""
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta
import bisect
import csv
import pickle
import statistics as st
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'pipeline'))
import modelo as m

LIMITES_FRP = [2, 5, 10, 20, 50, 100, 200, 500]


def main():
    datos = pickle.loads((m.DERIVADOS / 'auditoria.pkl').read_bytes())
    filas_dia, hora, celda_dia = datos['filas_dia'], datos['hora'], datos['celda_dia']
    atributos = {}
    with (m.DERIVADOS / 'celdas.csv').open() as f:
        for r in csv.DictReader(f):
            atributos[int(r['i']), int(r['j'])] = (r['departamento'], r['region'])
    aqua, snpp = celda_dia['Aqua'], celda_dia['SNPP']
    por_dia = defaultdict(lambda: defaultdict(int))
    for sensor, d in celda_dia.items():
        for (_, _, dia) in d:
            por_dia[sensor][dia] += 1
    out = []

    out.append('1. Hora solar local media de las detecciones diurnas aceptadas, por año')
    for plat in ('Aqua', 'SNPP', 'NOAA20'):
        out.append(f'   {plat:7s} ' + ' '.join(f'{y}:{st.mean(v):.2f}' for y, v in sorted(hora[plat].items())))

    out.append('\n2. Rachas de días sin ninguna fila en el archivo (>= 3 días), con la media del sensor de referencia')
    for plat, ref, desde in (('Aqua', 'SNPP', '2012-01-20'), ('SNPP', 'NOAA20', '2018-04-01'), ('NOAA20', 'SNPP', '2018-04-01')):
        d, racha = date.fromisoformat(desde), []
        while d <= date(2025, 12, 31):
            if filas_dia[plat].get(d.isoformat(), 0) == 0:
                racha.append(d)
            else:
                if len(racha) >= 3:
                    media = st.mean(filas_dia[ref].get(x.isoformat(), 0) for x in racha)
                    out.append(f'   {plat:7s} {racha[0]} a {racha[-1]} ({len(racha)} días); {ref}: {media:.0f} filas/día')
                racha = []
            d += timedelta(days=1)

    out.append('\n3. Razón de celdas-día SNPP/Aqua en tres ventanas de agosto-septiembre')
    for y in range(2016, 2022):
        def total(sensor, a, b):
            d, t = date(y, *a), 0
            while d <= date(y, *b):
                t += por_dia[sensor][d]
                d += timedelta(days=1)
            return t
        v = [(total('SNPP', a, b), total('Aqua', a, b)) for a, b in (((8, 1), (8, 15)), ((8, 16), (9, 2)), ((9, 3), (9, 30)))]
        out.append(f'   {y}: 1-15 ago {v[0][0] / v[0][1]:.2f} | 16 ago-2 sep {v[1][0] / v[1][1]:.2f} | 3-30 sep {v[2][0] / v[2][1]:.2f}')
    abril = [por_dia['Aqua'][date(2022, 4, d)] for d in range(1, 17)]
    out.append(f'   Aqua, 1-16 de abril de 2022: {sum(abril)} celdas-día; SNPP: {sum(por_dia["SNPP"][date(2022, 4, d)] for d in range(1, 17))}')

    out.append('\n4. Coincidencia celda a celda en el mismo día local, 2013-2017')
    en = lambda k: 2013 <= k[2].year <= 2017
    n_aqua = sum(1 for k in aqua if en(k))
    out.append(f'   celdas-día de Aqua que VIIRS también registra: {100 * sum(1 for k in aqua if en(k) and k in snpp) / n_aqua:.0f} %')
    vecina = sum(1 for k in aqua if en(k) and any((k[0] + a, k[1] + b, k[2]) in snpp for a in (-1, 0, 1) for b in (-1, 0, 1)))
    out.append(f'   ... contando también las ocho celdas vecinas: {100 * vecina / n_aqua:.0f} %')
    n, h = defaultdict(int), defaultdict(int)
    for k, (_, frp, _) in snpp.items():
        if en(k):
            b = bisect.bisect(LIMITES_FRP, frp)
            n[b] += 1
            h[b] += k in aqua
    out.append('   P(Aqua registra la celda-día | FRP total de VIIRS en MW):')
    out.append('   ' + '  '.join(f'>={([0] + LIMITES_FRP)[b]}: {100 * h[b] / n[b]:.0f} %' for b in sorted(n)))

    out.append('\n5. Alternativa: quedarse con las celdas-día de VIIRS con FRP total >= F0 y compararlas con Aqua (2018-2022, sin meses con corte)')
    fuera = m.meses_excluidos() | {(2022, 7), (2022, 8)}
    for f0 in (0, 10, 15, 20, 25, 30):
        dep, pais = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
        for sensor, pos, tabla in (('SNPP', 0, snpp), ('Aqua', 1, aqua)):
            for k, (_, frp, _) in tabla.items():
                y, mes = k[2].year, k[2].month
                if 2018 <= y <= 2022 and (y, mes) not in fuera and (sensor == 'Aqua' or frp >= f0):
                    dep[atributos[k[0], k[1]][0], y, mes][pos] += 1
                    pais[y, mes][pos] += 1
        a = sum(v[1] for v in pais.values())
        out.append(f'   F0 = {f0:2d} MW: razón {sum(v[0] for v in pais.values()) / a:.2f}; WAPE departamento '
                   f'{100 * sum(abs(v[0] - v[1]) for v in dep.values()) / a:.0f} %; WAPE país '
                   f'{100 * sum(abs(v[0] - v[1]) for v in pais.values()) / a:.0f} %')

    (RAIZ / 'docs' / 'auditoria.txt').write_text('\n'.join(out) + '\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
