.PHONY: pdf graficos verificar modelos reproducir

pdf:
	latexmk -pdf -interaction=nonstopmode -halt-on-error libro.tex

graficos:
	python3 scripts/generar_graficos.py

modelos:
	python3 scripts/comparar_modelos.py
	python3 scripts/regiones_peru.py
	python3 scripts/noaa20_peru.py

verificar:
	python3 scripts/verificar_ejemplos.py

reproducir:
	bash scripts/descargar_peru.sh
	python3 scripts/analizar_peru.py
	python3 scripts/comparar_modelos.py
	python3 scripts/regiones_peru.py
	python3 scripts/noaa20_peru.py
	python3 scripts/verificar_ejemplos.py
	python3 scripts/generar_graficos.py
	latexmk -pdf -interaction=nonstopmode -halt-on-error libro.tex
