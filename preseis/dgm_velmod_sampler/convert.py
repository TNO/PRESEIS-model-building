"""Compatibility conversion module for the legacy PRESEIS import path."""

from ..model_building.convert import (
    convert_dgm,
    convert_groningen,
    convert_velmod,
)

__all__ = [
    "convert_dgm",
    "convert_groningen",
    "convert_velmod",
]