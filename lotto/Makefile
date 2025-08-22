PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: venv install run clean

venv:
	@test -d .venv || python3 -m venv .venv
	@$(PY) -m pip install --upgrade pip

install: venv
	@if [ -f requirements.txt ]; then $(PIP) install -r requirements.txt; fi
	@if [ -f requirements-dev.txt ]; then $(PIP) install -r requirements-dev.txt; fi

run:
	@$(PY) -m app   # 필요 시 엔트리포인트 변경

clean:
	@rm -rf .venv **/__pycache__ .pytest_cache .ruff_cache dist build
