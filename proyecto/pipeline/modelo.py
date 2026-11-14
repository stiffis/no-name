"""Paso 2: elegir y ajustar la conversión Aqua -> VIIRS (Suomi NPP con cortes rellenados).

Unidad de ajuste: trozo departamento x región natural, por mes. Departamentos, regiones y país
se obtienen sumando trozos ya convertidos, de modo que todos los niveles son coherentes.

Diseño:
  calibración 2013-2017 (etiqueta MODIS 6.2, la misma de 2003-2011, y antes de la deriva de Aqua);
  selección por validación cruzada dejando fuera un año dentro de 2013-2017;
  prueba independiente 2018-2022; contraste 2023-2025 (Aqua ya deriva: se espera peor ajuste).
  Los meses con corte documentado de Aqua (cortes.json) se excluyen de todo.

Candidatos, con V el conteo de VIIRS y A el de Aqua en un trozo y mes:
  razón          V = r A                      (r único, por región o por región y temporada)
  log-lineal     log(1+V) = a + b log(1+A)    con corrección de retransformación de Duan
  Poisson        log E[V] = a + b log(1+A)    por máxima verosimilitud
  Poisson+trozo  E[V] = f_t exp(a + b log(1+A)), con f_t = (V_t + k)/(P_t + k): factor propio de
                 cada trozo, contraído hacia 1 con k pseudo-observaciones
Temporada: julio-octubre frente al resto. Los log-lineales se conservan para documentar por qué
fallan con conteos llenos de ceros: la corrección de Duan se infla y las sumas se sesgan.
Salida: datos/derivados/modelo.json
"""
from pathlib import Path
from collections import defaultdict
import csv
import json
import math
import statistics as st

RAIZ = Path(__file__).resolve().parents[1]
DERIVADOS = RAIZ / 'datos' / 'derivados'
CALIBRACION = [2013, 2014, 2015, 2016, 2017]
PRUEBA = [2018, 2019, 2020, 2021, 2022]
CONTRASTE = [2023, 2024, 2025]
MESES = range(1, 13)
REGIONES = ['costa', 'sierra', 'selva']
OBJETIVO = 'VIIRS'


def temporada(mes):
    return 'seca' if mes in (7, 8, 9, 10) else 'resto'


def cargar():
    atributos = {}
    with (DERIVADOS / 'celdas.csv').open() as f:
        for r in csv.DictReader(f):
            atributos[int(r['i']), int(r['j'])] = (r['departamento'], r['region'])
    conteo = defaultdict(float)
    with (DERIVADOS / 'celdas_mes.csv').open() as f:
        for r in csv.DictReader(f):
            dep, reg = atributos[int(r['i']), int(r['j'])]
            conteo[r['sensor'], dep, reg, int(r['anio']), int(r['mes'])] += float(r['dias'])
    trozos = sorted({(d, r) for d, r in atributos.values()})
    return conteo, trozos


def meses_excluidos():
    cortes = json.loads((DERIVADOS / 'cortes.json').read_text())
    return frozenset((int(t[:4]), int(t[5:])) for t in cortes['aqua_meses_excluidos'])


def razon(grupo):
    def ajustar(datos):
        num, den = defaultdict(float), defaultdict(float)
        for (_, reg, _, m), (a, v) in datos.items():
            num[grupo(reg, m)] += v
            den[grupo(reg, m)] += a
        r = {k: num[k] / den[k] for k in num if den[k] > 0}
        total = sum(num.values()) / sum(den.values())
        return {'r': {str(k): v for k, v in r.items()}}, lambda dep, reg, m, a: r.get(grupo(reg, m), total) * a
    return ajustar


