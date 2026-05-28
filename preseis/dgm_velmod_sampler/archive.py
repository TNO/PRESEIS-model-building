"""Compatibility archive module for the legacy PRESEIS import path."""

from ..model_building.archive import (
    get_archive_output_dir,
    stage_processed_models_for_archive,
)

__all__ = [
    "get_archive_output_dir",
    "stage_processed_models_for_archive",
]