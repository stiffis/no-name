"""Calibración Aqua -> Suomi NPP por región natural aproximada de Perú.

Relieve: teselas Terrarium (Mapzen/AWS Open Data), zoom 6, guardadas en datos/relieve/.
Regla de región, por celda de 0,05 grados:
  sierra  elevación >= 2000 m, o celda encerrada entre cumbres de su misma latitud;
  costa   por debajo de 2000 m y al oeste de la cordillera;
  selva   por debajo de 2000 m y al este de la cordillera.
Es una aproximación por relieve, no el mapa oficial de regiones naturales.
Los filtros son los de analizar_peru.py; el total nacional se comprueba contra peru_mensual.csv.
Requiere NumPy y Pillow. Descarga solo las teselas que falten.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
import csv
import hashlib
import json
import math
import statistics as st
import subprocess

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RELIEVE = ROOT / 'datos' / 'relieve'
ZOOM = 6
TESELAS_X = range(17, 20)
TESELAS_Y = range(31, 36)
URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
UMBRAL_SIERRA = 2000
ANIOS = range(2013, 2025)
AJUSTE = [2018, 2019, 2020]
PRUEBA = [2021, 2022]
MESES = range(1, 13)
REGIONES = ['costa', 'sierra', 'selva']


def cargar_relieve():
    RELIEVE.mkdir(parents=True, exist_ok=True)
    mosaico = np.zeros((256 * len(TESELAS_Y), 256 * len(TESELAS_X)))
    huellas = []
    for a, x in enumerate(TESELAS_X):
        for b, y in enumerate(TESELAS_Y):
            p = RELIEVE / f'{ZOOM}_{x}_{y}.png'
            if not p.exists():
                subprocess.run(['curl', '-sS', '--fail', '-m', '90', '-o', str(p),
                                URL.format(z=ZOOM, x=x, y=y)], check=True)
            rgb = np.asarray(Image.open(p).convert('RGB'), dtype=float)
            mosaico[256 * b:256 * (b + 1), 256 * a:256 * (a + 1)] = (
                rgb[:, :, 0] * 256 + rgb[:, :, 1] + rgb[:, :, 2] / 256 - 32768)
            huellas.append({'archivo': p.name, 'url': URL.format(z=ZOOM, x=x, y=y),
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    return mosaico, huellas


def elevacion(mosaico, lat, lon):
    n = 2 ** ZOOM
    px = (lon + 180) / 360 * n * 256 - TESELAS_X[0] * 256
    s = math.sin(math.radians(lat))
    py = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n * 256 - TESELAS_Y[0] * 256
    return mosaico[int(py), int(px)]


def clasificar(mosaico):
    lats = range(int((-19 + 90) * 20), int((0.5 + 90) * 20))
    lons = range(int((-82 + 180) * 20), int((-68 + 180) * 20))
    alto = {}
    for i in lats:
        fila = [j for j in lons
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


def leer_celdas_dia(region):
    celdas = defaultdict(set)
    for fuente, sensor in [('modis', 'Aqua'), ('viirs-snpp', 'SNPP')]:
        for anio in ANIOS:
            vistos = set()
            with (ROOT / 'datos' / 'originales' / f'{fuente}_{anio}_Peru.csv').open(newline='') as f:
                for fila in csv.DictReader(f):
                    if fuente == 'modis':
                        if fila['satellite'] not in ('Aqua', 'A') or float(fila['confidence']) < 30:
                            continue
                    elif fila['confidence'].lower() not in ('n', 'h'):
                        continue
                    if fila['daynight'] != 'D' or fila['type'] != '0':
                        continue
                    clave = tuple(fila.values())
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    local = datetime.strptime(fila['acq_date'] + fila['acq_time'].zfill(4),
                                              '%Y-%m-%d%H%M') - timedelta(hours=5)
                    i = int(((Decimal(fila['latitude']) + 90) * 20).to_integral_value(rounding=ROUND_FLOOR))
                    j = int(((Decimal(fila['longitude']) + 180) * 20).to_integral_value(rounding=ROUND_FLOOR))
                    celdas[sensor, region(i, j), anio, local.month].add((i, j, local.date()))
    return {k: len(v) for k, v in celdas.items()}


def ajustar_unica(c, reg):
    r = (sum(c.get(('SNPP', reg, y, m), 0) for y in AJUSTE for m in MESES)
         / sum(c.get(('Aqua', reg, y, m), 0) for y in AJUSTE for m in MESES))
    return {'r': r}, lambda a: r * a


def ajustar_potencia(c, reg):
    pares = [(c.get(('Aqua', reg, y, m), 0), c.get(('SNPP', reg, y, m), 0)) for y in AJUSTE for m in MESES]
    pares = [(a, v) for a, v in pares if a > 0 and v > 0]
    xs, ys = [math.log(a) for a, _ in pares], [math.log(v) for _, v in pares]
    mx, my = st.mean(xs), st.mean(ys)
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    alfa = math.exp(my - beta * mx)
    return {'alfa': alfa, 'beta': beta, 'meses_usados': len(pares)}, lambda a: alfa * a ** beta if a > 0 else 0.0


def main():
    mosaico, huellas = cargar_relieve()
    region = clasificar(mosaico)
    for nombre, lat, lon, esperada in [('Lima', -12.05, -77.04, 'costa'), ('Huancayo', -12.07, -75.21, 'sierra'),
                                       ('Cusco', -13.52, -71.97, 'sierra'), ('Pucallpa', -8.38, -74.55, 'selva'),
                                       ('Iquitos', -3.75, -73.25, 'selva'), ('Piura', -5.19, -80.63, 'costa'),
                                       ('Puerto Maldonado', -12.59, -69.19, 'selva')]:
        obtenida = region(int((lat + 90) * 20), int((lon + 180) * 20))
        assert obtenida == esperada, (nombre, obtenida)
    c = leer_celdas_dia(region)

    with (ROOT / 'datos' / 'peru_mensual.csv').open() as f:
        nacional = {(r['sensor'], int(r['anio']), int(r['mes'])): int(r['celdas_dia']) for r in csv.DictReader(f)}
    for (sensor, anio, mes), total in nacional.items():
        assert sum(c.get((sensor, reg, anio, mes), 0) for reg in REGIONES) == total, (sensor, anio, mes)

    filas = [{'sensor': s, 'region': reg, 'anio': y, 'mes': m, 'celdas_dia': c.get((s, reg, y, m), 0)}
             for s in ('Aqua', 'SNPP') for reg in REGIONES for y in ANIOS for m in MESES]
    with (ROOT / 'datos' / 'peru_regiones_mensual.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)

    resumen = {'regla': f'sierra >= {UMBRAL_SIERRA} m o entre cumbres; costa al oeste; selva al este',
               'relieve': huellas, 'ajuste': AJUSTE, 'prueba': PRUEBA, 'regiones': {}}
    obs_total = defaultdict(float)
    est_total = {'unica': defaultdict(float), 'potencia': defaultdict(float)}
    for reg in REGIONES:
        pu, unica = ajustar_unica(c, reg)
        pp, pot = ajustar_potencia(c, reg)
        info = {'aqua_ajuste': sum(c.get(('Aqua', reg, y, m), 0) for y in AJUSTE for m in MESES),
                'viirs_ajuste': sum(c.get(('SNPP', reg, y, m), 0) for y in AJUSTE for m in MESES),
                'unica': pu, 'potencia': pp}
        for nombre, modelo in [('unica', unica), ('potencia', pot)]:
            err, obs = [], []
            for y in PRUEBA:
                for m in MESES:
                    o = c.get(('SNPP', reg, y, m), 0)
                    e = modelo(c.get(('Aqua', reg, y, m), 0))
                    err.append(e - o)
                    obs.append(o)
                    est_total[nombre][y, m] += e
                    if nombre == 'unica':
                        obs_total[y, m] += o
            info[f'wape_{nombre}'] = 100 * sum(abs(e) for e in err) / sum(obs)
            info[f'sesgo_{nombre}'] = st.mean(err)
        resumen['regiones'][reg] = info
    total_obs = sum(obs_total.values())
    resumen['suma_regional'] = {n: 100 * sum(abs(est_total[n][k] - obs_total[k]) for k in obs_total) / total_obs
                                for n in est_total}
    (ROOT / 'datos' / 'peru_regiones.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + '\n')

    def num(v, d):
        return '\\num{' + f'{v:.{d}f}' + '}'
    macros = {}
    for reg in REGIONES:
        r = resumen['regiones'][reg]
        t = reg.capitalize()
        macros[f'Reg{t}Aqua'] = num(r['aqua_ajuste'], 0)
        macros[f'Reg{t}VIIRS'] = num(r['viirs_ajuste'], 0)
        macros[f'Reg{t}Razon'] = num(r['unica']['r'], 2)
        macros[f'Reg{t}Alfa'] = num(r['potencia']['alfa'], 1)
        macros[f'Reg{t}Beta'] = num(r['potencia']['beta'], 2)
        macros[f'Reg{t}WapeUnica'] = num(r['wape_unica'], 1)
        macros[f'Reg{t}WapePot'] = num(r['wape_potencia'], 1)
    macros['RegSumaUnica'] = num(resumen['suma_regional']['unica'], 1)
    macros['RegSumaPot'] = num(resumen['suma_regional']['potencia'], 1)
    (ROOT / 'datos' / 'peru_regiones_macros.tex').write_text(
        '\n'.join('\\newcommand{\\' + k + '}{' + v + '}' for k, v in macros.items()) + '\n')

    for reg in REGIONES:
        r = resumen['regiones'][reg]
        print(f"{reg:7s} Aqua {r['aqua_ajuste']:6d} VIIRS {r['viirs_ajuste']:6d} razón {r['unica']['r']:5.2f} "
              f"alfa {r['potencia']['alfa']:6.1f} beta {r['potencia']['beta']:.2f} "
              f"WAPE única {r['wape_unica']:5.1f} potencia {r['wape_potencia']:5.1f}")
    print('suma de regiones frente al total nacional, WAPE:', resumen['suma_regional'])


if __name__ == '__main__':
    main()
