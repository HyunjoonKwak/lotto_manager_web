PY := .venv/bin/python
PIP := .venv/bin/pip
RUN_CMD := $(PY) -m app

.PHONY: venv install run clean

venv:
	@test -d .venv || python3 -m venv .venv
	@$(PY) -m pip install --upgrade pip

install: venv
	@if [ -f requirements.txt ]; then $(PIP) install -r requirements.txt; fi
	@if [ -f requirements-dev.txt ]; then $(PIP) install -r requirements-dev.txt; fi

run:
	@$(RUN_CMD)

clean:
	@rm -rf .venv **/__pycache__ .pytest_cache .ruff_cache dist build
