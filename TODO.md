# TODO

## In Progress

- Add direct Zenodo-backed downloads for preconverted xarray/HDF5 model files and wire them through the setup/download scripts.
- Keep setup/download scoped to the requested models instead of always fetching every archive.
- Harden archive extraction while touching the download path.

## Next

- Fix deprecated `sample_dgm_velmod()` positional compatibility so legacy callers do not swap DGM and VELMOD inputs.
- Make Groningen conversion honor `remove_anhydrite` instead of always building both variants.
- Ensure custom processed output directories are created before conversion writes files.
- Tighten CLI/documentation consistency around model flags and setup flows.

## Backlog

- Clean up and streamline the example notebooks.