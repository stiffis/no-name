# Recursos: Lunar Landing Site Navigator

NASA Space Apps Challenge 2026, 14 y 15 de noviembre. Enunciado completo con recursos oficiales: 28 de octubre.

> Reto: herramienta intuitiva para comparar sitios y fechas de alunizaje en el polo sur
> lunar, visualizando la posición del Sol y la Tierra respecto al horizonte para evaluar
> la generación de energía y las ventanas de comunicación directa con la Tierra.

Recopilado el 2026-10-26 y actualizado el 2026-10-28 con el enunciado oficial (ver `ENUNCIADO.md`). Cada recurso tiene enlace. Lo que no pude verificar a fondo está marcado con ⚠️.

## Lo que pide el enunciado oficial

- **Las métricas que nombra**: elevación solar (en grande), duración de la luz solar, ventanas de visibilidad de la Tierra y **tiempo que falta para la puesta del Sol o de la Tierra** (sunset/Earthset).
- **No solo el polo sur**: lista curada de sitios (Apollo, objetivos CLPS, misiones comerciales, otros países) **más coordenadas personalizadas**. El polo sur es el caso más difícil, no el único.
- **El caso de uso central**: "la misión se retrasó, ¿qué sitio alternativo de la misma región o qué fecha alternativa en el mismo sitio sirve?". Compara escenarios lado a lado y rápido.
- **Horizonte sin atmósfera**: terreno + borde de la esfera lunar, sin refracción.
- **Libración**: la piden considerar. skyfield/SPICE ya la incluyen si se usan bien los marcos (§2).
- **Para dos públicos**: planificadores (detalle técnico) y educadores o público general (por qué la Luna es tan distinta).
- **Herramientas existentes que nombran**: QuickMap, Moon Trek y JPL Horizons (§7).
- **Recursos oficiales: viernes 13 de noviembre**, un día antes del hackathon.

---

## 0. Ruta de estudio

| Fechas | Bloque | Ejercicio para cerrar el bloque |
|---|---|---|
| 26 oct – 1 nov | **Geometría**: marcos lunares, efemérides, skyfield (§1, §2) | Azimut y elevación del Sol y la Tierra vistos desde Shackleton durante 1 mes, sin terreno |
| 2 – 8 nov | **Terreno**: rasters, estereográfica polar, DEM LOLA, horizonte (§3, §4) | Máscara de horizonte de un sitio + % de iluminación; comparar con los papers (§5) |
| 9 – 13 nov | **Rendimiento e interfaz** (§6, §7) y lectura del enunciado oficial | Medir cuánto tarda el horizonte y probar una vista en el navegador |
| 14 – 15 nov | **Hackathon**: se construye de cero lo que se entrega | — |

Lo que hagas antes del 14 es estudio y pruebas desechables. Confirma con el Local Lead si se puede traer código previo (§8).

---

## 1. Conceptos clave (resumen para no perderse)

- **Marco Mean Earth / Polar Axis (MOON_ME)**: el estándar de coordenadas lunares que usan LRO y LOLA. Su eje X apunta, en promedio, a la Tierra. El otro marco, **MOON_PA** (ejes principales de inercia), difiere en cientos de metros: no los mezcles.
- **Radio de referencia lunar**: 1737.4 km. Las alturas de LOLA están medidas respecto a esta esfera.
- **El Sol en el polo sur**: el eje lunar está inclinado ~1.5° respecto a la eclíptica, así que el Sol da vueltas al horizonte subiendo y bajando apenas ~1.5°. Cualquier montaña lo tapa, y por eso el terreno lo decide todo.
- **La Tierra en el polo sur**: por la libración, la Tierra oscila unos grados alrededor de su posición media, que en el polo cae justo en el horizonte. Pasa cerca de la mitad del tiempo bajo el horizonte.
- **Máscara de horizonte**: para cada azimut, el ángulo de elevación del terreno más alto. Un astro se ve si su elevación es mayor que la máscara en su azimut. El Sol es un disco de ~0.5°, así que puede verse parcialmente.
- **Curvatura**: la Luna es pequeña y el horizonte "cae" rápido con la distancia. Hay que corregir la curvatura al calcular los ángulos con montañas lejanas, a decenas de km.

---

## 2. Efemérides y coordenadas

