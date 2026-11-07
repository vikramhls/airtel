# Udyam OneFlow - see README. On Windows without make, use run.ps1.
PY ?= python

setup:
	$(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm install

seed:
	$(PY) scripts/seed.py

test:
	cd backend && $(PY) -m pytest -q

build:
	cd frontend && npm run build

dev:
	cd backend && $(PY) -m uvicorn app.main:app --reload --port 8000 & cd frontend && npm run dev

serve: build
	cd backend && $(PY) -m uvicorn app.main:app --port 8000

reports:
	$(PY) scripts/analyze_leads.py
	$(PY) scripts/run_kyc_batch.py
	$(PY) scripts/train_propensity.py --data backend/app/data --out reports --models models
	$(PY) scripts/simulate.py

.PHONY: setup seed test build dev serve reports
