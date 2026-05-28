"""Compatibility package for the legacy PRESEIS import path."""

from ..model_building import (
    __version__,
    convert_dgm,
    convert_groningen,
    convert_velmod,
    download_models,
    get_processed_data_dir,
    get_raw_data_dir,
    load_model_dataset,
    sample_velocity_model,
)

__all__ = [
    "sample_velocity_model",
    "download_models",
    "convert_dgm",
    "convert_velmod",
    "convert_groningen",
    "get_processed_data_dir",
    "get_raw_data_dir",
    "load_model_dataset",
]