### Documentación
- **Skyfield, marcos planetarios (Luna)**: cómo cargar `moon_080317.tf`, `pck00008.tpc` y `moon_pa_de421_1900-2050.bpc`, construir `MOON_ME_DE421` y ubicar un observador en la superficie con `build_latlon_degrees(..., elevation_m=...)`. Es **el punto de partida**.
  https://rhodesmill.org/skyfield/planetary.html
- **Skyfield, documentación general** (tiempos, efemérides, altaz):
  https://rhodesmill.org/skyfield/
- **NAIF SPICE, tutoriales oficiales**: el estándar de la NASA para geometría espacial. Para el reto basta con leer los de marcos (FK) y orientación (PCK).
  https://naif.jpl.nasa.gov/naif/tutorials.html
- **NAIF, tutorial de marcos Luna/Tierra** (PCK y FK lunares, ME vs PA):
  https://naif.jpl.nasa.gov/pub/naif/self_training/individual_docs/A6_lunar-earth_pck-fk.pdf
- **SpiceyPy, lección práctica de PCK binario**: calcula el punto subterrestre en MOON_ME y en MOON_PA y mide cuánto difieren.
  https://spiceypy.readthedocs.io/en/main/binary_pck.html
- **Kernels genéricos de NAIF** (DE440, marcos lunares actuales `moon_de440_*.tf`):
  https://naif.jpl.nasa.gov/pub/naif/generic_kernels/
- **WebGeocalc** (calculadora web de SPICE, útil para **validar** tus números):
  https://wgc.jpl.nasa.gov/
- **JPL Horizons**, la fuente que nombra el enunciado. Calcula efemérides, iluminación y visibilidad desde **puntos de la superficie de otros cuerpos** (la Luna es el cuerpo 301). Sirve para validar skyfield o como fuente alternativa.
  - Manual: https://ssd.jpl.nasa.gov/horizons/manual.html
  - Tutorial: https://ssd.jpl.nasa.gov/horizons/tutorial.html
  - API: https://ssd-api.jpl.nasa.gov/doc/horizons.html
  - Desde Python con astroquery (observador en la Luna con `{'lon':…, 'lat':…, 'elevation':…, 'body': 301}`): https://astroquery.readthedocs.io/en/stable/jplhorizons/jplhorizons.html
  - ⚠️ No confirmé la sintaxis exacta de la API cruda (`coord@301`); con astroquery el ejemplo de la Luna sí está documentado.

### Estándares de coordenadas lunares
- **"A Standardized Lunar Coordinate System for the LRO"** (white paper, 2008). Explica por qué se eligió MOON_ME y el radio de 1737.4 km.
  https://science.nasa.gov/wp-content/uploads/2024/01/luncoordwhitepaper-10-08.pdf
- **USGS, "Lunar Grid Systems, Coordinate Systems and Map Projections for the Artemis Missions"**:
  https://www.usgs.gov/publications/lunar-grid-systems-coordinate-systems-and-map-projections-artemis-missions-and-lunar

### Libros
- **Jean Meeus, *Astronomical Algorithms*** (2.ª ed., 1998). El clásico para calcular posiciones de astros a mano. Sirve para entender lo que skyfield hace por dentro. *De pago.*
- **Urban & Seidelmann, *Explanatory Supplement to the Astronomical Almanac*** (3.ª ed., 2013). Referencia de sistemas de tiempo y coordenadas. Para consultar, no para leer entero. *De pago.*
- **Montenbruck & Pfleger, *Astronomy on the Personal Computer***. Igual que Meeus, pero orientado a código. *De pago.*

---

## 3. Datos de terreno (LOLA, a bordo de LRO)

- **PGDA, "A New View of the Lunar South Pole from LOLA"**: DEMs de 80–90°S a **20 m/píxel**, como GeoTIFF optimizados para la nube (COG). Ejemplo: `LDEM_80S_20MPP_ADJ.TIF`. Los archivos `LDEC` son mapas de conteo para saber qué píxeles tienen medición real.
  https://pgda.gsfc.nasa.gov/products/90
- **PGDA, mosaico de 5 m/píxel de 87–90°S**: unos 3.3 GB solo el de alturas. Hay que citar a Barker et al. (2021), *Planetary & Space Science*.
  https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/
- **PGDA, DEMs de 5 m por sitio** (Shackleton, de Gerlache, Malapert, etc.):
  https://pgda.gsfc.nasa.gov/products/78
  https://core2.gsfc.nasa.gov/PGDA/LOLA_5mpp
