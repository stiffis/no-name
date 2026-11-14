"""Verificaciones independientes de cifras, tablas y procedencia del libro.
Solo biblioteca estándar. No descarga ni modifica datos.
"""
from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import json
import math
import statistics as st

ROOT = Path(__file__).resolve().parents[1]

def planck(lam_um, temp):
    lam = lam_um * 1e-6
    return 2*6.62607015e-34*299792458**2 / (lam**5*math.expm1(
        6.62607015e-34*299792458/(lam*1.380649e-23*temp))) * 1e-6

def main():
    # Coherencia dimensional e inversión de Planck, apéndice B.
    c1 = 2*6.62607015e-34*299792458**2*1e24
    c2 = 6.62607015e-34*299792458/1.380649e-23*1e6
    for lam in [3.96, 11]:
        for temp in [300, 600, 1000]:
            L = planck(lam,temp)
            inv = c2/(lam*math.log1p(c1/(lam**5*L)))
            assert math.isclose(inv,temp,rel_tol=1e-12)
    assert math.isclose(1/(.2+.8/8), 10/3)
    assert 10_000_000*(8+4+4+4+1+1) == 220_000_000
    assert sum(abs(a-b) for a,b in zip([2,8,45,110],[0,10,50,100]))/4 == 4.75
    assert 40*29 == 1160  # febrero bisiesto, ejercicio del capítulo 13
    # Presencias: la unión no equivale a la suma.
    assert len({('A',1),('B',1)} | {('B',1),('C',1)}) == 3
    manifest = json.loads((ROOT/'datos/procedencia_peru.json').read_text())
    assert len(manifest)==24
    for item in manifest:
        p=ROOT/'datos/originales'/item['archivo']
        assert p.stat().st_size==item['bytes'], p
        assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],p
    with (ROOT/'datos/peru_mensual.csv').open() as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==288
    assert len({(r['sensor'],r['anio'],r['mes']) for r in rows})==288
    vals={(r['sensor'],int(r['anio']),int(r['mes'])):int(r['celdas_dia']) for r in rows}
    for r in rows:
        assert 0 <= int(r['celdas_dia']) <= int(r['detecciones'])
    x=sum(vals['Aqua',y,m] for y in range(2018,2021) for m in range(1,13))
    v=sum(vals['SNPP',y,m] for y in range(2018,2021) for m in range(1,13))
    assert (x,v)==(26508,124188)
    ratio=v/x
    obs=[vals['SNPP',y,m] for y in [2021,2022] for m in range(1,13)]
    pred=[ratio*vals['Aqua',y,m] for y in [2021,2022] for m in range(1,13)]
    error=[p-o for p,o in zip(pred,obs)]
    report=json.loads((ROOT/'datos/resultados_peru.json').read_text())
    assert math.isclose(st.mean(map(abs,error)),report['mae_prueba'])
    assert math.isclose(st.mean(error),report['sesgo_prueba'])
    assert math.isclose(100*sum(map(abs,error))/sum(obs),report['wape_prueba_porcentaje'])
    for month in range(1,13):
        history=[vals['SNPP',y,month] for y in range(2013,2024)]
        q90=st.quantiles(history,n=10,method='inclusive')[8]
        c=report['climatologia'][month-1]
        assert c['q90']==q90 and c['mediana']==st.median(history)
    assert math.isclose(sum(c['fraccion_anual_media'] for c in report['climatologia']),100)
    assert report['total_filas_originales']==sum(i['filas_originales'] for i in manifest)
    for item in json.loads((ROOT/'figuras/procedencia_imagenes.json').read_text()):
        assert hashlib.sha256((ROOT/'figuras'/item['archivo']).read_bytes()).hexdigest()==item['sha256']
    modelos=json.loads((ROOT/'datos/peru_modelos.json').read_text())
    assert modelos['modelo_elegido']=='potencia'
    xs=[math.log(vals['Aqua',y,m]) for y in range(2018,2021) for m in range(1,13)]
    ys=[math.log(vals['SNPP',y,m]) for y in range(2018,2021) for m in range(1,13)]
    mx,my=st.mean(xs),st.mean(ys)
    beta=sum((a-mx)*(b-my) for a,b in zip(xs,ys))/sum((a-mx)**2 for a in xs)
    alfa=math.exp(my-beta*mx)
    pot=modelos['modelos']['potencia']
    assert math.isclose(beta,pot['parametros']['beta']) and math.isclose(alfa,pot['parametros']['alfa'])
    err=[alfa*vals['Aqua',y,m]**beta-vals['SNPP',y,m] for y in [2021,2022] for m in range(1,13)]
    assert math.isclose(100*sum(map(abs,err))/sum(obs),pot['prueba_2021_2022']['wape'])
    assert math.isclose(modelos['modelos']['unica']['prueba_2021_2022']['wape'],report['wape_prueba_porcentaje'])
    assert sum(int(r['detecciones']) for r in rows if r['sensor']=='SNPP' and 2018<=int(r['anio'])<=2020)==201257
    assert sum(int(r['detecciones']) for r in rows if r['sensor']=='Aqua' and 2018<=int(r['anio'])<=2020)==36546
    reg=defaultdict(int)
    with (ROOT/'datos/peru_regiones_mensual.csv').open() as f:
        for r in csv.DictReader(f):
            reg[r['sensor'],int(r['anio']),int(r['mes'])]+=int(r['celdas_dia'])
    assert reg==vals
    regiones=json.loads((ROOT/'datos/peru_regiones.json').read_text())
    assert sum(r['aqua_ajuste'] for r in regiones['regiones'].values())==x
    assert sum(r['viirs_ajuste'] for r in regiones['regiones'].values())==v
    for item in regiones['relieve']:
        assert hashlib.sha256((ROOT/'datos/relieve'/item['archivo']).read_bytes()).hexdigest()==item['sha256']
    procedencia_n20=json.loads((ROOT/'datos/procedencia_noaa20.json').read_text())
    assert len(procedencia_n20)==8
    for item in procedencia_n20:
        p=ROOT/'datos/originales'/item['archivo']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],p
        assert item['versiones']=={'2':item['filas_originales']}
    n20={}
    with (ROOT/'datos/peru_noaa20_mensual.csv').open() as f:
        for r in csv.DictReader(f):
            n20[int(r['anio']),int(r['mes'])]=int(r['celdas_dia'])
            assert 0<=int(r['celdas_dia'])<=int(r['detecciones'])
    assert all(n20[2018,m]==0 for m in (1,2,3))
    eslabon=json.loads((ROOT/'datos/peru_noaa20.json').read_text())
    r20=sum(vals['SNPP',y,m] for y in (2019,2020,2021) for m in range(1,13))/sum(n20[y,m] for y in (2019,2020,2021) for m in range(1,13))
    assert math.isclose(r20,eslabon['razon_snpp_sobre_noaa20'])
    obs20=[vals['SNPP',y,m] for y in (2022,2023,2024) for m in range(1,13)]
    err20=[r20*n20[y,m]-o for (y,m),o in zip(((y,m) for y in (2022,2023,2024) for m in range(1,13)),obs20)]
    assert math.isclose(100*sum(map(abs,err20))/sum(obs20),eslabon['prueba_razon']['wape'])
    cortes={(2020,8),(2020,9),(2022,3),(2022,4),(2022,7),(2022,8)}
    aj=[(y,m) for y in (2018,2019,2020) for m in range(1,13) if (y,m) not in cortes]
    pr=[(y,m) for y in (2021,2022) for m in range(1,13) if (y,m) not in cortes]
    rl=sum(vals['SNPP',y,m] for y,m in aj)/sum(vals['Aqua',y,m] for y,m in aj)
    lx=[math.log(vals['Aqua',y,m]) for y,m in aj]
    ly=[math.log(vals['SNPP',y,m]) for y,m in aj]
    bl=sum((a-st.mean(lx))*(b-st.mean(ly)) for a,b in zip(lx,ly))/sum((a-st.mean(lx))**2 for a in lx)
    al=math.exp(st.mean(ly)-bl*st.mean(lx))
    ol=sum(vals['SNPP',y,m] for y,m in pr)
    wu=100*sum(abs(rl*vals['Aqua',y,m]-vals['SNPP',y,m]) for y,m in pr)/ol
    wp=100*sum(abs(al*vals['Aqua',y,m]**bl-vals['SNPP',y,m]) for y,m in pr)/ol
    assert (round(rl,3),round(al,1),round(bl,2),round(wu,1),round(wp,1))==(4.541,29.5,0.73,19.6,7.4)
    print('Correcto: constantes y fórmulas, agregación, 32 originales, 288 agregados mensuales,')
    print('validación temporal, comparación de modelos, regiones, eslabón NOAA-20, percentiles históricos y procedencia de ocho imágenes.')

if __name__=='__main__':
    main()
