#!/usr/bin/env bash
set -euo pipefail
raiz="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$raiz/datos/originales"
descargas=()
for anio in {2000..2025}; do descargas+=("modis $anio"); done
for anio in {2012..2025}; do descargas+=("viirs-snpp $anio"); done
for anio in {2018..2025}; do descargas+=("viirs-jpss1 $anio"); done
for item in "${descargas[@]}"; do
    read -r fuente anio <<< "$item"
    nombre="${fuente}_${anio}_Peru.csv"
    destino="$raiz/datos/originales/$nombre"
    if [[ -s "$destino" ]]; then
        continue
    fi
    curl --fail --silent --show-error --location --retry 2 --max-time 180 \
        "https://firms.modaps.eosdis.nasa.gov/data/country/$fuente/$anio/$nombre" \
        --output "$destino.part"
    mv -- "$destino.part" "$destino"
    echo "descargado $nombre"
done
