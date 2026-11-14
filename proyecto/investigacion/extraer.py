"""Extrae de los CSV originales lo necesario para auditar el método (una sola lectura).

Salida: datos/derivados/auditoria.pkl con
  filas_dia[plataforma][fecha_utc]         filas de cualquier tipo (para detectar cortes)
  hora[plataforma][anio]                   horas solares locales de detecciones diurnas aceptadas
  celda_dia[sensor][(i, j, fecha_local)]   (focos, FRP sumada, scan mínimo) de detecciones diurnas aceptadas
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
import csv
import pickle
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
import celdas as c

PLATAFORMA = {'Terra': 'Terra', 'T': 'Terra', 'Aqua': 'Aqua', 'A': 'Aqua', 'N': 'SNPP', 'N20': 'NOAA20'}


def main():
    filas_dia = defaultdict(lambda: defaultdict(int))
    hora = defaultdict(lambda: defaultdict(list))
    celda_dia = defaultdict(dict)
    for fuente, sensor, _ in c.FUENTES:
        for ruta in sorted(c.ORIGINALES.glob(f'{fuente}_*_Peru.csv')):
            with ruta.open(newline='') as f:
                for fila in csv.DictReader(f):
                    plat = PLATAFORMA[fila['satellite']]
                    filas_dia[plat][fila['acq_date']] += 1
                    if plat == 'Terra' or not c.aceptar(fuente, fila):
                        continue
                    utc = datetime.strptime(fila['acq_date'] + fila['acq_time'].zfill(4), '%Y-%m-%d%H%M')
                    local = utc - timedelta(hours=5)
                    solar = (utc.hour + utc.minute / 60 + float(fila['longitude']) / 15) % 24
                    hora[plat][local.year].append(solar)
                    k = (c.indice(fila['latitude'], 90), c.indice(fila['longitude'], 180), local.date())
                    n, frp, scan = celda_dia[sensor].get(k, (0, 0.0, 99.0))
                    celda_dia[sensor][k] = (n + 1, frp + float(fila['frp'] or 0), min(scan, float(fila['scan'])))
    salida = {'filas_dia': {p: dict(d) for p, d in filas_dia.items()},
              'hora': {p: dict(d) for p, d in hora.items()},
              'celda_dia': dict(celda_dia)}
    with (c.DERIVADOS / 'auditoria.pkl').open('wb') as f:
        pickle.dump(salida, f)
    print({s: len(d) for s, d in celda_dia.items()})


if __name__ == '__main__':
    main()
