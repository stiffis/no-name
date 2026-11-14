"""Segundo eslabón de la cadena: Suomi NPP -> NOAA-20 en Perú.

Suomi NPP dejó de entregar datos nuevos el 2 de noviembre de 2026; NOAA-20 comparte su órbita
de las 13:30. Se calibra con el solape y se prueba en años reservados, con el mismo diseño que
analizar_peru.py y comparar_modelos.py.

Entrada: datos/originales/viirs-jpss1_<año>_Peru.csv y datos/peru_mensual.csv.
Filtros: idénticos a analizar_peru.py (diurno, type=0, confianza n/h, celdas de 0,05 grados,
fecha local UTC-5, sin duplicados idénticos).
Diseño fijado antes de ver resultados: ajuste 2019-2021, prueba 2022-2024. 2018 empieza el
1 de abril y queda fuera. 2025 no tiene Suomi NPP descargado: se convierte, no se valida.
Solo biblioteca estándar.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
import csv
import hashlib
import json
import math
import statistics as st

ROOT = Path(__file__).resolve().parents[1]
ANIOS = range(2018, 2026)
AJUSTE = [2019, 2020, 2021]
PRUEBA = [2022, 2023, 2024]
MESES = range(1, 13)


def leer_noaa20():
    celdas = defaultdict(set)
    focos = Counter()
    procedencia = []
    for anio in ANIOS:
        nombre = f'viirs-jpss1_{anio}_Peru.csv'
        p = ROOT / 'datos' / 'originales' / nombre
        if not p.exists():
            raise FileNotFoundError(f'Falta {nombre}; ejecutar descargar_peru.sh')
        leidas = aceptadas = duplicadas = 0
        versiones, fechas, vistos = Counter(), set(), set()
        with p.open(newline='') as f:
            for fila in csv.DictReader(f):
                leidas += 1
                versiones[fila['version']] += 1
                fechas.add(fila['acq_date'])
                assert fila['satellite'] == 'N20', fila['satellite']
                assert 'NRT' not in fila['version'].upper(), nombre
                if fila['confidence'].lower() not in ('n', 'h'):
                    continue
                if fila['daynight'] != 'D' or fila['type'] != '0':
                    continue
                clave = tuple(fila.values())
                if clave in vistos:
                    duplicadas += 1
                    continue
                vistos.add(clave)
                local = datetime.strptime(fila['acq_date'] + fila['acq_time'].zfill(4),
                                          '%Y-%m-%d%H%M') - timedelta(hours=5)
                assert local.year == anio, (nombre, local)
                i = int(((Decimal(fila['latitude']) + 90) * 20).to_integral_value(rounding=ROUND_FLOOR))
                j = int(((Decimal(fila['longitude']) + 180) * 20).to_integral_value(rounding=ROUND_FLOOR))
                celdas[anio, local.month].add((i, j, local.date()))
                focos[anio, local.month] += 1
                aceptadas += 1
        procedencia.append({
            'archivo': nombre,
            'url': f'https://firms.modaps.eosdis.nasa.gov/data/country/viirs-jpss1/{anio}/{nombre}',
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'bytes': p.stat().st_size,
            'fecha_descarga_utc': datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
            'filas_originales': leidas, 'filas_aceptadas': aceptadas,
            'duplicados_identicos_descartados': duplicadas,
            'versiones': dict(versiones),
            'primera_fecha_deteccion': min(fechas), 'ultima_fecha_deteccion': max(fechas),
        })
    return {k: len(v) for k, v in celdas.items()}, focos, procedencia


def medir(pred, obs):
    err = [p - o for p, o in zip(pred, obs)]
    return {'mae': st.mean(abs(e) for e in err), 'sesgo': st.mean(err),
            'wape': 100 * sum(abs(e) for e in err) / sum(obs)}


def main():
    n20, focos_n20, procedencia = leer_noaa20()
    with (ROOT / 'datos' / 'peru_mensual.csv').open() as f:
        filas = list(csv.DictReader(f))
    snpp = {(int(r['anio']), int(r['mes'])): int(r['celdas_dia']) for r in filas if r['sensor'] == 'SNPP'}
    focos_snpp = {(int(r['anio']), int(r['mes'])): int(r['detecciones']) for r in filas if r['sensor'] == 'SNPP'}

    s_aj = sum(snpp[y, m] for y in AJUSTE for m in MESES)
    n_aj = sum(n20.get((y, m), 0) for y in AJUSTE for m in MESES)
    razon = s_aj / n_aj

    xs = [math.log(n20[y, m]) for y in AJUSTE for m in MESES]
    ys = [math.log(snpp[y, m]) for y in AJUSTE for m in MESES]
    mx, my = st.mean(xs), st.mean(ys)
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    alfa = math.exp(my - beta * mx)

    obs = [snpp[y, m] for y in PRUEBA for m in MESES]
    pred_razon = [razon * n20[y, m] for y in PRUEBA for m in MESES]
    pred_pot = [alfa * n20[y, m] ** beta for y in PRUEBA for m in MESES]
    identidad = [n20[y, m] for y in PRUEBA for m in MESES]

    anuales = []
    for y in ANIOS:
        fila: dict = {'anio': y, 'noaa20': sum(n20.get((y, m), 0) for m in MESES),
                'focos_noaa20': sum(focos_n20.get((y, m), 0) for m in MESES)}
        if any((y, m) in snpp for m in MESES):
            fila['snpp'] = sum(snpp.get((y, m), 0) for m in MESES)
            fila['focos_snpp'] = sum(focos_snpp.get((y, m), 0) for m in MESES)
            fila['razon_snpp_noaa20'] = fila['snpp'] / fila['noaa20']
        fila['noaa20_en_escala_snpp'] = razon * fila['noaa20']
        anuales.append(fila)

    resumen = {
        'eslabon': 'Suomi NPP <- NOAA-20, celdas-día diurnas, Perú',
        'ajuste': AJUSTE, 'prueba': PRUEBA,
        'nota_2018': 'empieza el 2018-04-01; excluido del ajuste y de la prueba',
        'nota_2025': 'sin Suomi NPP descargado; solo conversión',
        'razon_snpp_sobre_noaa20': razon, 'snpp_ajuste': s_aj, 'noaa20_ajuste': n_aj,
        'potencia': {'alfa': alfa, 'beta': beta},
        'prueba_sin_convertir': medir(identidad, obs),
        'prueba_razon': medir(pred_razon, obs),
        'prueba_potencia': medir(pred_pot, obs),
        'anuales': anuales,
    }
    (ROOT / 'datos' / 'peru_noaa20.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'datos' / 'procedencia_noaa20.json').write_text(
        json.dumps(procedencia, ensure_ascii=False, indent=2) + '\n')
    with (ROOT / 'datos' / 'peru_noaa20_mensual.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['anio', 'mes', 'detecciones', 'celdas_dia'])
        for y in ANIOS:
            for m in MESES:
                w.writerow([y, m, focos_n20.get((y, m), 0), n20.get((y, m), 0)])
    with (ROOT / 'datos' / 'peru_noaa20_prueba.dat').open('w') as f:
        f.write('t snpp noaa20 convertido\n')
        for t, (y, m) in enumerate(((y, m) for y in PRUEBA for m in MESES), start=1):
            f.write(f'{t} {snpp[y, m]} {n20[y, m]} {razon * n20[y, m]:.1f}\n')

    def num(v, d):
        return '\\num{' + f'{v:.{d}f}' + '}'
    macros = {
        'NveinteRazon': num(razon, 3),
        'NveinteAjusteSNPP': num(s_aj, 0), 'NveinteAjusteNveinte': num(n_aj, 0),
        'NveinteBeta': num(beta, 2), 'NveinteAlfa': num(alfa, 2),
        'NveinteWapeSin': num(resumen['prueba_sin_convertir']['wape'], 1),
        'NveinteWapeRazon': num(resumen['prueba_razon']['wape'], 1),
        'NveinteWapePot': num(resumen['prueba_potencia']['wape'], 1),
        'NveinteSesgoRazon': num(resumen['prueba_razon']['sesgo'], 1),
        'NveinteTotalVeinticinco': num(anuales[-1]['noaa20'], 0),
        'NveinteConvVeinticinco': num(anuales[-1]['noaa20_en_escala_snpp'], 0),
    }
    (ROOT / 'datos' / 'peru_noaa20_macros.tex').write_text(
        '\n'.join('\\newcommand{\\' + k + '}{' + v + '}' for k, v in macros.items()) + '\n')

    print(f'razón SNPP/N20 = {razon:.4f}   potencia alfa {alfa:.3f} beta {beta:.3f}')
    for k in ('prueba_sin_convertir', 'prueba_razon', 'prueba_potencia'):
        r = resumen[k]
        print(f"{k:22s} WAPE {r['wape']:5.1f}  MAE {r['mae']:7.1f}  sesgo {r['sesgo']:+7.1f}")
    for a in anuales:
        print(a)


if __name__ == '__main__':
    main()
