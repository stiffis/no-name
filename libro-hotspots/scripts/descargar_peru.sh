#!/usr/bin/env bash
# CSV públicos de FIRMS. No requiere clave. Los archivos existentes se conservan.
# viirs-jpss1 es NOAA-20 (JPSS-1 era su nombre antes del lanzamiento).
set -euo pipefail
book_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$book_root/datos/originales"
descargas=()
for year in {2013..2024}; do descargas+=("modis $year" "viirs-snpp $year"); done
for year in {2018..2025}; do descargas+=("viirs-jpss1 $year"); done
for item in "${descargas[@]}"; do
    read -r source year <<< "$item"
    name="${source}_${year}_Peru.csv"
    dest="$book_root/datos/originales/$name"
    if [[ -s "$dest" ]]; then
      continue
    fi
    curl --fail --location --retry 2 --max-time 180 \
      "https://firms.modaps.eosdis.nasa.gov/data/country/$source/$year/$name" \
      --output "$dest.part"
    mv -- "$dest.part" "$dest"
done
