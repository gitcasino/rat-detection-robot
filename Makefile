# Development entry points. Everything is a thin wrapper around the tool each
# component already uses, so nothing here hides a command you can run yourself.

SHELL := /bin/bash
.DEFAULT_GOAL := help

ROOT := $(shell pwd)
VENV := $(ROOT)/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
BACKEND := $(ROOT)/backend
FRONTEND := $(ROOT)/frontend

.PHONY: help setup backend backend-test frontend frontend-test frontend-build lint typecheck firmware-check check simulator clean clean-all

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## Create the Python venv and install both dependency sets
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r $(BACKEND)/requirements.txt
	cd $(FRONTEND) && npm install
	@echo "ready: 'make backend' and 'make frontend'"

backend: ## Run the FastAPI server with reload
	cd $(BACKEND) && "$(VENV)/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000

backend-test: ## Run the backend pytest suite
	cd $(BACKEND) && "$(PY)" -m pytest -q

frontend: ## Run the Vite dev server
	cd $(FRONTEND) && npm run dev

frontend-test: ## Run the frontend vitest suite
	cd $(FRONTEND) && npm test

frontend-build: ## Type-check and build the production bundle
	cd $(FRONTEND) && npm run build

lint: ## Lint the frontend
	cd $(FRONTEND) && npm run lint

typecheck: ## Type-check the frontend
	cd $(FRONTEND) && npm run typecheck

firmware-check: ## Native firmware tests plus Arduino-facing syntax check
	bash $(ROOT)/tools/check_firmware.sh

simulator: ## Post synthetic telemetry to a local backend (opt-in, dev only)
	$(PY) $(ROOT)/scripts/simulate_telemetry.py --confirm-synthetic

check: firmware-check backend-test typecheck lint frontend-test frontend-build ## Run every check in order
	@echo "all checks passed"

clean: ## Remove build output
	rm -rf $(FRONTEND)/dist $(ROOT)/build
	find $(BACKEND) -name '__pycache__' -type d -prune -exec rm -rf {} +

clean-all: clean ## Also remove installed dependencies and local databases
	rm -rf $(VENV) $(FRONTEND)/node_modules
	rm -f $(BACKEND)/*.db $(BACKEND)/.pytest-*.db
