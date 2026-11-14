"""Paso 3: serie armonizada por área y archivos JSON para la web.

Escala común: celdas-día diurnas de Suomi NPP.
  2003-01 a 2012-01: Aqua convertido con el modelo elegido en modelo.py, con banda de incertidumbre.
  2012-02 a 2025-12: Suomi NPP observado (sus datos empiezan el 20 de enero de 2012); los días de
                     corte se rellenan con NOAA-20 (celdas.py) y el mes queda marcado.
Áreas: país, tres regiones naturales aproximadas y 26 departamentos, todas sumas de trozos.
Bandas: percentiles 10 y 90 del cociente observado/predicho fuera de muestra (validación cruzada
por año en 2013-2017), por nivel de área y por tamaño de la predicción.
Referencia de lo normal: 2003-2024, mediana y percentiles 10 y 90 de cada mes.
Salidas en web/datos/: areas.json, series.json, metodo.json, departamentos.geojson.
"""
from pathlib import Path
from collections import defaultdict
import bisect
import json
import shutil
import statistics as st

import modelo as m

RAIZ = Path(__file__).resolve().parents[1]
WEB = RAIZ / 'web' / 'datos'
INICIO, FIN = (2003, 1), (2025, 12)
CORTE_SNPP = (2012, 2)
REFERENCIA = range(2003, 2025)
NOMBRES_REGION = {'costa': 'Costa', 'sierra': 'Sierra', 'selva': 'Selva'}
LIMITES_TAMANO = [10, 50, 200, 1000]


def meses():
    y, mes = INICIO
    while (y, mes) <= FIN:
        yield y, mes
        y, mes = (y + 1, 1) if mes == 12 else (y, mes + 1)


def areas_de(dep, reg):
    return ['PE', f'R-{reg}', dep]


def percentil(valores, p):
    s = sorted(valores)
    h = (len(s) - 1) * p
    i = int(h)
    return s[i] + (h - i) * (s[min(i + 1, len(s) - 1)] - s[i])


def nivel(area):
    return 'pais' if area == 'PE' else ('region' if area.startswith('R-') else 'departamento')


def por_area(predecir, datos):
    pred, obs = defaultdict(float), defaultdict(float)
    for (dep, reg, y, mes), (a, v) in datos.items():
        p = predecir(dep, reg, mes, a)
        for area in areas_de(dep, reg):
            pred[area, y, mes] += p
            obs[area, y, mes] += v
    return pred, obs


def bandas(calibracion, ajustar):
    pred, obs = defaultdict(float), defaultdict(float)
    for fuera in m.CALIBRACION:
        _, predecir = ajustar({k: v for k, v in calibracion.items() if k[2] != fuera})
        p, o = por_area(predecir, {k: v for k, v in calibracion.items() if k[2] == fuera})
        pred.update(p)
        obs.update(o)
    grupos = defaultdict(list)
    for k, p in pred.items():
        if p > 0:
            grupos[nivel(k[0]), bisect.bisect(LIMITES_TAMANO, p)].append(obs[k] / p)
    tabla = {}
    for (niv, tam), cocientes in grupos.items():
        if len(cocientes) >= 20:
            tabla[niv, tam] = (percentil(cocientes, 0.1), percentil(cocientes, 0.9), len(cocientes))
    return tabla


def banda(tabla, area, p):
    niv, tam = nivel(area), bisect.bisect(LIMITES_TAMANO, p)
    while (niv, tam) not in tabla and tam > 0:
        tam -= 1
    lo, hi, _ = tabla.get((niv, tam), (0.0, 3.0, 0))
    return round(p * lo, 1), round(p * hi, 1)


