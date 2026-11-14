"""Caso real FIRMS, Perú 2013-2024. Reproduce las tablas del libro sin paquetes externos.

Entrada: CSV anuales originales de firms.modaps.eosdis.nasa.gov/data/country/.
Análisis: Aqua MODIS y Suomi NPP VIIRS por separado, solo D, type=0,
confianza MODIS>=30 o VIIRS n/h. Celdas de 0.05 grados; fecha local UTC-5.
No se estima área quemada ni cobertura despejada a partir de puntos positivos.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
import csv
import hashlib
import json
import statistics as st
import time

ROOT = Path(__file__).resolve().parents[1]
YEARS = range(2013, 2025)
BASE = range(2013, 2024)
TRAIN = range(2018, 2021)
TEST = range(2021, 2023)


def q(values, p):
    s = sorted(values)
    h = (len(s)-1)*p
    i = int(h)
    return s[i] + (h-i)*(s[min(i+1, len(s)-1)]-s[i])


def write_csv(name, fields, rows):
    with (ROOT/'datos'/name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    start = time.perf_counter()
    provenance, tables = [], []
    daily = defaultdict(set)
    for source, sensor in [('modis','Aqua'), ('viirs-snpp','SNPP')]:
        for year in YEARS:
            name = f'{source}_{year}_Peru.csv'
            p = ROOT/'datos'/'originales'/name
            if not p.exists():
                raise FileNotFoundError(f'Falta {name}; ejecutar descargar_peru.sh')
            versions, sats = Counter(), Counter()
            read = accepted = duplicate = 0
            dates, seen = set(), set()
            raw_count = Counter()
            with p.open(newline='') as f:
                reader = csv.DictReader(f)
                required = {'latitude','longitude','acq_date','acq_time','confidence',
                            'daynight','satellite','type','version'}
                assert required <= set(reader.fieldnames), (name, reader.fieldnames)
                for row in reader:
                    read += 1
                    assert None not in row and all(v is not None for v in row.values()), name
                    versions[row['version']] += 1
                    sats[row['satellite']] += 1
                    dates.add(row['acq_date'])
                    if source == 'modis':
                        if row['satellite'] not in ('Aqua','A') or float(row['confidence']) < 30:
                            continue
                        assert row['version'] in ('6.2','6.03','61.03'), row['version']
                        if year in list(TRAIN)+list(TEST):
                            assert row['version'] == '6.03', row['version']
                    else:
                        if row['confidence'].lower() not in ('n','h'):
                            continue
                        assert row['satellite'] in ('N','Suomi NPP','SNPP'), row['satellite']
                        assert row['version'].startswith('2'), row['version']
                    assert 'NRT' not in row['version'].upper(), name
                    if row['daynight'] != 'D' or row['type'] != '0':
                        continue
                    rawkey = tuple(row.values())
                    if rawkey in seen:
                        duplicate += 1
                        continue
                    seen.add(rawkey)
                    hhmm = row['acq_time'].zfill(4)
                    when = datetime.strptime(row['acq_date']+hhmm, '%Y-%m-%d%H%M')
                    local = when - timedelta(hours=5)
                    assert local.year == year, (name, local)
                    lat, lon = Decimal(row['latitude']), Decimal(row['longitude'])
                    assert -90 <= lat <= 90 and -180 <= lon <= 180
                    i = int(((lat+90)*20).to_integral_value(rounding=ROUND_FLOOR))
                    j = int(((lon+180)*20).to_integral_value(rounding=ROUND_FLOOR))
                    key = (sensor, year, local.month)
                    daily[key].add((i,j,local.date().isoformat()))
                    raw_count[local.month] += 1
                    accepted += 1
            assert read > 0 and len(dates) > 50, (name, read, len(dates))
            provenance.append({
                'archivo': name,
                'url': f'https://firms.modaps.eosdis.nasa.gov/data/country/{source}/{year}/{name}',
                'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                'bytes': p.stat().st_size,
                'fecha_descarga_utc': datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                'filas_originales': read, 'filas_aceptadas': accepted,
                'duplicados_identicos_descartados': duplicate,
                'versiones': dict(versions), 'satelites': dict(sats),
                'primera_fecha_deteccion': min(dates), 'ultima_fecha_deteccion': max(dates),
                'dias_con_alguna_deteccion_archivo': len(dates),
            })
            for month in range(1,13):
                tables.append({'sensor':sensor, 'anio':year, 'mes':month,
                               'detecciones':raw_count[month],
                               'celdas_dia':len(daily[(sensor,year,month)])})
    counts = {(r['sensor'],r['anio'],r['mes']):r['celdas_dia'] for r in tables}
    points = {(r['sensor'],r['anio'],r['mes']):r['detecciones'] for r in tables}
    annual = lambda sensor, year: sum(counts[(sensor,year,m)] for m in range(1,13))
    x = sum(annual('Aqua',y) for y in TRAIN)
    v = sum(annual('SNPP',y) for y in TRAIN)
    ratio = v/x
    predictions = []
    for year in TEST:
        for month in range(1,13):
            obs = counts[('SNPP',year,month)]
            pred = ratio*counts[('Aqua',year,month)]
            predictions.append({'anio':year,'mes':month,'viirs':obs,
                                'aqua_convertido':pred,'error':pred-obs})
    errors = [r['error'] for r in predictions]
    mae = st.mean(abs(e) for e in errors)
    bias = st.mean(errors)
    wape = sum(abs(e) for e in errors)/sum(r['viirs'] for r in predictions)*100
    climatology = []
    for month in range(1,13):
        values = [counts[('SNPP',y,month)] for y in BASE]
        median = st.median(values)
        current = counts[('SNPP',2024,month)]
        fraction = st.mean(counts[('SNPP',y,month)]/annual('SNPP',y) for y in BASE)*100
        climatology.append({'mes':month,'q10':q(values,.1),'mediana':median,
                            'q90':q(values,.9),'actual2024':current,
                            'fraccion_anual_media':fraction,
                            'anomalia_porcentual':(current/median-1)*100 if median else None})
    cumulative = 0
    for c in climatology:
        cumulative += c['fraccion_anual_media']
        c['acumulado'] = cumulative
    assert math_close(cumulative,100)
    heatmap = [{'mes':m,'fila':y-2013,'anio':y,'actividad':counts[('SNPP',y,m)]}
               for y in YEARS for m in range(1,13)]
    yearrows = [{'anio':y,'aqua':annual('Aqua',y),'viirs':annual('SNPP',y),
                 'razon':annual('SNPP',y)/annual('Aqua',y),
                 'aqua_convertido':ratio*annual('Aqua',y),
                 'focos_aqua':sum(points[('Aqua',y,m)] for m in range(1,13)),
                 'focos_viirs':sum(points[('SNPP',y,m)] for m in range(1,13))}
                for y in YEARS]
    summary = {
        'caso':'Perú, archivos nacionales de FIRMS; no equivale a un censo de incendios',
        'fecha_calculo_utc': datetime.now(timezone.utc).isoformat(),
        'periodo':[2013,2024], 'referencia_estacional':[2013,2023],
        'entrenamiento':[2018,2020], 'prueba':[2021,2022],
        'filtros':'Aqua / SNPP; D; type=0; confianza >=30 / n,h; sin duplicados idénticos',
        'rejilla_grados':.05, 'zona_horaria':'UTC-05:00',
        'total_filas_originales':sum(r['filas_originales'] for r in provenance),
        'total_filas_seleccionadas':sum(r['filas_aceptadas'] for r in provenance),
        'sum_aqua_ajuste':x, 'sum_viirs_ajuste':v,'razon_ajuste':ratio,
        'mae_prueba':mae,'sesgo_prueba':bias,'wape_prueba_porcentaje':wape,
        'anuales':yearrows,'climatologia':climatology,
        'limitaciones':['Sin máscara de observaciones despejadas: ninguna corrección de cobertura.',
                        'CSV nacional: se conserva la selección espacial de FIRMS.',
                        'La calibración es una línea base didáctica, no un producto NASA validado.',
                        'Prueba temporal elegida antes de mirar resultados; no se optimiza con ella.'],
        'segundos_procesamiento':time.perf_counter()-start,
    }
    for filename,data in [('procedencia_peru.json',provenance),('resultados_peru.json',summary)]:
        (ROOT/'datos'/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    write_csv('peru_mensual.csv',list(tables[0]),tables)
    write_csv('peru_calendario.csv',list(heatmap[0]),heatmap)
    write_csv('peru_climatologia.csv',list(climatology[0]),climatology)
    write_csv('peru_anual.csv',list(yearrows[0]),yearrows)
    write_csv('peru_validacion.csv',list(predictions[0]),predictions)
    macros = {'PeruFilas':summary['total_filas_originales'],
              'PeruAceptadas':summary['total_filas_seleccionadas'],
              'PeruRatio':round(ratio,3), 'PeruMAE':round(mae,1),
              'PeruSesgo':round(bias,1),'PeruWAPE':round(wape,1),
              'PeruAjusteAqua':x,'PeruAjusteVIIRS':v,
              'PeruAgostoMediana':climatology[7]['mediana'],
              'PeruAgostoActual':climatology[7]['actual2024'],
              'PeruAgostoAnomalia':round(climatology[7]['anomalia_porcentual'],1),
              'PeruSeptMediana':climatology[8]['mediana'],
              'PeruSeptActual':climatology[8]['actual2024'],
              'PeruSeptQnoventa':climatology[8]['q90'],
              'PeruSeptAnomalia':round(climatology[8]['anomalia_porcentual'],1),
              'PeruASO':round(sum(c['fraccion_anual_media'] for c in climatology[7:10]),1)}
    (ROOT/'datos'/'peru_macros.tex').write_text('\n'.join(
        '\\newcommand{\\'+name+'}{\\num{'+str(value)+'}}'
        for name,value in macros.items())+'\n')
    (ROOT/'datos'/'peru_tabla_mensual.tex').write_text('\n'.join(
        f"{c['mes']} & \\num{{{c['mediana']}}} & \\num{{{c['q90']}}} & \\num{{{c['actual2024']}}} \\\\"
        for c in climatology)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def math_close(a,b):
    return abs(a-b)<1e-9


if __name__=='__main__':
    main()
