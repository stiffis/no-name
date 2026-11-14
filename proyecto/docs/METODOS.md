# Métodos de armonización: auditoría, correcciones y fórmulas finales

Fecha: 13 de noviembre de 2026. Ámbito: Perú, detecciones diurnas, 2003–2025.
Todo lo que sigue se reproduce con `make todo` y `python3 investigacion/extraer.py && python3 investigacion/auditoria.py`.
Los números de la auditoría están en `docs/auditoria.txt`; los del modelo, en `datos/derivados/modelo.json`.

## 1. Qué se unifica

Tres registros de focos de calor de NASA FIRMS, que miden lo mismo con instrumentos distintos:

| Registro | Sensor | Píxel | Años usados | Papel |
|---|---|---|---|---|
| Aqua | MODIS | 1 km (hasta 2 × 4,8 km en el borde) | 2003–2011 | se convierte |
| Suomi NPP | VIIRS | 375 m (hasta 0,8 km) | 2012–2025 | escala común |
| NOAA-20 | VIIRS | 375 m | 2018–2025 | rellena los cortes de Suomi NPP |

Los tres cruzan el ecuador a las 13:30. Terra (10:30) no se usa: observa otro momento del ciclo diario del fuego.

## 2. Lo que encontró la auditoría

### 2.1 Cortes de servicio en plena temporada (corregido)

Los archivos no avisan de los días en que un satélite no observó. Se encontraron tres casos que distorsionaban el método:

| Satélite | Periodo | Causa | Efecto medido en nuestros datos |
|---|---|---|---|
| Aqua | 16 ago – 2 sep 2020 | anomalía del formateador | la razón VIIRS/Aqua de esa quincena es 26, frente a 3,2–4,3 en los demás años |
| Aqua | 31 mar – 16 abr 2022 | modo seguro de la nave | 0 celdas-día de Aqua frente a 199 de Suomi NPP |
| Suomi NPP | 26 jul – 10 ago 2022 | modo seguro de la nave | 15 días sin una sola fila; NOAA-20 registra 204 filas diarias |

Además, Suomi NPP tiene otros 31 días sueltos sin datos entre 2020 y 2025, sobre todo en 2024.

El corte de Aqua de 2020 no deja días vacíos, porque la NASA reprocesó ese periodo con cobertura parcial. Solo se ve
comparando con otro sensor.

**Corrección aplicada:**
- *Suomi NPP*: un día es de corte si Suomi NPP no tiene ninguna celda-día en el país y NOAA-20 tiene al menos 30.
  Esos 46 días se rellenan con las celdas-día de NOAA-20 multiplicadas por 0,964 (la razón Suomi NPP / NOAA-20 de
  2019–2021). Los meses afectados quedan marcados como `snpp_rellenado`.
- *Aqua*: los cuatro meses afectados (2020-08, 2020-09, 2022-03, 2022-04) se excluyen de la calibración, de la
  validación cruzada y de la prueba. No afectan a la serie final, porque Aqua solo se usa hasta enero de 2012.
- Entre 2003 y 2011 no se encontró ningún corte de Aqua en temporada (se comparó con Terra).

### 2.2 Deriva de la órbita de Aqua (confirmado; el diseño ya lo evitaba)

Hora solar local media de las detecciones diurnas de Aqua: 13:34 entre 2002 y 2021; 13:40 en 2022; 13:52 en 2023;
14:17 en 2024; 14:50 en 2025. Suomi NPP y NOAA-20 se mantienen en 13:30 todos los años. Coincide con lo que publica la
NASA: Aqua dejó de mantener su órbita en 2021.

Consecuencia: **los datos de Aqua de 2023 en adelante no sirven para calibrar**. Nuestra calibración (2013–2017) y la
prueba (2018–2022) quedan antes de la deriva fuerte. En el contraste 2023–2025 el modelo subestima un 4 %, que es el
signo esperable de un cambio en el sensor de entrada.

### 2.3 La diferencia entre sensores no es un umbral de tamaño (cambia la interpretación)

Se comparó celda por celda, el mismo día, entre 2013 y 2017:

- Solo el **55 %** de las celdas-día de Aqua aparecen también en Suomi NPP (76 % contando las celdas vecinas).
- La probabilidad de que Aqua registre una celda-día que Suomi NPP sí registró crece con la potencia del fuego, pero
  **se satura cerca del 50 %**: 4 % con 2–5 MW, 22 % con 20–50 MW, 44 % con 100–200 MW, 54 % por encima de 500 MW.

Si la diferencia fuera solo que MODIS no ve fuegos pequeños, esa probabilidad llegaría a 100 % para los grandes. No
llega. Los dos satélites pasan con hasta una hora de diferencia y ven cada lugar con ángulos distintos: buena parte
de la discrepancia es de **muestreo**, no de sensibilidad.

