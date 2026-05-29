# Development Notes

This document covers maintainer-only workflows. User-facing setup and usage stay in [README.md](../README.md).

## Naming

Adopted outward-facing position in the PRESEIS portfolio:

- Portfolio area: `preseis.model_building`
- Capability/package-facing name: `model_building`
- Distribution/package-facing name: `preseis-model-building`
- Zenodo xarray archive name: `preseis-model-building-xarray-models.zip`

Rationale:

- The package name should describe the durable PRESEIS capability, not the current source models.
- Model families such as DGM, VELMOD, and Groningen should enter through configuration, not through the package or artifact name.
- `model_building` is broad enough to last if the current layer-cake style gridding workflow grows into adjacent model-building tasks.

The preferred Python import path is `preseis.model_building`. The compatibility import path `preseis.dgm_velmod_sampler` remains available until a separate migration removes it.

## Zenodo Archive Workflow

The processed xarray/HDF5 archive is staged into `build/zenodo/`, which is already ignored by git.

1. Generate or collect processed `.h5` files in `data/processed/`.
2. Stage the archive files:

```bash
uv run python scripts/package_xarray_archive.py
```

Optional flags:

```bash
# Use a different processed source directory
uv run python scripts/package_xarray_archive.py --processed-dir /path/to/processed

# Fail if any expected archive file is missing
uv run python scripts/package_xarray_archive.py --strict

# Exclude optional variants
uv run python scripts/package_xarray_archive.py --no-variants
```

The staging command writes:

- `build/zenodo/staged-files/` with the copied `.h5` payloads
- `build/zenodo/manifest.json` with staged and missing files
- `build/zenodo/README.txt` with a quick summary
- `build/zenodo/preseis-model-building-xarray-models.zip` when at least one processed file is available

The current published archive URL is configured in [config/config.yaml](../config/config.yaml). Update it when you publish a new Zenodo record.

### Suggested Zenodo Description

Use a short provenance block that points to one project landing page for source-model references:

```text
This archive contains preconverted xarray/HDF5 derivative products for PRESEIS Model Building and allows users to skip the raw download and conversion workflow. It currently packages processed forms of DGM-deep V5, VELMOD-3.1, VELMOD-3.2, VELMOD-4, and Groningen 2017.

Official source model landing pages and references are collected on the project landing page:
<project-readme-url>#source-data-and-references
```

Replace `<project-readme-url>` with the public README URL for the repository when you publish the Zenodo record.

## Make Targets

Optional convenience targets are provided in [Makefile](../Makefile).

```bash
make help
make setup
make setup-xarray ARGS="--version velmod-3.1 --zenodo-url <archive-url>"
make package-zenodo
```

The `make` layer is only a thin wrapper around the Python scripts. The Python CLIs remain the primary interface.