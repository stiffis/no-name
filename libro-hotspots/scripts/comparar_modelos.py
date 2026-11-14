"""Compara modelos de calibración Aqua -> Suomi NPP con los agregados mensuales de Perú.

Entrada: datos/peru_mensual.csv (lo produce analizar_peru.py).
Selección: validación cruzada dejando un año fuera, solo con 2018-2020.
Evaluación: 2021-2022, que no interviene en la selección. Se añaden dos periodos
de contraste con otra etiqueta de versión MODIS: 2013-2017 y 2023-2024.
Solo biblioteca estándar.
"""
from pathlib import Path
import csv
import json
import math
import statistics as st

ROOT = Path(__file__).resolve().parents[1]
AJUSTE = [2018, 2019, 2020]
PRUEBA = [2021, 2022]
CONTRASTES = {'2013-2017': list(range(2013, 2018)), '2023-2024': [2023, 2024]}
MESES = range(1, 13)
TRIMESTRE = {m: (m - 1) // 3 for m in MESES}


def cargar():
    with (ROOT / 'datos' / 'peru_mensual.csv').open() as f:
        return {(r['sensor'], int(r['anio']), int(r['mes'])): int(r['celdas_dia'])
                for r in csv.DictReader(f)}


def razon_unica(c, anios):
    r = (sum(c['SNPP', y, m] for y in anios for m in MESES)
         / sum(c['Aqua', y, m] for y in anios for m in MESES))
    return {'r': r}, lambda a, m: r * a


def razon_por_grupo(grupo):
    def ajustar(c, anios):
        claves = sorted(set(grupo.values()))
        r = {g: sum(c['SNPP', y, m] for y in anios for m in MESES if grupo[m] == g)
                / sum(c['Aqua', y, m] for y in anios for m in MESES if grupo[m] == g)
             for g in claves}
        return {'r': r}, lambda a, m: r[grupo[m]] * a
    return ajustar


def potencia(c, anios):
    xs = [math.log(c['Aqua', y, m]) for y in anios for m in MESES]
    ys = [math.log(c['SNPP', y, m]) for y in anios for m in MESES]
    mx, my = st.mean(xs), st.mean(ys)
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    alfa = math.exp(my - beta * mx)
    return {'alfa': alfa, 'beta': beta}, lambda a, m: alfa * a ** beta


MODELOS = {
    'unica': razon_unica,
    'trimestral': razon_por_grupo(TRIMESTRE),
    'mensual': razon_por_grupo({m: m for m in MESES}),
    'potencia': potencia,
}


def medir(c, predecir, anios):
    obs = [c['SNPP', y, m] for y in anios for m in MESES]
    est = [predecir(c['Aqua', y, m], m) for y in anios for m in MESES]
    err = [e - o for e, o in zip(est, obs)]
    return {'mae': st.mean(abs(e) for e in err), 'sesgo': st.mean(err),
            'wape': 100 * sum(abs(e) for e in err) / sum(obs)}


def main():
    c = cargar()
    assert all(c['Aqua', y, m] > 0 for y in range(2013, 2025) for m in MESES)
    resultados = {}
    for nombre, ajustar in MODELOS.items():
        abs_err = total = 0
        for fuera in AJUSTE:
            _, predecir = ajustar(c, [y for y in AJUSTE if y != fuera])
            for m in MESES:
                abs_err += abs(predecir(c['Aqua', fuera, m], m) - c['SNPP', fuera, m])
                total += c['SNPP', fuera, m]
        parametros, predecir = ajustar(c, AJUSTE)
        resultados[nombre] = {
            'parametros': parametros,
            'wape_validacion_cruzada': 100 * abs_err / total,
            'prueba_2021_2022': medir(c, predecir, PRUEBA),
            'contrastes': {k: medir(c, predecir, v) for k, v in CONTRASTES.items()},
        }
    elegido = min(resultados, key=lambda n: resultados[n]['wape_validacion_cruzada'])
    salida = {'ajuste': AJUSTE, 'prueba': PRUEBA, 'seleccion': 'validación cruzada por año en 2018-2020',
              'modelo_elegido': elegido, 'modelos': resultados}
    (ROOT / 'datos' / 'peru_modelos.json').write_text(
        json.dumps(salida, ensure_ascii=False, indent=2, default=str) + '\n')

    _, pot = potencia(c, AJUSTE)
    _, uni = razon_unica(c, AJUSTE)
    with (ROOT / 'datos' / 'peru_modelos_prueba.dat').open('w') as f:
        f.write('t etiqueta viirs unica potencia\n')
        t = 0
        for y in PRUEBA:
            for m in MESES:
                t += 1
                a = c['Aqua', y, m]
                f.write(f"{t} {y}-{m:02d} {c['SNPP', y, m]} {uni(a, m):.1f} {pot(a, m):.1f}\n")
    with (ROOT / 'datos' / 'peru_modelos_ajuste.dat').open('w') as f:
        f.write('aqua viirs mes\n')
        for y in AJUSTE:
            for m in MESES:
                f.write(f"{c['Aqua', y, m]} {c['SNPP', y, m]} {m}\n")
    rm = resultados['mensual']['parametros']['r']
    with (ROOT / 'datos' / 'peru_razon_mensual.dat').open('w') as f:
        f.write('mes razon aqua\n')
        for m in MESES:
            f.write(f"{m} {rm[m]:.3f} {sum(c['Aqua', y, m] for y in AJUSTE)}\n")

    def num(v, d):
        return '\\num{' + f'{v:.{d}f}' + '}'
    p = resultados['potencia']
    macros = {
        'PeruPotAlfa': num(p['parametros']['alfa'], 1),
        'PeruPotBeta': num(p['parametros']['beta'], 2),
        'PeruPotWAPE': num(p['prueba_2021_2022']['wape'], 1),
        'PeruPotMAE': num(p['prueba_2021_2022']['mae'], 1),
        'PeruPotSesgo': num(p['prueba_2021_2022']['sesgo'], 1),
        'PeruRazonMin': num(min(rm.values()), 1),
        'PeruRazonMax': num(max(rm.values()), 1),
    }
    for nombre, clave in [('Unica', 'unica'), ('Trim', 'trimestral'), ('Mens', 'mensual'), ('Pot', 'potencia')]:
        r = resultados[clave]
        macros[f'PeruCV{nombre}'] = num(r['wape_validacion_cruzada'], 1)
        macros[f'PeruTest{nombre}'] = num(r['prueba_2021_2022']['wape'], 1)
        macros[f'PeruAntes{nombre}'] = num(r['contrastes']['2013-2017']['wape'], 1)
        macros[f'PeruDespues{nombre}'] = num(r['contrastes']['2023-2024']['wape'], 1)
    (ROOT / 'datos' / 'peru_modelos_macros.tex').write_text(
        '\n'.join('\\newcommand{\\' + k + '}{' + v + '}' for k, v in macros.items()) + '\n')

    print('modelo elegido por validación cruzada:', elegido)
    for nombre, r in resultados.items():
        print(f"{nombre:11s} CV {r['wape_validacion_cruzada']:5.1f}  prueba {r['prueba_2021_2022']['wape']:5.1f}"
              f"  2013-17 {r['contrastes']['2013-2017']['wape']:5.1f}  2023-24 {r['contrastes']['2023-2024']['wape']:5.1f}")


if __name__ == '__main__':
    main()