Consecuencias:
- La armonización **solo es válida en agregados** (departamento y mes, o mayores). No se puede decir qué celda concreta
  ardió en 2005.
- El método alternativo de "quedarse con los fuegos de VIIRS por encima de cierta potencia" funciona peor. Con el mejor
  umbral (20 MW) el error nacional es 17 % y el departamental 26 %, frente a 9,3 % y 20,5 % del modelo estadístico.
  Se descarta.

### 2.4 El modelo log-lineal falla con ceros (corregido antes, documentado)

La ley de potencia ajustada sobre logaritmos, que funciona a escala nacional, sobrestima entre 40 % y 141 % a escala de
departamento: la mitad de los meses tienen cero o muy pocas detecciones y la corrección de retransformación se infla.
Se sustituyó por una regresión de Poisson, que modela el valor esperado directamente y admite ceros.

### 2.5 Cada departamento tiene su propio nivel (mejora añadida)

Con una sola curva por región natural, algunos departamentos quedaban sistemáticamente altos o bajos. Se añadió un
factor por cada trozo departamento × región, contraído hacia 1 para que los trozos con pocos datos no se disparen.
La validación cruzada lo eligió, y el error por departamento baja de 25,5 % a 20,5 %.

### 2.6 Etiquetas de versión de MODIS (no resuelto)

El campo `version` de los archivos MODIS vale `6.2` de 2000 a 2017, `6.03` de 2018 a 2022 y `61.03` desde 2023.
La documentación de FIRMS explica el formato general (colección y origen del procesamiento) pero **no encontré qué
significan esos tres valores concretos**. Por precaución, la calibración usa 2013–2017, que tiene la misma etiqueta
que los años que se convierten (2003–2011). La prueba de 2018–2022 cruza a la etiqueta `6.03` y el error no empeora,
lo que sugiere que el cambio no es grave, pero no lo demuestra.

## 3. El método final

### 3.1 Unidad

Para cada celda de 0,05° × 0,05° (índices `i = ⌊(lat + 90)·20⌋`, `j = ⌊(lon + 180)·20⌋`) y cada día local (UTC−5):

```
I(sensor, celda, día) = 1 si hay al menos una detección aceptada; 0 si no
```

Detección aceptada: pasada diurna, `type = 0`, sin filas idénticas repetidas; Aqua con confianza ≥ 30; VIIRS con
confianza nominal o alta.

La actividad de un trozo `t` (departamento × región natural) en un mes es la suma de `I` sobre sus celdas y sus días:
`A` para Aqua, `V` para VIIRS. La unidad es la celda-día.

### 3.2 Relleno de Suomi NPP

```
V(t, mes) = S(t, días sin corte) + ρ · N(t, días de corte),      ρ = 0,9641
```

`S` y `N` son las celdas-día de Suomi NPP y de NOAA-20. `ρ` es la razón de sumas nacionales de 2019–2021.
En la prueba del libro (ajuste 2019–2021, prueba 2022–2024) esta conversión tiene un error mensual de 6,5 %.

### 3.3 Conversión de Aqua a la escala de VIIRS

```
E[V] = f_t · exp( a_r + b_r · ln(1 + A) )
```

con `r` la región natural del trozo. Los parámetros `a_r`, `b_r` se estiman por máxima verosimilitud de Poisson
(Newton–Raphson) con los meses de 2013–2017:

| Región | a | b |
|---|---|---|
| Costa | 1,497 | 1,115 |
| Sierra | 1,588 | 0,982 |
| Selva | 2,057 | 0,878 |

El factor de cada trozo es

```
f_t = ( V_t + k ) / ( P_t + k ),      k = 50
```

donde `V_t` es la suma observada del trozo en 2013–2017 y `P_t` la suma que predice la curva regional. Con `k = 50`,
un trozo con miles de celdas-día usa su propio nivel y uno con pocas se queda cerca de 1. Hay 47 trozos; la mediana de
`f_t` es 0,94 y el rango va de 0,16 a 1,58.

El valor de un departamento, una región o el país es la **suma** de sus trozos convertidos. Así todos los niveles
cuadran entre sí.

### 3.4 La serie

```
2003-01 a 2012-01:  valor = Aqua convertido (3.3), con banda
2012-02 a 2025-12:  valor = VIIRS (3.2)
```

Suomi NPP empieza el 20 de enero de 2012, por eso enero de 2012 todavía usa Aqua.

### 3.5 Incertidumbre

Para cada nivel (país, región, departamento) y cada tamaño de predicción, se toman los percentiles 10 y 90 del
cociente observado / predicho en la validación cruzada de 2013–2017, siempre con predicciones fuera de muestra.
La banda de un mes es `[P10 · predicción, P90 · predicción]`.

