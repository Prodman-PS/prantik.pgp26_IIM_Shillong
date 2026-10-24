PYTHON ?= python

# Regenerate the synthetic dataset (seeded; identical to the shipped copy)
data:
	$(PYTHON) -m src.generator --n-patients 800 --seed 42 --out data/synthetic

# Feature table only (~45 s) — enough for the dashboard, since trained models are committed in artifacts/
features:
	$(PYTHON) -m src.features.fusion

# Jury quick start: build the feature table, then open the dashboard
quickstart: features dashboard

# Feature fusion -> flare model (baseline + LightGBM, ablation) -> alert feed   (~15 min on 2 cores)
train:
	$(PYTHON) -m src.features.fusion
	$(PYTHON) -m src.models.train
	$(PYTHON) -m src.alerts.run

# Doctor dashboard on http://localhost:8501
dashboard:
	$(PYTHON) -m streamlit run src/dashboard/app.py

test:
	$(PYTHON) -m pytest -q tests

all: data train test

.PHONY: data features quickstart train dashboard test all
