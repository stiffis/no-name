.PHONY: datos celdas modelo exportar diagnostico auditoria todo

datos:
	bash pipeline/descargar.sh

celdas:
	python3 pipeline/celdas.py

modelo:
	python3 pipeline/modelo.py

exportar:
	python3 pipeline/exportar.py

diagnostico:
	python3 pipeline/diagnostico.py

auditoria:
	python3 investigacion/extraer.py
	python3 investigacion/auditoria.py

todo: datos celdas modelo exportar diagnostico