Comprobación en la prueba 2018–2022: la banda contiene el valor observado en el 82,8 % de los casos por departamento,
el 76,2 % por región y el 71,4 % a nivel país. Lo esperado es 80 %: **a nivel país la banda es algo estrecha**.

### 3.6 Lo normal y la anomalía

Para cada área y cada mes del año, con los años 2003–2024: mediana, percentil 10 y percentil 90 de la serie.
La anomalía de un mes es `100 · (valor / mediana − 1)`.

## 4. Validación

Diseño: calibración 2013–2017; selección del modelo por validación cruzada dejando un año fuera, con el error por
departamento y mes; prueba 2018–2022, que no interviene en nada de lo anterior. Error: WAPE = 100 · Σ|pred − obs| / Σ obs.

| Modelo | Validación cruzada (dep.) | Prueba: dep. | Prueba: país | Sesgo del total |
|---|---|---|---|---|
| Razón única | 30,7 | 34,5 | 23,9 | +3,7 % |
| Poisson por región | 25,9 | 25,5 | 9,6 | +1,8 % |
| **Poisson por región + factor de trozo (elegido)** | **20,5** | **20,5** | **9,3** | **+1,6 %** |
| Log-lineal por región | 79,7 | 84,2 | 74,5 | +73,0 % |

Sin excluir los meses con corte de Aqua, el error nacional del modelo elegido sería 12,1 %: casi un tercio del error
aparente era de los datos, no del modelo. La tabla completa con los 13 candidatos está en `datos/derivados/modelo.json`.

## 5. Supuestos y límites

1. **Estabilidad.** Se supone que la relación entre Aqua y VIIRS de 2013–2017 valía en 2003–2011. No se puede
   comprobar: VIIRS no existía. A favor: la razón de agosto–septiembre se mantiene entre 3,3 y 4,4 en los trece años
   del solape.
2. **Solo agregados.** La correspondencia celda a celda es del 55 %; la serie no sirve para localizar fuegos antiguos.
3. **Sin corrección de nubes ni de cobertura.** Un mes muy nuboso aparece con poca actividad. Las máscaras de nubes
   no están en los archivos de puntos de FIRMS.
4. **Solo las 13:30.** Las quemas de otras horas no se ven.
5. **Regiones naturales aproximadas** por relieve, no el mapa oficial.
6. **Error por departamento del 20 %.** Los meses con pocas detecciones tienen bandas muy anchas.
7. **Etiquetas de versión de MODIS sin aclarar** (sección 2.6).
8. **La banda a nivel país es estrecha** (cubre el 71 % en lugar del 80 %).
9. **2025 con cautela.** Suomi NPP tiene días rellenados y fue un año de actividad muy baja sin causa identificada.

## 6. Contexto en la literatura

- No encontré un método publicado y revisado que armonice **conteos** de focos MODIS–VIIRS en celdas; el trabajo
  publicado se centra en la potencia radiativa y en el área quemada.
- Li et al. (2018) comparan la potencia radiativa de ambos sensores y describen los duplicados de MODIS en ángulos
  grandes. Un artículo de 2026 en *Remote Sensing* propone corregir cada sensor antes de fusionarlos, en lugar de
  sumar detecciones.
- Vadrevu y Lasko (2018) encuentran en una zona agrícola de la India 4,8 veces más detecciones de VIIRS que de MODIS.
  En Perú medimos 4,6 en celdas-día: el mismo orden.
- Boschetti, Roy y Giglio trabajan en una serie armonizada de **área quemada** en celdas de 0,25°, calibrada
  estadísticamente por región. Es el mismo principio a otra escala.

## 7. Fuentes

- Corte de Aqua de 2020: https://ladsweb.modaps.eosdis.nasa.gov/alerts-and-issues/171856
- Modo seguro de Aqua de 2022: https://mcst.gsfc.nasa.gov/news
- Modo seguro de Suomi NPP de 2022: https://www.earthdata.nasa.gov/data/alerts-outages/suomi-npp-recovers-from-safe-mode
- Deriva de las órbitas de Terra y Aqua: https://modis-land.gsfc.nasa.gov/news.html
- Atributos de los datos de FIRMS: https://earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs
- Li et al. (2018): https://repository.library.noaa.gov/view/noaa/49896/noaa_49896_DS1.pdf
- Vadrevu y Lasko (2018): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6108185/
- Corrección y fusión de FRP (2026): https://doi.org/10.3390/rs18101650
- Boschetti, Roy y Giglio, continuidad MODIS–VIIRS: https://modis.gsfc.nasa.gov/sci_team/meetings/202204/presentations/session1/boschetti.pdf