def log_lineal(grupo):
    def ajustar(datos):
        puntos = defaultdict(list)
        for (_, reg, _, m), (a, v) in datos.items():
            puntos[grupo(reg, m)].append((math.log1p(a), math.log1p(v)))
        params = {}
        for k, p in puntos.items():
            xs, ys = [x for x, _ in p], [y for _, y in p]
            mx, my = st.mean(xs), st.mean(ys)
            b = sum((x - mx) * (y - my) for x, y in p) / sum((x - mx) ** 2 for x in xs)
            a = my - b * mx
            duan = st.mean(math.exp(y - (a + b * x)) for x, y in p)
            params[k] = (a, b, duan)

        def predecir(dep, reg, m, conteo_a):
            a, b, duan = params[grupo(reg, m)]
            return max(0.0, math.exp(a + b * math.log1p(conteo_a)) * duan - 1)
        return {'params': {str(k): {'a': a, 'b': b, 'duan': d} for k, (a, b, d) in params.items()}}, predecir
    return ajustar


def poisson(grupo):
    def ajustar(datos):
        puntos = defaultdict(list)
        for (_, reg, _, m), (a, v) in datos.items():
            puntos[grupo(reg, m)].append((math.log1p(a), v))
        params = {}
        for k, p in puntos.items():
            a, b = math.log(max(st.mean(v for _, v in p), 1e-9)), 0.0
            for _ in range(100):
                ga = gb = haa = hab = hbb = 0.0
                for x, v in p:
                    mu = math.exp(a + b * x)
                    ga += v - mu
                    gb += (v - mu) * x
                    haa += mu
                    hab += mu * x
                    hbb += mu * x * x
                det = haa * hbb - hab * hab
                da = (hbb * ga - hab * gb) / det
                db = (haa * gb - hab * ga) / det
                a, b = a + da, b + db
                if abs(da) + abs(db) < 1e-12:
                    break
            params[k] = (a, b)

        def predecir(dep, reg, m, conteo_a):
            a, b = params[grupo(reg, m)]
            return math.exp(a + b * math.log1p(conteo_a))
        return {'params': {str(k): {'a': a, 'b': b} for k, (a, b) in params.items()}}, predecir
    return ajustar


def con_factor_de_trozo(base, k):
    def ajustar(datos):
        params, predecir_base = base(datos)
        obs, pred = defaultdict(float), defaultdict(float)
        for (dep, reg, _, m), (a, v) in datos.items():
            obs[dep, reg] += v
            pred[dep, reg] += predecir_base(dep, reg, m, a)
        factor = {t: (obs[t] + k) / (pred[t] + k) for t in pred}
        params = dict(params, k=k, factor={f'{d}|{r}': f for (d, r), f in factor.items()})
        return params, lambda dep, reg, m, a: factor.get((dep, reg), 1.0) * predecir_base(dep, reg, m, a)
    return ajustar


CANDIDATOS = {
    'razon_unica': razon(lambda reg, m: 'todo'),
    'razon_region': razon(lambda reg, m: reg),
    'razon_region_temporada': razon(lambda reg, m: (reg, temporada(m))),
    'loglineal_unica': log_lineal(lambda reg, m: 'todo'),
    'loglineal_region': log_lineal(lambda reg, m: reg),
    'loglineal_region_temporada': log_lineal(lambda reg, m: (reg, temporada(m))),
    'poisson_unica': poisson(lambda reg, m: 'todo'),
    'poisson_region': poisson(lambda reg, m: reg),
    'poisson_region_temporada': poisson(lambda reg, m: (reg, temporada(m))),
    'poisson_region_trozo_k50': con_factor_de_trozo(poisson(lambda reg, m: reg), 50),
    'poisson_region_trozo_k200': con_factor_de_trozo(poisson(lambda reg, m: reg), 200),
    'poisson_region_temporada_trozo_k50': con_factor_de_trozo(poisson(lambda reg, m: (reg, temporada(m))), 50),
    'poisson_region_temporada_trozo_k200': con_factor_de_trozo(poisson(lambda reg, m: (reg, temporada(m))), 200),
}


def pares(conteo, trozos, anios, excluidos=frozenset()):
    return {(dep, reg, y, m): (conteo.get(('Aqua', dep, reg, y, m), 0), conteo.get((OBJETIVO, dep, reg, y, m), 0))
            for dep, reg in trozos for y in anios for m in MESES if (y, m) not in excluidos}


