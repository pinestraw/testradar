PYTHON ?= $(shell ./scripts/find_python.sh)

.PHONY: bootstrap bootstrap-dev test package smoke-wheel release-check print-version clean

bootstrap:
	./scripts/pip_user_install.sh "$(PYTHON)" -e .

bootstrap-dev:
	./scripts/pip_user_install.sh "$(PYTHON)" -e '.[dev]'

test: bootstrap-dev
	$(PYTHON) -m pytest

package: bootstrap-dev
	rm -rf dist build
	$(PYTHON) -m build --no-isolation
	$(PYTHON) -m twine check --strict dist/*
	$(PYTHON) scripts/check_dist.py dist/*

smoke-wheel: package
	wheel="$$(ls dist/*.whl | head -n 1)"; \
	temp_site="$$(mktemp -d)"; \
	trap 'rm -rf "$$temp_site"' EXIT; \
	[ -n "$$wheel" ] || { echo "No wheel found in dist/"; exit 1; }; \
	$(PYTHON) -m pip install --target "$$temp_site" "$$wheel"; \
	PYTHONPATH="$$temp_site" $(PYTHON) -m testradar --help

release-check: test smoke-wheel

print-version:
	$(PYTHON) scripts/read_version.py

clean:
	rm -rf dist build .pytest_cache .coverage htmlcov
