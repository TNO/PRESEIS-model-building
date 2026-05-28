"""Utility functions for path management, configuration, and model I/O."""

from pathlib import Path
from typing import Optional, Union

import xarray as xr
import yaml


MODEL_DATASET_ENGINE = "h5netcdf"


def _resolve_config(config: Optional[dict] = None, config_path: Optional[Union[str, Path]] = None) -> dict:
    """Return an explicit config dict or load one from disk."""
    return config if config is not None else load_config(config_path)


def get_package_root() -> Path:
    """
    Get the package root directory for the PRESEIS model-building repository.

    Returns
    -------
    Path
        Package root directory
    """
    # Go up from the package implementation directory -> preseis -> repository root.
    return Path(__file__).parent.parent.parent


def get_data_dir():
    """
    Get the data directory, creating it if needed.

    Returns
    -------
    Path
        Data directory
    """
    data_dir = get_package_root() / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_raw_data_dir():
    """
    Get the raw data directory, creating it if needed.

    Returns
    -------
    Path
        Raw data directory (for downloaded files)
    """
    raw_dir = get_data_dir() / "raw"
    raw_dir.mkdir(exist_ok=True)
    return raw_dir


def get_processed_data_dir():
    """
    Get the processed data directory, creating it if needed.

    Returns
    -------
    Path
        Processed data directory (for converted .h5 files)
    """
    proc_dir = get_data_dir() / "processed"
    proc_dir.mkdir(exist_ok=True)
    return proc_dir