def main():
    conteo, trozos = m.cargar()
    info = json.loads((m.DERIVADOS / 'modelo.json').read_text())
    elegido = info['elegido']
    ajustar = m.CANDIDATOS[elegido]
    excluidos = m.meses_excluidos()
    calibracion = m.pares(conteo, trozos, m.CALIBRACION, excluidos)
    _, predecir = ajustar(calibracion)
    tabla = bandas(calibracion, ajustar)
    cortes = json.loads((m.DERIVADOS / 'cortes.json').read_text())
    rellenados = {(int(t[:4]), int(t[5:])) for t in cortes['snpp_meses_rellenados']}

    pred_p, obs_p = por_area(predecir, m.pares(conteo, trozos, m.PRUEBA, excluidos))
    cobertura = defaultdict(lambda: [0, 0])
    for k, p in pred_p.items():
        lo, hi = banda(tabla, k[0], p)
        cobertura[nivel(k[0])][0] += lo <= obs_p[k] <= hi
        cobertura[nivel(k[0])][1] += 1

    aqua, snpp, n20, conv = (defaultdict(float) for _ in range(4))
    for dep, reg in trozos:
        for y, mes in meses():
            a = conteo.get(('Aqua', dep, reg, y, mes), 0)
            p = predecir(dep, reg, mes, a)
            for area in areas_de(dep, reg):
                aqua[area, y, mes] += a
                snpp[area, y, mes] += conteo.get((m.OBJETIVO, dep, reg, y, mes), 0)
                n20[area, y, mes] += conteo.get(('NOAA20', dep, reg, y, mes), 0)
                conv[area, y, mes] += p

    geo = json.loads((RAIZ / 'datos' / 'limites' / 'peru_adm1_simplificado.geojson').read_text())
    nombres = {f['properties']['shapeISO']: f['properties']['shapeName'] for f in geo['features']}
    nombres['PE-LMA*'] = 'Lima Metropolitana'
    nombres['PE-LIM'] = 'Lima (provincias)'
    nombres['PE-CAL'] = 'Callao'
    lista = [{'id': 'PE', 'nombre': 'Perú', 'nivel': 'pais'}]
    lista += [{'id': f'R-{r}', 'nombre': NOMBRES_REGION[r], 'nivel': 'region'} for r in m.REGIONES]
    lista += sorted(({'id': d, 'nombre': nombres[d], 'nivel': 'departamento'} for d in nombres),
                    key=lambda x: x['nombre'])
    presentes = {a for a, _, _ in conv}

    series = {}
    for area in (x['id'] for x in lista):
        filas = []
        for y, mes in meses():
            k = (area, y, mes)
            if (y, mes) < CORTE_SNPP:
                valor, fuente = conv[k], 'aqua_convertido'
                lo, hi = banda(tabla, area, conv[k])
            else:
                fuente = 'snpp_rellenado' if (y, mes) in rellenados else 'snpp'
                valor, lo, hi = snpp[k], round(snpp[k], 1), round(snpp[k], 1)
            filas.append({'anio': y, 'mes': mes, 'valor': round(valor, 1), 'fuente': fuente,
                          'bajo': lo, 'alto': hi, 'aqua': int(aqua[k]),
                          'aqua_convertido': round(conv[k], 1),
                          'aqua_fiable': (y, mes) not in excluidos and y <= 2021,
                          'snpp': round(snpp[k], 1) if (y, mes) >= (2012, 1) else None,
                          'noaa20': int(n20[k]) if y >= 2018 else None})
        normal = []
        for mes in m.MESES:
            hist = [f['valor'] for f in filas if f['mes'] == mes and f['anio'] in REFERENCIA]
            normal.append({'mes': mes, 'mediana': round(st.median(hist), 1),
                           'p10': round(percentil(hist, 0.1), 1), 'p90': round(percentil(hist, 0.9), 1)})
        series[area] = {'meses': filas, 'normal': normal, 'tiene_datos': area in presentes}

    metodo = {
        'escala': 'celdas-día diurnas de Suomi NPP (celdas de 0,05 grados, fecha local UTC-5)',
        'tramos': {'aqua_convertido': '2003-01 a 2012-01', 'snpp': '2012-02 a 2025-12',
                   'snpp_rellenado': 'meses con días de corte de Suomi NPP rellenados con NOAA-20'},
        'cortes': cortes,
        'cobertura_banda_en_prueba_pct': {niv: round(100 * a / b, 1) for niv, (a, b) in cobertura.items()},
        'modelo_elegido': elegido,
        'parametros': info['candidatos'][elegido]['parametros'],
        'comparacion_modelos': {n: {'cv_wape_departamento': round(r['cv_wape_departamento'], 1),
                                    'prueba_wape_departamento': round(r['prueba_2018_2022']['wape_departamento'], 1),
                                    'prueba_wape_pais': round(r['prueba_2018_2022']['wape_pais'], 1),
                                    'prueba_sesgo_pais': round(r['prueba_2018_2022']['sesgo_pais_pct'], 1)}
                                for n, r in info['candidatos'].items()},
        'diseno': info['diseno'],
        'bandas': {f'{niv}|tamano>{([0] + LIMITES_TAMANO)[t]}': {'p10': round(lo, 3), 'p90': round(hi, 3), 'n': n}
                   for (niv, t), (lo, hi, n) in sorted(tabla.items())},
        'referencia_normal': [REFERENCIA[0], REFERENCIA[-1]],
        'filtros': 'diurno; type=0; Aqua con confianza >= 30; VIIRS nominal o alta; sin filas repetidas',
        'regiones': 'aproximación por relieve (sierra >= 2000 m o entre cumbres); no es el mapa oficial',
        'fuentes': ['NASA FIRMS, archivos anuales por país (MODIS C6.x y VIIRS 375 m C2)',
                    'geoBoundaries gbOpen PER ADM1 (dominio público)',
                    'Teselas de elevación Terrarium (AWS Open Data)'],
    }
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / 'areas.json').write_text(json.dumps(lista, ensure_ascii=False) + '\n')
    (WEB / 'series.json').write_text(json.dumps(series, ensure_ascii=False, separators=(',', ':')) + '\n')
    (WEB / 'metodo.json').write_text(json.dumps(metodo, ensure_ascii=False, indent=2) + '\n')
    shutil.copyfile(RAIZ / 'datos' / 'limites' / 'peru_adm1_simplificado.geojson', WEB / 'departamentos.geojson')

    pe = series['PE']['meses']
    for y in (2005, 2010, 2012, 2013, 2024):
        print(y, round(sum(f['valor'] for f in pe if f['anio'] == y)))
    print('bandas:', {k: (round(v[0], 2), round(v[1], 2), v[2]) for k, v in sorted(tabla.items())})
    print('cobertura de la banda P10-P90 en la prueba (esperado ~80 %):', metodo['cobertura_banda_en_prueba_pct'])
    print('tamaño series.json:', (WEB / 'series.json').stat().st_size // 1024, 'KiB')


if __name__ == '__main__':
    main()
