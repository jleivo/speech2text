# speech2text — Makefile
# Source: ~/git/speech2text
# Runtime: /srv/speech2text on tucspeechp01.intra.leivo

SERVICE := speech2text
SRV_DIR := /srv/$(SERVICE)
DEPLOY_HOST := tucspeechp01.intra.leivo
PYTHON := .venv/bin/python

.PHONY: deploy build test clean lint

build:
	@echo "Interpreted language — nothing to build."
	@if [ ! -d .venv ]; then \
		echo "Creating venv..."; \
		python3 -m venv .venv --prompt $(SERVICE); \
		.venv/bin/pip install -r requirements.txt --upgrade --quiet; \
	fi

test: build
	$(PYTHON) -m pytest tests/ -v --tb=short

lint: build
	$(PYTHON) -m pylint handlers/ src/ --disable=R0801 --fail-under=8.0 || true

deploy: test
	@echo "Deploying $(SERVICE) to $(DEPLOY_HOST):$(SRV_DIR)..."
	ssh jaxon@$(DEPLOY_HOST) 'cd $(SRV_DIR) && \
		sudo -u $(SERVICE) git pull origin main && \
		sudo -u $(SERVICE) $(SRV_DIR)/.venv/bin/pip install -r requirements.txt --upgrade --quiet && \
		sudo systemctl restart $(SERVICE).service && \
		sleep 2 && systemctl is-active $(SERVICE).service'
	@echo "Deployed $(SERVICE) to $(DEPLOY_HOST)"

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ *.egg-info
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