- ⚠️ ~90 % de los píxeles de 5 m son **interpolados**. Usa los mapas de conteo para saber dónde confiar.
- **PGDA, "Lunar Polar Illumination"**: mapas de iluminación ya calculados. Sirven para **validar**.
  https://pgda.gsfc.nasa.gov/products/69
- **LROC, mapa de iluminación del polo sur ponderado por tiempo** (con imágenes de cámara, otra fuente para comparar):
  https://data.lroc.im-ldi.com/lroc/view_rdr/WAC_POLE_ILL_TWI_SOUTH
- **SLDEM2015** (LOLA + Kaguya), DEM **global entre 60°N y 60°S** a 512 px/grado (~59 m). Sirve para los sitios fuera del polo (Apollo, etc.). Cita: Barker et al. (2016), *Icarus*.
  https://pgda.gsfc.nasa.gov/products/54
  https://astrogeology.usgs.gov/search/map/moon_lro_lola_selene_kaguya_tc_dem_merge_60n60s_59m
- **Lista curada de sitios**: el enunciado pide Apollo, CLPS (IM-1 en Malapert, IM-2 en Mons Mouton, Blue Ghost en Mare Crisium…), misiones comerciales y de otros países (Chandrayaan-3, Chang'e 4/5/6, SLIM). ⚠️ Saca cada coordenada de una fuente oficial y cítala; no las copies de memoria. Los sitios de la **cara oculta** (Chang'e 4 y 6) tienen la Tierra **siempre** bajo el horizonte: buen ejemplo educativo.
- **Sitios candidatos de Artemis III** (anunciados en octubre de 2024): Peak near Cabeus B, Haworth, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 1, Nobile Rim 2, de Gerlache Rim 2 y Slater Plain. Son la **lista de sitios natural** para la herramienta.
  https://www.astronomy.com/space-exploration/here-are-the-nine-sites-where-artemis-3-might-land-on-the-moon/
  ⚠️ El plan de Artemis cambió: se reporta que Artemis III ya no alunizará y que pasará a ser un ensayo en órbita terrestre. Los sitios siguen siendo relevantes, pero no digas "Artemis III aterrizará aquí" sin revisar nasa.gov/artemis.
  https://www.skyatnightmagazine.com/news/artemis-iii-wont-land-on-moon

---

## 4. Algoritmo del horizonte

- **Dozier & Frew (1990)**, "Rapid calculation of terrain parameters for radiation modeling from digital elevation data", IEEE TGRS, DOI 10.1109/36.58986. Es **el** algoritmo clásico para el horizonte: rota la grilla hacia cada azimut y resuelve un problema 1D, con una poda que evita revisar todos los puntos.
  https://ntrs.nasa.gov/citations/19910030222
- **topocalc** (implementación en Python + C de Dozier & Frew, para leer código real):
  https://pypi.org/project/topocalc/
- **Paper de GMD (2022)** sobre cálculo eficiente de horizonte y factor de cielo visible. Compara métodos y rendimiento.
  https://gmd.copernicus.org/articles/15/6817/2022/
- **GRASS GIS `r.horizon` y `r.sun`**: herramientas libres que ya hacen esto en la Tierra. Sus manuales explican los parámetros.
  https://grass.osgeo.org/grass-stable/manuals/r.horizon.html

**Plan de implementación sugerido**: (1) versión ingenua, que marcha por el rayo en cada azimut y es O(azimuts × distancia), para tener una referencia correcta; (2) agregar la corrección por curvatura; (3) optimizar con Dozier o paralelizar, comparando siempre contra la versión ingenua.

---

## 5. Papers científicos (para validar y para el pitch)

- **Mazarico et al. (2011)**, iluminación de las regiones polares con topografía LOLA. Calculan horizontes y simulan ~18.6 años con paso de 1 hora.
  https://ntrs.nasa.gov/citations/20120010094
- **Gläser et al. (2014)**, *Icarus* 243, 79–90, DOI 10.1016/j.icarus.2014.08.013. DTM de 20 m/píxel; el sitio "Connecting Ridge" recibe Sol el **92.27 %** del tiempo a 2 m del suelo. **Buen número para validar tu herramienta.**
  https://elib.dlr.de/94240
- **Gläser et al. (2017)**, *Planetary and Space Science*: regiones de máxima iluminación en ambos polos.
  https://elib.dlr.de/119091
