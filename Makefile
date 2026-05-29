UV_RUN ?= uv run
PYTHON ?= $(UV_RUN) python
ARGS ?=

.PHONY: help bootstrap bootstrap-with-uv setup setup-raw setup-xarray download download-raw convert package-zenodo test
.PHONY: clean clean-safe clean-build clean-cache clean-data clean-all distclean

-include make/internal-github.mk

help:
	@printf '%s\n' \
	  'make bootstrap       Create .venv and install project + dev dependencies (requires uv)' \
	  'make bootstrap-with-uv Install uv if missing, then run bootstrap' \
	  'make setup           Default setup (preconverted xarray from Zenodo)' \
	  'make setup-raw       Setup via raw source archives + conversion (advanced)' \
	  'make setup-xarray    Alias for setup (Zenodo xarray workflow)' \
	  'make download        Default download (preconverted xarray from Zenodo)' \
	  'make download-raw    Download raw source archives (advanced)' \
	  'make convert         Run the conversion CLI' \
	  'make package-zenodo  Stage processed files into build/zenodo' \
	  'make clean           Safe cleanup (build/test/cache artifacts)' \
	  'make clean-data      Remove downloaded/processed data directories' \
	  'make clean-all       Full cleanup (safe cleanup + data cleanup)' \
	  'make distclean       Alias for clean-all' \
	  'make test            Run the test suite' \
	  '' \
	  'Pass extra CLI args with ARGS="..."'
	@$(MAKE) --no-print-directory help-internal >/dev/null 2>&1 || true

bootstrap:
	@if ! command -v uv >/dev/null 2>&1; then \
	  echo "uv is not installed. Run 'make bootstrap-with-uv' or install uv first."; \
	  exit 1; \
	fi
	uv venv
	uv sync --all-extras
	@printf '%s\n' 'Environment ready. Use: source .venv/bin/activate'

bootstrap-with-uv:
	@if ! command -v uv >/dev/null 2>&1; then \
	  if command -v curl >/dev/null 2>&1; then \
	    curl -LsSf https://astral.sh/uv/install.sh | sh; \
	  else \
	    echo "curl is required to auto-install uv. Install uv manually, then run make bootstrap."; \
	    exit 1; \
	  fi; \
	fi
	@PATH="$$HOME/.local/bin:$$PATH" $(MAKE) bootstrap

setup:
	$(PYTHON) scripts/setup_data.py $(ARGS)

setup-raw:
	$(PYTHON) scripts/setup_data.py --download-source raw $(ARGS)

setup-xarray:
	$(MAKE) setup ARGS="$(ARGS)"

download:
	$(PYTHON) scripts/download.py $(ARGS)

download-raw:
	$(PYTHON) scripts/download.py --download-source raw $(ARGS)

convert:
	$(PYTHON) scripts/convert.py $(ARGS)

package-zenodo:
	$(PYTHON) scripts/package_xarray_archive.py $(ARGS)

test:
	$(UV_RUN) pytest $(ARGS)

clean: clean-safe

clean-safe: clean-build clean-cache

clean-build:
	rm -rf build dist htmlcov .pytest_cache .coverage .coverage.* .mypy_cache .ruff_cache .nox .tox

clean-cache:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

# Removes downloaded/generated model data. Recreates keep files for empty dirs.
clean-data:
	rm -rf data/raw data/processed
	mkdir -p data/raw data/processed
	touch data/raw/.gitkeep data/processed/.gitkeep

clean-all: clean-safe clean-data

distclean: clean-all