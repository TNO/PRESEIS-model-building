UV_RUN ?= uv run
PYTHON ?= $(UV_RUN) python
ARGS ?=
BASE_BRANCH ?= main
STAGING_BRANCH ?= github_staging
EXCLUDE_FILE ?= .github-staging-exclude
README_RENAME_TARGET ?= README.md

.PHONY: help bootstrap bootstrap-with-uv setup setup-raw setup-xarray download download-raw convert package-zenodo test setup-git-hooks refresh-github-staging
.PHONY: clean clean-safe clean-build clean-cache clean-data clean-all distclean
.PHONY: check-git-hooks-files check-github-staging-files

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
	  'make setup-git-hooks Configure local git hooks and safe push defaults (internal branches only)' \
	  'make refresh-github-staging Build github_staging from BASE_BRANCH with exclusions and README policy (internal branches only)' \
	  'make test            Run the test suite' \
	  '' \
	  'Pass extra CLI args with ARGS="..."'

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

check-git-hooks-files:
	@if [ ! -f .githooks/pre-push ]; then \
	  echo "Git hook facility is not available on this branch/worktree."; \
	  echo "Missing required file: .githooks/pre-push"; \
	  echo "This is expected on GitHub/public staging branches where maintainer tooling is excluded."; \
	  echo "Switch to an internal development branch to use: make setup-git-hooks"; \
	  exit 1; \
	fi

check-github-staging-files:
	@if [ ! -f scripts/refresh_github_staging.sh ] || [ ! -f .github-staging-exclude ]; then \
	  echo "github_staging refresh facility is not available on this branch/worktree."; \
	  echo "Missing required files: scripts/refresh_github_staging.sh and/or .github-staging-exclude"; \
	  echo "This is expected on GitHub/public staging branches where maintainer tooling is excluded."; \
	  echo "Switch to an internal development branch to use: make refresh-github-staging"; \
	  exit 1; \
	fi

setup-git-hooks: check-git-hooks-files
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-push
	git config remote.pushDefault origin
	@printf '%s\n' 'Configured .githooks and set remote.pushDefault=origin'

refresh-github-staging: check-github-staging-files
	./scripts/refresh_github_staging.sh $(BASE_BRANCH) $(STAGING_BRANCH) $(EXCLUDE_FILE) $(README_RENAME_TARGET)

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