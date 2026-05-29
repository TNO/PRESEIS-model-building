# PRESEIS Model Building

## Description

This package provides PRESEIS model-building functionality for layered subsurface models configured through data and metadata files. The current configuration covers DGM-deep V5, VELMOD 3.1, VELMOD 3.2, VELMOD 4, and Groningen 2017. Official source pages and references are collected in [Source Data and References](#source-data-and-references).

**K-factor parameterization:**
The velocity models use a linear depth parameterization: V(z) = V₀ + k·z, where V₀ is the velocity at the top of each stratigraphic unit and k is the velocity gradient. The k-values in [config/velmod31_k.csv](config/velmod31_k.csv), [config/velmod32_k.csv](config/velmod32_k.csv), and [config/velmod4_k.csv](config/velmod4_k.csv) have been manually extracted from the technical reports (see [config/README.md](config/README.md) for details).

## Installation

Install the package in editable mode using uv:

```bash
uv pip install -e .

# Or with development dependencies
uv pip install -e ".[dev]"
```

Or use Makefile bootstrap targets:

```bash
# Create .venv and install project + dev dependencies (requires uv already installed)
make bootstrap

# Install uv first if missing, then bootstrap the environment
make bootstrap-with-uv
```

For notebooks, register a project-specific kernel display name:

```bash
python -m ipykernel install --user --name preseis-model-building --display-name "PRESEIS Model Building"
```

The distribution name is `preseis-model-building`. The preferred Python import path is `preseis.model_building`, and the compatibility import path `preseis.dgm_velmod_sampler` remains available.

## Setup

### Quick Start (Make-Centered, Recommended)

```bash
# Install uv if needed and bootstrap environment
make bootstrap-with-uv

# Or bootstrap directly if uv is already installed
make bootstrap

# Default setup: download preconverted xarray/HDF5 files from Zenodo
make setup

# Optional verification
make test
```

This default setup downloads preconverted xarray/HDF5 model files from Zenodo into `data/processed/`.

### Direct UV Workflow

If you prefer direct `uv` commands instead of `make`, use:

```bash
# Install project with development dependencies
uv pip install -e ".[dev]"

# Default setup: download preconverted xarray/HDF5 files from Zenodo
uv run python scripts/setup_data.py

# Optional verification
uv run pytest
```

### Advanced Documentation

- Full setup options (raw vs xarray, subsets, force behavior, manual download/convert flows) are in [README_ADVANCED.md](docs/README_ADVANCED.md).

## Usage

After setup, use the models in your code:

```python
from preseis.model_building import (
  get_processed_data_dir,
  load_model_dataset,
  sample_velocity_model,
)

# Load models
data_dir = get_processed_data_dir()
dgm = load_model_dataset(data_dir / "DGM5_UTM31.h5")

# Load specific VELMOD version
velmod31 = load_model_dataset(data_dir / "VELMOD31_UTM31.h5")
velmod32 = load_model_dataset(data_dir / "VELMOD32_UTM31.h5")
velmod4 = load_model_dataset(data_dir / "VELMOD4_UTM31.h5")

# Sample at specific locations and depths
samples = sample_velocity_model(x, y, z, depth_model=dgm, velocity_model=velmod31)

# Request both P-wave and S-wave output for VELMOD using a Vp-Vs relationship
samples_with_s = sample_velocity_model(
  x,
  y,
  z,
  depth_model=dgm,
  velocity_model=velmod31,
  vs_relationship_type="linear",
  vs_intercept=-1172.0,
  vs_slope=0.862,
)
print(samples_with_s["Vinst"].coords["mode"].values)  # ['P', 'S']
```

S-wave sampling is already supported:
- Groningen uses the embedded layer-specific Vp-Vs parameters in the processed model files.
- VELMOD models can return both P-wave and S-wave samples when you provide a relationship through `vs_relationship_type`, `vs_intercept`, and `vs_slope`.

Notebook examples:

- [notebooks/examples.ipynb](notebooks/examples.ipynb): current primary example notebook.
- [notebooks/examples_reboot_legacy.ipynb](notebooks/examples_reboot_legacy.ipynb): restored legacy notebook from the reboot branch, updated to use `data/processed/` paths.

### VELMOD Version Comparison

| Version | Year | Grid Resolution | File Size | Key Features |
|---------|------|----------------|-----------|--------------|
| 3.1 | 2017 | 316 x 556 | ~239 MB | Original regional model |
| 3.2 | 2024 | 316 x 556 | ~537 MB | Updated with improved accuracy |
| 4 | 2020 | 316 x 556 | ~1.3 GB | Integrated seismic stacking velocities, better lateral variations |

All versions use UTM31N coordinate system and include V₀ (top velocity) and k (velocity gradient) for each stratigraphic unit.

#### VELMOD 4 Combined Units

VELMOD 4 provides some stratigraphic units as combined layers in the source data:
- **RN+RB** (Rijnland + Roer Base) → mapped to **RN** in the processed dataset
- **S+AT** (Scruff + Altena) → mapped to **S** in the processed dataset

This mapping is applied automatically during conversion. The k-values for these units are taken from the dominant formation (RN for RN+RB, S for S+AT). See [config/velmod4_k.csv](config/velmod4_k.csv) for details.

## Configuration

Download URLs are specified in [config/config.yaml](config/config.yaml).
To enable direct processed downloads, set `xarray_archive.url` to the archive URL that contains the preconverted `.h5` model files.
Use `load_model_dataset(...)` to open processed model files so the package picks the supported backend and normalizes geospatial metadata for you.

## Source Data and References

This package converts and packages derivative products from the official source models. For concise provenance, use the official landing/reference page for each source model below.

- [DGM-deep V5 details and workflow](https://www.nlog.nl/en/details-dgm-deep-v5)
- [DGM-deep V5 download page](https://www.nlog.nl/en/dgm-deep-v5-and-offshore)
- [VELMOD-3.1 official page](https://www.nlog.nl/en/velmod-31)
- [VELMOD-3.2 official page](https://www.nlog.nl/en/velmod-32)
- [VELMOD-4 official page](https://www.nlog.nl/en/velmod-4)
- [Groningen 2017 official reference report](https://nam-onderzoeksrapporten.data-app.nl/reports/download/groningen/en/9a5751d9-2ff5-4b6a-9c25-e37e76976bc1)

The NLOG landing pages link onward to the corresponding technical reports, appendices, and downloadable source grids. The Groningen model is referenced here through the official NAM report link used by this project.

## Testing

Run tests with:

```bash
uv run pytest tests/
```

## Support

Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap

At some point, the package may include code for the generation of random realizations of velocities within the uncertainty specifications of VELMOD and related uncertainty-aware workflows.

## License

Copyright (c) 2023-2026 TNO.

Licensed under the European Union Public Licence v. 1.2 (EUPL-1.2). See [LICENSE](LICENSE).
