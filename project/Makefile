.PHONY: data cells model export diagnostics verify audit serve all

data:
	bash pipeline/download.sh

cells:
	python3 pipeline/cells.py

model:
	python3 pipeline/model.py

export:
	python3 pipeline/export.py

diagnostics:
	python3 pipeline/diagnostics.py

verify:
	python3 pipeline/verify.py

audit:
	python3 research/extract.py
	python3 research/audit.py
	python3 research/floor.py

serve:
	python3 -m http.server 8000 --directory web

all: data cells model export verify diagnostics
