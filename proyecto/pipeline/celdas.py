"""Paso 1: de los CSV de FIRMS a celdas-día mensuales por celda de 0,05 grados.

Filtros (los del libro): pasada diurna, type=0, sin filas idénticas repetidas,
MODIS solo Aqua con confianza >= 30, VIIRS con confianza nominal o alta.
Fecha local UTC-5. Celda: índices enteros desde (-90, -180) con paso 0,05 grados.

Cortes de servicio:
  Suomi NPP: un día local es de corte si SNPP no tiene ninguna celda-día en el país y NOAA-20 tiene
  al menos 30. Esos días se rellenan con las celdas-día de NOAA-20 multiplicadas por la razón
  SNPP/NOAA-20 de 2019-2021. El resultado es el sensor "VIIRS" (Suomi NPP rellenado).
  Aqua: cortes documentados por NASA (no dejan días vacíos porque se reprocesaron con cobertura
  parcial); sus meses se excluyen de la calibración y de la prueba en modelo.py.

Salidas en datos/derivados/:
  celdas_mes.csv   sensor, i, j, anio, mes, dias   (días con al menos una detección)
  cortes.json      días rellenados de Suomi NPP, razón usada y meses de Aqua excluidos
  celdas.csv       i, j, departamento, region      (para cada celda que aparece)
  procedencia.json huellas SHA-256 y conteos de filas de cada archivo original
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
from typing import Any
import csv
import hashlib
import json
import math

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ORIGINALES = RAIZ / 'datos' / 'originales'
DERIVADOS = RAIZ / 'datos' / 'derivados'
FUENTES = [('modis', 'Aqua', range(2002, 2026)),
           ('viirs-snpp', 'SNPP', range(2012, 2026)),
           ('viirs-jpss1', 'NOAA20', range(2018, 2026))]
ZOOM, TESELAS_X, TESELAS_Y = 6, range(17, 20), range(31, 36)
UMBRAL_SIERRA = 2000
CORTES_AQUA = [
    {'desde': '2020-08-16', 'hasta': '2020-09-02', 'causa': 'anomalía del formateador FMU/SSR',
     'fuente': 'https://ladsweb.modaps.eosdis.nasa.gov/alerts-and-issues/171856'},
    {'desde': '2022-03-31', 'hasta': '2022-04-16', 'causa': 'modo seguro de la nave',
     'fuente': 'https://mcst.gsfc.nasa.gov/news'},
]
MINIMO_REFERENCIA = 30
ANIOS_RAZON_NOAA20 = (2019, 2020, 2021)


def indice(valor, origen):
    return int(((Decimal(valor) + origen) * 20).to_integral_value(rounding=ROUND_FLOOR))


def aceptar(fuente, fila):
    if fila['daynight'] != 'D' or fila['type'] != '0':
        return False
    if fuente == 'modis':
        return fila['satellite'] in ('Aqua', 'A') and float(fila['confidence']) >= 30
    return fila['confidence'].lower() in ('n', 'h')


def leer():
    dias = defaultdict(set)
    procedencia = []
    for fuente, sensor, anios in FUENTES:
        for anio in anios:
            nombre = f'{fuente}_{anio}_Peru.csv'
            ruta = ORIGINALES / nombre
            leidas = aceptadas = repetidas = 0
            versiones, vistos = Counter(), set()
            with ruta.open(newline='') as f:
                for fila in csv.DictReader(f):
                    leidas += 1
                    versiones[fila['version']] += 1
                    assert 'NRT' not in fila['version'].upper(), nombre
                    if not aceptar(fuente, fila):
                        continue
                    clave = tuple(fila.values())
                    if clave in vistos:
                        repetidas += 1
                        continue
                    vistos.add(clave)
                    local = datetime.strptime(fila['acq_date'] + fila['acq_time'].zfill(4),
                                              '%Y-%m-%d%H%M') - timedelta(hours=5)
                    i, j = indice(fila['latitude'], 90), indice(fila['longitude'], 180)
                    dias[sensor, i, j, local.year, local.month].add(local.day)
                    aceptadas += 1
            procedencia.append({
                'archivo': nombre, 'sensor': sensor,
                'url': f'https://firms.modaps.eosdis.nasa.gov/data/country/{fuente}/{anio}/{nombre}',
                'sha256': hashlib.sha256(ruta.read_bytes()).hexdigest(), 'bytes': ruta.stat().st_size,
                'fecha_descarga_utc': datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc).isoformat(),
                'filas_originales': leidas, 'filas_aceptadas': aceptadas,
                'repetidas_descartadas': repetidas, 'versiones': dict(versiones)})
    return dias, procedencia


def rellenar_snpp(dias):
    por_dia = defaultdict(lambda: defaultdict(int))
    for (sensor, _, _, y, mes), ds in dias.items():
        for d in ds:
            por_dia[sensor][date(y, mes, d)] += 1
    cortes = sorted(d for d, n in por_dia['NOAA20'].items()
                    if n >= MINIMO_REFERENCIA and por_dia['SNPP'].get(d, 0) == 0)
    razon = (sum(n for d, n in por_dia['SNPP'].items() if d.year in ANIOS_RAZON_NOAA20)
             / sum(n for d, n in por_dia['NOAA20'].items() if d.year in ANIOS_RAZON_NOAA20))
    corte_mes = defaultdict(set)
    for d in cortes:
        corte_mes[d.year, d.month].add(d.day)
    conteos: dict[tuple[str, int, int, int, int], float] = {k: len(v) for k, v in dias.items()}
    for (sensor, i, j, y, mes), ds in dias.items():
        if sensor == 'SNPP':
            conteos['VIIRS', i, j, y, mes] = conteos.get(('VIIRS', i, j, y, mes), 0) + len(ds)
        elif sensor == 'NOAA20' and (y, mes) in corte_mes:
            n = len(ds & corte_mes[y, mes])
            if n:
                conteos['VIIRS', i, j, y, mes] = conteos.get(('VIIRS', i, j, y, mes), 0) + razon * n
    meses_aqua = set()
    for c in CORTES_AQUA:
        d = date.fromisoformat(c['desde'])
        while d <= date.fromisoformat(c['hasta']):
            meses_aqua.add((d.year, d.month))
            d += timedelta(days=1)
    info: dict[str, Any] = {'snpp_dias_rellenados': [d.isoformat() for d in cortes],
            'snpp_meses_rellenados': sorted(f'{y}-{m:02d}' for y, m in corte_mes),
            'razon_snpp_sobre_noaa20': razon, 'anios_razon': list(ANIOS_RAZON_NOAA20),
            'aqua_cortes': CORTES_AQUA,
            'aqua_meses_excluidos': sorted(f'{y}-{m:02d}' for y, m in meses_aqua)}
    return conteos, info


def cargar_relieve():
    mosaico = np.zeros((256 * len(TESELAS_Y), 256 * len(TESELAS_X)))
    for a, x in enumerate(TESELAS_X):
        for b, y in enumerate(TESELAS_Y):
            rgb = np.asarray(Image.open(RAIZ / 'datos' / 'relieve' / f'{ZOOM}_{x}_{y}.png').convert('RGB'),
                             dtype=float)
            mosaico[256 * b:256 * (b + 1), 256 * a:256 * (a + 1)] = (
                rgb[:, :, 0] * 256 + rgb[:, :, 1] + rgb[:, :, 2] / 256 - 32768)
    return mosaico


def elevacion(mosaico, lat, lon):
    n = 2 ** ZOOM
    px = (lon + 180) / 360 * n * 256 - TESELAS_X[0] * 256
    s = math.sin(math.radians(lat))
    py = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n * 256 - TESELAS_Y[0] * 256
    return mosaico[int(py), int(px)]


def clasificador_region():
    mosaico = cargar_relieve()
    alto = {}
    for i in range(int((-19 + 90) * 20), int((0.5 + 90) * 20)):
        fila = [j for j in range(int((-82 + 180) * 20), int((-68 + 180) * 20))
                if elevacion(mosaico, i / 20 - 90 + 0.025, j / 20 - 180 + 0.025) >= UMBRAL_SIERRA]
        if fila:
            alto[i] = (min(fila), max(fila), set(fila))
    filas = sorted(alto)

    def region(i, j):
        k = i if i in alto else min(filas, key=lambda f: abs(f - i))
        oeste, este, cumbres = alto[k]
        if i in alto and j in cumbres:
            return 'sierra'
        if j < oeste:
            return 'costa'
        if j > este:
            return 'selva'
        return 'sierra'
    return region


def anillos(geometria):
    poligonos = geometria['coordinates'] if geometria['type'] == 'MultiPolygon' else [geometria['coordinates']]
    return [anillo for poligono in poligonos for anillo in poligono]


def dentro(x, y, anillos_):
    adentro = False
    for anillo in anillos_:
        for (x1, y1), (x2, y2) in zip(anillo, anillo[1:] + anillo[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                adentro = not adentro
    return adentro


def clasificador_departamento():
    datos = json.loads((RAIZ / 'datos' / 'limites' / 'peru_adm1_simplificado.geojson').read_text())
    deps = []
    for f in datos['features']:
        r = anillos(f['geometry'])
        xs = [p[0] for a in r for p in a]
        ys = [p[1] for a in r for p in a]
        deps.append((f['properties']['shapeISO'], min(xs), max(xs), min(ys), max(ys), r))

    def departamento(i, j):
        x, y = j / 20 - 180 + 0.025, i / 20 - 90 + 0.025
        for iso, x0, x1, y0, y1, r in deps:
            if x0 <= x <= x1 and y0 <= y <= y1 and dentro(x, y, r):
                return iso
        cercano = min(deps, key=lambda d: min((p[0] - x) ** 2 + (p[1] - y) ** 2 for a in d[5] for p in a))
        return cercano[0]
    return departamento


def main():
    DERIVADOS.mkdir(parents=True, exist_ok=True)
    dias, procedencia = leer()
    conteos, cortes = rellenar_snpp(dias)
    region, departamento = clasificador_region(), clasificador_departamento()
    celdas = sorted({(i, j) for _, i, j, _, _ in conteos})
    atributos = {(i, j): (departamento(i, j), region(i, j)) for i, j in celdas}

    with (DERIVADOS / 'celdas_mes.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['sensor', 'i', 'j', 'anio', 'mes', 'dias'])
        for clave in sorted(conteos):
            w.writerow([*clave, round(conteos[clave], 3)])
    with (DERIVADOS / 'celdas.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['i', 'j', 'departamento', 'region'])
        for (i, j), (d, r) in atributos.items():
            w.writerow([i, j, d, r])
    (DERIVADOS / 'procedencia.json').write_text(json.dumps(procedencia, ensure_ascii=False, indent=2) + '\n')
    (DERIVADOS / 'cortes.json').write_text(json.dumps(cortes, ensure_ascii=False, indent=2) + '\n')

    total: defaultdict[str, float] = defaultdict(float)
    for (sensor, *_), v in conteos.items():
        total[sensor] += v
    print('celdas distintas:', len(celdas), ' celdas-día por sensor:', {k: round(v) for k, v in total.items()})
    print('días de Suomi NPP rellenados:', len(cortes['snpp_dias_rellenados']), cortes['snpp_meses_rellenados'],
          ' razón SNPP/NOAA-20:', round(cortes['razon_snpp_sobre_noaa20'], 4))
    print('celdas por región:', Counter(r for _, r in atributos.values()))
    print('celdas por departamento:', Counter(d for d, _ in atributos.values()).most_common(5), '...')


if __name__ == '__main__':
    main()
