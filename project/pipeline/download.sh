#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$root/data/raw"
downloads=()
for year in {2000..2025}; do downloads+=("modis $year"); done
for year in {2012..2025}; do downloads+=("viirs-snpp $year"); done
for year in {2018..2025}; do downloads+=("viirs-jpss1 $year"); done
for item in "${downloads[@]}"; do
    read -r source year <<< "$item"
    name="${source}_${year}_Peru.csv"
    target="$root/data/raw/$name"
    if [[ -s "$target" ]]; then
        continue
    fi
    curl --fail --silent --show-error --location --retry 2 --max-time 180 \
        "https://firms.modaps.eosdis.nasa.gov/data/country/$source/$year/$name" \
        --output "$target.part"
    mv -- "$target.part" "$target"
    echo "downloaded $name"
done