def get_config_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Get the path to the configuration file.

    Parameters
    ----------
    config_path : str or Path, optional
        Path to config file. If None, defaults to config/config.yaml.

    Returns
    -------
    Path
        Path to config file
    """
    if config_path is not None:
        return Path(config_path)
    return get_package_root() / "config" / "config.yaml"


def load_config(config_path: Optional[Union[str, Path]] = None) -> dict:
    """
    Load the configuration file (YAML).

    Parameters
    ----------
    config_path : str or Path, optional
        Path to config file. If None, defaults to config/config.yaml.

    Returns
    -------
    dict
        Configuration dictionary with model definitions
    """
    config_file = get_config_path(config_path)
    with open(config_file) as f:
        return yaml.safe_load(f)


def _normalize_loaded_model_dataset(dataset: xr.Dataset) -> xr.Dataset:
    """Normalize loaded model datasets across supported backends."""
    if "spatial_ref" in dataset and "spatial_ref" not in dataset.coords:
        dataset = dataset.set_coords("spatial_ref")
    return dataset


def open_model_dataset(
    model_path: Union[str, Path],
    *,
    decode_coords: Optional[str] = "all",
    engine: str = MODEL_DATASET_ENGINE,
    fallback_to_default: bool = True,
    **kwargs,
) -> xr.Dataset:
    """Open a processed model dataset, preferring the canonical h5netcdf backend."""
    model_path = Path(model_path)
    open_kwargs = dict(kwargs)
    if decode_coords is not None:
        open_kwargs["decode_coords"] = decode_coords

    try:
        dataset = xr.open_dataset(model_path, engine=engine, **open_kwargs)
    except (OSError, RuntimeError, ValueError):
        if not fallback_to_default or engine != MODEL_DATASET_ENGINE:
            raise
        dataset = xr.open_dataset(model_path, **open_kwargs)

    return _normalize_loaded_model_dataset(dataset)


def load_model_dataset(
    model_path: Union[str, Path],
    *,
    decode_coords: Optional[str] = "all",
    engine: str = MODEL_DATASET_ENGINE,
    fallback_to_default: bool = True,
    **kwargs,
) -> xr.Dataset:
    """Load a processed model dataset and normalize its geospatial metadata."""
    dataset = open_model_dataset(
        model_path,
        decode_coords=decode_coords,
        engine=engine,
        fallback_to_default=fallback_to_default,
        **kwargs,
    )
    dataset.load()
    dataset.close()
    return dataset


def get_public_model_name(
    model_key: str,
    config: Optional[dict] = None,
    config_path: Optional[Union[str, Path]] = None,
) -> str:
    """Return the public CLI-facing name for a configured model."""
    config = _resolve_config(config=config, config_path=config_path)
    if model_key not in config["models"]:
        raise KeyError(f"Model '{model_key}' not found")

    model_config = config["models"][model_key]
    if not model_key.startswith("velmod"):
        return model_key

    version = model_config.get("version")
    if version:
        return f"velmod-{version}"

    suffix = model_key.removeprefix("velmod")
    if not suffix.isdigit():
        return model_key
    if len(suffix) == 1:
        return f"velmod-{suffix}"
    return f"velmod-{suffix[0]}.{suffix[1:]}"


def get_available_model_names(
    config: Optional[dict] = None,
    config_path: Optional[Union[str, Path]] = None,
    include_variants: bool = True,
) -> list:
    """Return the supported public model names in configuration order."""
    config = _resolve_config(config=config, config_path=config_path)
    model_names = [
        get_public_model_name(model_key, config=config)
        for model_key in config["models"].keys()
    ]

    if include_variants and "groningen" in config["models"]:
        model_names.append("groningen-no-anhydrite")

    return model_names


def normalize_model_name(
    model_name: str,
    config: Optional[dict] = None,
    config_path: Optional[Union[str, Path]] = None,
) -> str:
    """Resolve a public model name or config key to the underlying config key."""
    config = _resolve_config(config=config, config_path=config_path)

    if model_name in config["models"]:
        return model_name

    if model_name.endswith("-no-anhydrite"):
        base_model_name = model_name.removesuffix("-no-anhydrite")
        if base_model_name in config["models"]:
            return base_model_name

    for model_key in config["models"].keys():
        if model_name == get_public_model_name(model_key, config=config):
            return model_key

    return model_name


def get_default_model_names(
    config: Optional[dict] = None,
    config_path: Optional[Union[str, Path]] = None,
) -> list:
    """Return the default public model names for setup workflows."""
    return get_available_model_names(
        config=config,
        config_path=config_path,
        include_variants=True,
    )


def expand_model_dependencies(
    model_names,
    config: Optional[dict] = None,
    config_path: Optional[Union[str, Path]] = None,
) -> list:
    """Expand requested public model names with configured dependencies."""
    config = _resolve_config(config=config, config_path=config_path)
    expanded = []

    for model_name in model_names:
        if model_name not in expanded:
            expanded.append(model_name)

        model_key = normalize_model_name(model_name, config=config)
        if model_key not in config["models"]:
            continue

        for dependency_key in config["models"][model_key].get("requires", []):
            dependency_name = get_public_model_name(dependency_key, config=config)
            if dependency_name not in expanded:
                expanded.append(dependency_name)

    return expanded


def get_model_output_file(
    model_name: str,
    config: Optional[dict] = None,
    config_path: Optional[Union[str, Path]] = None,
) -> str:
    """Return the processed output filename for a public model name or config key."""
    config = _resolve_config(config=config, config_path=config_path)
    model_key = normalize_model_name(model_name, config=config)
    if model_key not in config["models"]:
        available = get_available_model_names(config=config)
        raise KeyError(f"Model '{model_name}' not found. Available models: {available}")

    output_file = config["models"][model_key]["output_file"]
    if model_name.endswith("-no-anhydrite"):
        return output_file.replace(".h5", "_no_anhydrite.h5")
    return output_file


def get_model_config(model_key: str, config_path: Optional[Union[str, Path]] = None) -> dict:
    """
    Get configuration for a specific model.

    Parameters
    ----------
    model_key : str
        Model key (e.g., "dgm", "velmod31", "velmod32")
    config_path : str or Path, optional
        Path to config file. If None, defaults to config/config.yaml.

    Returns
    -------
    dict
        Model configuration

    Raises
    ------
    KeyError
        If model_key is not found in configuration
    """
    config = load_config(config_path)
    if model_key not in config["models"]:
        available = list(config["models"].keys())
        raise KeyError(f"Model '{model_key}' not found. Available: {available}")
    return config["models"][model_key]


def get_velmod_config(version: str, config_path: Optional[Union[str, Path]] = None) -> dict:
    """
    Get configuration for a VELMOD version.

    Parameters
    ----------
    version : str
        VELMOD version (e.g., "3.1", "3.2")
    config_path : str or Path, optional
        Path to config file. If None, defaults to config/config.yaml.

    Returns
    -------
    dict
        VELMOD configuration

    Raises
    ------
    ValueError
        If version is not configured
    """
    model_key = f"velmod{version.replace('.', '')}"
    config = load_config(config_path)

    if model_key not in config["models"]:
        available_versions = [
            k.replace("velmod", "").replace("31", "3.1").replace("32", "3.2")
            for k in config["models"].keys()
            if k.startswith("velmod")
        ]
        raise ValueError(
            f"VELMOD version {version} not configured. Available: {available_versions}"
        )

    return config["models"][model_key]
