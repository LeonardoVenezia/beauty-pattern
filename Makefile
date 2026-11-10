UV ?= $(HOME)/.local/bin/uv
PY := $(UV) run python
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: setup web-install test lint typecheck eval demo dev api web e2e pdf examples clean

setup:
	$(UV) sync --all-groups
	cd web && npm ci

web-install:
	cd web && npm ci

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check engine ai vision api render tests evals scripts
	$(UV) run mypy

typecheck: lint

eval:
	$(PY) -m evals.run_eval

demo:
	$(PY) -m scripts.demo

examples:
	$(PY) -m scripts.generate_examples

dev:
	@echo "Levanta API (8000) y web (3000) en paralelo. Ctrl+C corta ambos."
	@trap 'kill 0' INT TERM; \
	$(PY) -m uvicorn api.main:app --reload --port 8000 & \
	cd web && npm run dev & \
	wait

api:
	$(PY) -m uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

e2e:
	cd web && npx playwright test

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache data .ai-cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
