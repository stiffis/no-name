# NASA Space Apps Challenge 2026

Hackathon: 14 y 15 de noviembre de 2026. Reto: **Harmonization of MODIS and VIIRS Hot Spots**.
Recursos oficiales del reto: FIRMS (https://www.earthdata.nasa.gov/data/tools/firms).

## Estructura

```
space-apps-2026/
├── libro-hotspots/          proyecto activo
│   ├── libro.pdf            libro de estudio "Fuego desde el espacio"
│   ├── libro.tex, preambulo.tex, capitulos/, figuras/
│   ├── datos/originales/    32 CSV de FIRMS (Perú): MODIS y Suomi NPP 2013–2024, NOAA-20 2018–2025
│   ├── datos/relieve/       teselas de elevación para costa, sierra y selva
│   ├── datos/               tablas, JSON y macros derivados de los originales
│   ├── scripts/             descarga, análisis, modelos, regiones, NOAA-20, verificación, gráficos
│   ├── impresion/           PDF para imprimir del 11 de noviembre (versión anterior del libro)
│   ├── build/               temporales de LaTeX (se regeneran)
│   └── README.md            detalle de datos, resultados y reproducción
├── archivo/                 lo que ya no se usa; no se borró nada
│   ├── reto-lunar-navigator/   enunciado y guía del reto descartado
│   ├── respaldos/              tar.gz del libro antes de la continuación del 9 de noviembre
│   └── copia-suelta-venv/      copia de un .venv que apareció como .venv~
└── .venv/                   entorno con skyfield, scipy y rasterio (del reto lunar)
```

## Resultados centrales (Perú, celdas-día diurnas de 0,05°)

| Eslabón             | Modelo                      | Ajuste    | Prueba    | WAPE de prueba |
| ------------------- | --------------------------- | --------- | --------- | -------------- |
| Aqua → Suomi NPP    | razón única 4,685           | 2018–2020 | 2021–2022 | 21,6 %         |
| Aqua → Suomi NPP    | ley de potencia 27,4·A^0,75 | 2018–2020 | 2021–2022 | 7,0 %          |
| NOAA-20 → Suomi NPP | razón 0,964 (β = 1,00)      | 2019–2021 | 2022–2024 | 6,5 %          |

Por región, la razón Aqua → Suomi NPP es 8,74 en la costa, 5,05 en la sierra y 4,31 en la selva.
Suomi NPP dejó de entregar datos el 2 de noviembre de 2026; la serie continúa con NOAA-20.

## Comandos (desde `libro-hotspots/`)

```sh
make reproducir   # descarga lo que falte, recalcula todo, verifica y compila
make verificar    # comprueba huellas, cifras y tablas
make pdf          # compila el libro
```