def wape(errores, observados):
    return 100 * sum(abs(e) for e in errores) / sum(observados)


def evaluar(predecir, datos):
    por_dep, por_pais = defaultdict(lambda: [0.0, 0.0]), defaultdict(lambda: [0.0, 0.0])
    e_trozo, o_trozo = [], []
    for (dep, reg, y, m), (a, v) in datos.items():
        p = predecir(dep, reg, m, a)
        e_trozo.append(p - v)
        o_trozo.append(v)
        por_dep[dep, y, m][0] += p
        por_dep[dep, y, m][1] += v
        por_pais[y, m][0] += p
        por_pais[y, m][1] += v
    return {
        'wape_trozo': wape(e_trozo, o_trozo),
        'wape_departamento': wape([p - v for p, v in por_dep.values()], [v for _, v in por_dep.values()]),
        'wape_pais': wape([p - v for p, v in por_pais.values()], [v for _, v in por_pais.values()]),
        'sesgo_pais_pct': 100 * sum(p - v for p, v in por_pais.values()) / sum(v for _, v in por_pais.values()),
    }


def validacion_cruzada(ajustar, calibracion):
    pred, obs = defaultdict(float), defaultdict(float)
    for fuera in CALIBRACION:
        _, predecir = ajustar({k: v for k, v in calibracion.items() if k[2] != fuera})
        for (dep, reg, y, m), (a, v) in calibracion.items():
            if y == fuera:
                pred[dep, y, m] += predecir(dep, reg, m, a)
                obs[dep, y, m] += v
    return pred, obs


def main():
    conteo, trozos = cargar()
    fuera = meses_excluidos()
    calibracion = pares(conteo, trozos, CALIBRACION, fuera)
    resultados = {}
    for nombre, ajustar in CANDIDATOS.items():
        pred, obs = validacion_cruzada(ajustar, calibracion)
        params, predecir = ajustar(calibracion)
        resultados[nombre] = {
            'cv_wape_departamento': wape([pred[k] - obs[k] for k in obs], list(obs.values())),
            'parametros': params,
            'prueba_2018_2022': evaluar(predecir, pares(conteo, trozos, PRUEBA, fuera)),
            'prueba_2018_2022_sin_excluir_cortes': evaluar(predecir, pares(conteo, trozos, PRUEBA)),
            'contraste_2023_2025': evaluar(predecir, pares(conteo, trozos, CONTRASTE, fuera)),
        }
    elegido = min(resultados, key=lambda n: resultados[n]['cv_wape_departamento'])
    salida = {'diseno': {'calibracion': CALIBRACION, 'prueba': PRUEBA, 'contraste': CONTRASTE,
                         'meses_excluidos_por_corte_de_aqua': sorted(f'{y}-{m:02d}' for y, m in fuera),
                         'seleccion': 'validación cruzada dejando fuera un año, WAPE departamento-mes',
                         'unidad': 'departamento x región natural, mensual',
                         'objetivo': 'Suomi NPP con días de corte rellenados con NOAA-20'},
              'elegido': elegido, 'trozos': [list(t) for t in trozos], 'candidatos': resultados}
    (DERIVADOS / 'modelo.json').write_text(json.dumps(salida, ensure_ascii=False, indent=2) + '\n')

    print(f'{"modelo":38s} {"CV dep":>7s} | prueba: {"dep":>6s} {"país":>6s} {"sesgo":>6s} | contraste: {"dep":>6s} {"país":>6s} {"sesgo":>6s}')
    for n, r in resultados.items():
        p, c = r['prueba_2018_2022'], r['contraste_2023_2025']
        print(f'{n:38s} {r["cv_wape_departamento"]:7.1f} | {p["wape_departamento"]:14.1f} {p["wape_pais"]:6.1f} '
              f'{p["sesgo_pais_pct"]:+6.1f} | {c["wape_departamento"]:17.1f} {c["wape_pais"]:6.1f} {c["sesgo_pais_pct"]:+6.1f}')
    print('elegido por validación cruzada:', elegido)


if __name__ == '__main__':
    main()
