# Fuego desde el espacio

Libro en español sobre detección de fuego activo, MODIS, VIIRS, armonización y calendarios de actividad. La edición completa contiene 14 capítulos y tres apéndices: glosario, fórmulas y fuentes comentadas.

- **Lectura:** `libro.pdf`.
- **Texto editable:** `libro.tex`, `preambulo.tex` y `capitulos/`.
- **Imágenes reales:** `figuras/`; su fuente, fecha, encuadre y huella están en `figuras/procedencia_imagenes.json`.
- **Gráficos del caso peruano:** `figuras/peru_*.pdf`, con versiones SVG editables y PNG. Se generan con `scripts/generar_graficos.py`.

## Datos reales de Perú

Se conservan 32 archivos nacionales anuales de NASA FIRMS: MODIS y VIIRS/Suomi NPP de 2013–2024, y VIIRS/NOAA-20 de 2018–2025. Los 24 de MODIS y Suomi NPP contienen 1 100 073 filas originales; los 8 de NOAA-20, 629 297. Las URL, versiones, tamaños y SHA-256 están en `datos/procedencia_peru.json` y `datos/procedencia_noaa20.json`.

El análisis selecciona Aqua o Suomi NPP por separado, pasadas diurnas, tipo 0 y confianza MODIS ≥30 o VIIRS nominal/alta. Elimina duplicados idénticos y agrupa por celda de 0,05° y fecha local UTC−5, con origen de rejilla en −90°, −180°. Una celda-día con detección no equivale a un incendio ni a superficie quemada. Los conteos no se corrigen por cobertura ni nubes.

La referencia estacional usa Suomi NPP de 2013–2023 y la compara con 2024. La calibración Aqua → Suomi NPP usa 2018–2020 y se evalúa sin reajuste en 2021–2022: razón 4,6849; MAE mensual 717,4; WAPE 21,6 %. Es una comparación entre registros satelitales, no una validación contra verdad de terreno ni un factor universal para Perú.

`scripts/comparar_modelos.py` compara cuatro conversiones Aqua → Suomi NPP (razón única, trimestral, mensual y ley de potencia). El modelo se elige con validación cruzada por año dentro de 2018–2020 y se evalúa una vez en 2021–2022. Gana la ley de potencia, V = 27,4·A^0,75, con WAPE 7,0 % frente a 21,6 % de la razón única. En los periodos de contraste, que tienen otra etiqueta de versión MODIS, obtiene 7,6 % (2013–2017) y 12,0 % (2023–2024). Es un ajuste nacional y mensual: no es aditivo ni trasladable sin más a otras escalas.

`scripts/regiones_peru.py` repite el ajuste por región natural aproximada (costa, sierra, selva), definida por relieve con teselas Terrarium de AWS Open Data guardadas en `datos/relieve/`; requiere NumPy y Pillow. Razón única: costa 8,74; sierra 5,05; selva 4,31. La regla de región es una aproximación por elevación, no el mapa oficial.

`scripts/noaa20_peru.py` añade el segundo eslabón: Suomi NPP → NOAA-20 (carpeta `viirs-jpss1` de FIRMS, 2018–2025, versión `2`). Ajuste 2019–2021, prueba 2022–2024. Razón SNPP/NOAA-20 = 0,964 y exponente β = 1,00 (proporcional); WAPE de prueba 6,5 %. Permite continuar la serie después del cierre de Suomi NPP (2 de noviembre de 2026). 2018 empieza el 1 de abril y no se usa para ajustar; 2025 se convierte pero no se valida.

Los archivos MODIS descargados contienen distintos valores del campo `version`. El ejercicio de calibración se restringe a 2018–2022, con valor constante `6.03`; no se presenta toda la serie MODIS como un producto homogéneo. Los capítulos 13 y 14 detallan las decisiones y límites.

## Reproducción

El análisis y la verificación requieren Python 3 y su biblioteca estándar. Los cuatro gráficos nuevos requieren Matplotlib y NumPy; la descarga, `curl`; el libro, `latexmk` y una instalación de LaTeX con los paquetes del preámbulo. Las figuras generadas ya están incluidas: no es necesario regenerarlas para compilar el PDF.

```sh
bash scripts/descargar_peru.sh
python3 scripts/analizar_peru.py
python3 scripts/comparar_modelos.py
python3 scripts/regiones_peru.py
python3 scripts/noaa20_peru.py
python3 scripts/verificar_ejemplos.py
python3 scripts/generar_graficos.py
latexmk -pdf -interaction=nonstopmode -halt-on-error libro.tex
```

La descarga conserva los originales existentes. Antes de sustituirlos por versiones nuevas, guarda una copia del directorio `datos/`: el proveedor puede reprocesar sus archivos. Regenerar el análisis actualiza el manifiesto con los archivos disponibles; no recupera automáticamente una edición anterior.

`verificar_ejemplos.py` comprueba las huellas de los 24 originales y ocho imágenes, la unicidad de los 288 agregados mensuales, las cifras de validación, los percentiles y varios ejemplos numéricos. Los CSV derivados y las macros LaTeX se producen desde los mismos originales.

## Procedencia visual

Las escenas de Camp Fire (California, 9 de noviembre de 2018) y de la selva central peruana (15 de septiembre de 2024) proceden de NASA Worldview. Las composiciones en falso color se identifican como tales. Los esquemas conceptuales y ejemplos numéricos ilustrativos se distinguen de los datos observados en sus pies y explicaciones. El apéndice C reúne las referencias y especifica las capas de cada escena.
