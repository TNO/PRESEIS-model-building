# PRESEIS Model Building Advanced Guide

This document collects advanced setup and model options. For day-to-day onboarding, start with [README.md](../README.md).

## Setup Options (UV)

Default behavior is xarray/Zenodo-based setup:

```bash
# Download processed xarray/HDF5 files for all default models
uv run python scripts/setup_data.py

# Download only selected models from the processed archive
uv run python scripts/setup_data.py --version velmod-3.1
uv run python scripts/setup_data.py --version velmod-3.2
uv run python scripts/setup_data.py --version velmod-4
uv run python scripts/setup_data.py --version groningen
uv run python scripts/setup_data.py --version dgm
```

This path:
1. Downloads the processed archive configured in [config/config.yaml](../config/config.yaml)
2. Extracts requested .h5 files into data/processed/
3. Skips conversion because files are already processed

### Explicit Xarray Setup

```bash
uv run python scripts/setup_data.py --download-source xarray
uv run python scripts/setup_data.py --download-source xarray --zenodo-url <zenodo-archive-url>
uv run python scripts/setup_data.py --download-source xarray --version velmod-3.1
```

### Raw Source Setup (Advanced)

```bash
# Download raw source archives and convert to .h5
uv run python scripts/setup_data.py --download-source raw

# Raw source build for a subset
uv run python scripts/setup_data.py --download-source raw --version velmod-4
```

### Force Behavior

```bash
# Force re-download with default xarray source
uv run python scripts/setup_data.py --force

# Force raw-source re-download and reconversion for a specific version
uv run python scripts/setup_data.py --download-source raw --version velmod-4 --force
```

## Manual Download/Convert Flow

```bash
# Download only (default: processed xarray from Zenodo)
uv run python scripts/download.py

# Download only a subset of raw models
uv run python scripts/download.py --download-source raw --model velmod-3.1 dgm

# Download processed xarray files from Zenodo
uv run python scripts/download.py --download-source xarray --zenodo-url <zenodo-archive-url>

# Convert only (requires data to be downloaded first)
uv run python scripts/convert.py --model velmod-3.1  # or velmod-3.2, velmod-4, groningen, dgm

# Force re-download or reconvert
uv run python scripts/download.py --force
uv run python scripts/convert.py --model velmod-3.2 --force
```

## Make Equivalents

```bash
# xarray default
make setup

# raw source setup
make setup-raw

# xarray-only alias
make setup-xarray

# download workflows
make download
make download-raw
```

## Data Outputs

Data is stored in:
- data/raw/ for downloaded ZIP/TAR and extracted source grids
- data/processed/ for processed .h5 files

Typical outputs include:
- DGM5_UTM31.h5
- VELMOD31_UTM31.h5
- VELMOD32_UTM31.h5
- VELMOD4_UTM31.h5
- GRONINGEN_2017_RD.h5

## Groningen 2017 Notes

Convert Groningen directly:

```bash
uv run python scripts/setup_data.py --version groningen
# Or convert only (if raw data is already present):
uv run python scripts/convert.py --model groningen
```

Data sources:
- Velocity model: https://nam-onderzoeksrapporten.data-app.nl
- Technical report: https://nam-onderzoeksrapporten.data-app.nl/reports/download/groningen/en/9a5751d9-2ff5-4b6a-9c25-e37e76976bc1

Model highlights:
- VELMOD4-compatible HDF5 output
- 50m x 50m grid
- Native S-wave data included
- CRS: Amersfoort / RD New (EPSG:28992)

## VELMOD Version Notes

| Version | Year | Grid Resolution | File Size | Key Features |
|---------|------|----------------|-----------|--------------|
| 3.1 | 2017 | 316 x 556 | ~239 MB | Original regional model |
| 3.2 | 2024 | 316 x 556 | ~537 MB | Updated with improved accuracy |
| 4 | 2020 | 316 x 556 | ~1.3 GB | Integrated seismic stacking velocities, better lateral variations |

VELMOD 4 combined-unit handling in conversion:
- RN+RB is mapped to RN
- S+AT is mapped to S

See [config/velmod4_k.csv](../config/velmod4_k.csv) and [config/config.yaml](../config/config.yaml) for details.
