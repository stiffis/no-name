# Calendario de quemas armonizado del Perú (MODIS + VIIRS)

Proyecto para el reto *Harmonization of MODIS and VIIRS Hot Spots* del NASA Space Apps Challenge 2026.

Une el registro de focos de calor de MODIS/Aqua (desde 2002) y de VIIRS/Suomi NPP (desde 2012) en una sola
escala, de 2003 a 2025, para el Perú, sus tres regiones naturales y sus 26 departamentos.

## Qué hace

1. **`pipeline/celdas.py`**: lee los CSV anuales de NASA FIRMS y cuenta, por celda de 0,05° y mes, los días
   con al menos una detección (celdas-día). Rellena los días de corte de Suomi NPP con NOAA-20 y asigna cada
   celda a su departamento y a su región natural.
2. **`pipeline/modelo.py`**: elige la conversión Aqua → VIIRS comparando 13 candidatos.
3. **`pipeline/exportar.py`**: arma la serie armonizada de cada área, sus bandas de incertidumbre y su
   referencia de lo normal, y escribe los JSON de `web/datos/`.
4. **`pipeline/diagnostico.py`**: dibuja `docs/continuidad_2012.png`, la comprobación del empalme.
5. **`investigacion/`**: la auditoría del método (`extraer.py` y `auditoria.py`), que escribe `docs/auditoria.txt`.

```sh
make todo        # descarga lo que falte y recalcula todo (~1 minuto sin contar la descarga)
```

Requiere Python 3 con NumPy, Pillow y Matplotlib, y `curl`.

## Decisiones

| Decisión | Valor | Por qué |
|---|---|---|
| Unidad | celdas-día diurnas, celda de 0,05°, fecha local UTC−5 | elimina duplicados entre píxeles y satélites |
| Sensores | Aqua y Suomi NPP | misma hora de paso (13:30) |
| Filtros | `type=0`; Aqua confianza ≥ 30; VIIRS nominal o alta | excluye fuentes estáticas y detecciones débiles |
| Escala común | Suomi NPP | es el registro que continúa (y NOAA-20 lo prolonga) |
| Calibración | 2013–2017 | misma etiqueta MODIS (`6.2`) que 2003–2011 y antes de la deriva orbital de Aqua |
| Selección | validación cruzada dejando un año fuera, error a nivel departamento-mes | es la escala que usa la web |
| Prueba | 2018–2022, no usada para elegir ni ajustar | |
| Unidad de ajuste | departamento × región natural | todos los niveles se obtienen sumando, sin incoherencias |

## Resultado

Modelo elegido por validación cruzada: **regresión de Poisson por región con un factor por departamento**,
E[V] = f·exp(a + b·ln(1 + A)). Las fórmulas, los parámetros y la auditoría completa están en
[`docs/METODOS.md`](docs/METODOS.md).

| Prueba 2018–2022 | Razón única | Modelo elegido |
|---|---|---|
| Error por departamento y mes (WAPE) | 34,5 % | **20,5 %** |
| Error nacional por mes (WAPE) | 23,9 % | **9,3 %** |
| Sesgo del total | +3,7 % | **+1,6 %** |

Tres correcciones que salieron de auditar los datos:
- **Cortes de servicio.** Aqua estuvo sin datos del 16 de agosto al 2 de septiembre de 2020 y del 31 de marzo al
  16 de abril de 2022; esos meses se excluyen del ajuste y de la prueba. Suomi NPP tiene 46 días sin datos entre
  2020 y 2025 (15 seguidos en julio–agosto de 2022), que se rellenan con NOAA-20.
- **Deriva de Aqua.** Su hora de paso va de 13:34 a 14:50 entre 2021 y 2025; por eso no se calibra con años posteriores a 2017.
- **Solo agregados.** Celda a celda, Aqua y VIIRS coinciden el mismo día solo el 55 % de las veces. La serie vale por
  departamento y mes, no para localizar fuegos.

## Límites

- Mide **actividad detectada a las 13:30 de días despejados**, no superficie quemada ni número de incendios.
- Sin corrección de nubes ni de cobertura.
- Las regiones naturales son una aproximación por relieve, no el mapa oficial.
- Los meses de 2003 a enero de 2012 son estimaciones, con su banda; el error por departamento ronda el 20 %.
- 2000–2002 quedan fuera: solo hay Terra, que pasa a otra hora.

## Fuentes

- NASA FIRMS, archivos anuales por país: MODIS Colección 6.x y VIIRS 375 m Colección 2.
  Huellas SHA-256 en `datos/derivados/procedencia.json`.
- geoBoundaries, gbOpen PER ADM1 (dominio público).
- Teselas de elevación Terrarium (AWS Open Data).
- Giglio et al. (2016) y Schroeder et al. (2014), algoritmos de detección.

## Uso de IA

Este proyecto se desarrolló con asistencia de Claude (Anthropic) para el análisis de datos, el código y la
documentación. Las decisiones y la revisión son del equipo.