- **Speyerer & Robinson (2013)**, *Icarus* 222(1), 122–136, DOI 10.1016/j.icarus.2012.10.010. Regiones casi siempre iluminadas, a partir de imágenes de la cámara WAC.
  https://www.lroc.asu.edu/images/991
- **Bryant (JPL), visibilidad de la Tierra e iluminación en el polo sur**, con horizontes del radar de Goldstone. En el mejor sitio: ~92 % de Sol y ~50 % de comunicación directa con la Tierra. **El paper más cercano al reto: combina Sol y Tierra.**
  https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.html
  https://ntrs.nasa.gov/citations/20150008843
- **Barker et al. (2021)**, LOLA mejorado en el polo sur (base de los DEMs de 5 m):
  https://ntrs.nasa.gov/citations/20205009660
- **Wikipedia, "Peak of eternal light"**, para entender el concepto y como puerta a más fuentes:
  https://en.wikipedia.org/wiki/Peak_of_eternal_light

---

## 6. Rendimiento (tu ventaja: arquitectura)

- **Gorelick & Ozsvald, *High Performance Python*** (2.ª ed., 2020). Perfilado, NumPy, Cython, multiprocessing. *De pago.*
- **Ulrich Drepper, "What Every Programmer Should Know About Memory"** (2007). Cachés, localidad, TLB. Gratis.
  https://people.freebsd.org/~lstewart/articles/cpumemory.pdf
- **Bryant & O'Hallaron, *Computer Systems: A Programmer's Perspective***, capítulos de optimización y jerarquía de memoria. *De pago.*
- Ideas concretas para el reto:
  - Cada azimut es independiente: paraleliza por azimut o por sitio.
  - Recorrer el raster en diagonal falla en caché; Dozier rota la grilla para leer en filas contiguas.
  - Precalcula y cachea las máscaras de horizonte por sitio. Las efemérides son baratas, el terreno no.
  - Si NumPy no alcanza: el núcleo en C o Go llamado desde Python, o un compute shader en el navegador (WebGPU).

---

## 7. Interfaz y visualización

- **Cesium Moon** (antes "Cesium Moon Terrain"): la Luna en 3D en el navegador con CesiumJS. Polo sur a 5 m/píxel en 87.5–90°S. Requiere cuenta gratuita de Cesium ion. ⚠️ Hay artefactos visuales reportados justo en el polo.
  https://cesium.com/platform/cesium-ion/content/cesium-moon/
  https://cesium.com/blog/2024/08/06/introducing-cesium-moon-terrain/
- **Herramientas existentes**: el reto dice que son difíciles de usar. Estúdialas para saber qué hacer mejor.
  - LROC QuickMap: https://quickmap.lroc.asu.edu/
  - NASA Moon Trek: https://trek.nasa.gov/moon/
- **Proyección estereográfica polar**: los DEMs de LOLA vienen en esta proyección, en metros.
  - Snyder, *Map Projections: A Working Manual*, USGS PP 1395 (1987). Gratis y con todas las fórmulas: https://pubs.usgs.gov/publication/pp1395
  - Rasterio (leer GeoTIFF y transformar coordenadas): https://rasterio.readthedocs.io/
- **Visualización del cielo**: un diagrama polar con la máscara de horizonte (perfil del terreno) más las trayectorias del Sol y la Tierra encima. Es la vista que más se entiende de un vistazo. Matplotlib sirve para prototipos.

---

## 8. Reglas de Space Apps 2026

- FAQ de participantes: IA ("Super Intelligence") permitida; **el envío debe describir cómo se usó.**
  https://www.spaceappschallenge.org/resources/participant-faqs/
- Términos y condiciones 2026: el código es open source (Apache 2.0 por defecto) y **hay que citar todas las fuentes**. Sin citas pueden quitar el premio.
  https://www.spaceappschallenge.org/legal/
- Envío: abre el sáb 14 de noviembre a las 9:00 y cierra el dom 15 a las 23:59, hora local.
- ⚠️ No está claro si se permite código escrito antes del 14. **Pregúntale al Local Lead.**

---

## 9. Checklist de citas (ir llenando)

- [ ] DEM LOLA usado (producto PGDA + paper de Barker et al. 2021 si es el de 5 m)
- [ ] Kernels de efemérides (NAIF / JPL DE)
- [ ] Skyfield, NumPy, rasterio y demás librerías
- [ ] Papers usados para validar
- [ ] Declaración de uso de IA
