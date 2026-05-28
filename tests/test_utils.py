"""Tests for utility functions."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest

import preseis.dgm_velmod_sampler as legacy_model_building
import preseis.model_building as model_building
import preseis.model_building.examples
from preseis.model_building.utils import (
    expand_model_dependencies,
    get_available_model_names,
    get_config_path,
    get_data_dir,
    get_default_model_names,
    get_model_config,
    get_model_output_file,
    get_package_root,
    get_processed_data_dir,
    get_public_model_name,
    get_raw_data_dir,
    get_velmod_config,
    load_config,
    normalize_model_name,
)


def test_get_package_root():
    """Test that package root returns correct path."""
    root = get_package_root()
    assert root.exists()
    assert root.is_dir()
    # Check that expected directories exist
    assert (root / "preseis").exists()
    assert (root / "config").exists()


def test_get_data_dir():
    """Test data directory creation and retrieval."""
    data_dir = get_data_dir()
    assert data_dir.exists()
    assert data_dir.is_dir()
    assert data_dir.name == "data"


def test_get_raw_data_dir():
    """Test raw data directory creation."""
    raw_dir = get_raw_data_dir()
    assert raw_dir.exists()
    assert raw_dir.is_dir()
    assert raw_dir.name == "raw"
    # Check it's under data/
    assert raw_dir.parent.name == "data"


def test_get_processed_data_dir():
    """Test processed data directory creation."""
    proc_dir = get_processed_data_dir()
    assert proc_dir.exists()
    assert proc_dir.is_dir()
    assert proc_dir.name == "processed"
    # Check it's under data/
    assert proc_dir.parent.name == "data"


def test_make_depth_axis_uses_meter_coordinates_for_plotting():
    """Depth helper should keep sampling values and expose meter coordinates."""
    depth_axis = preseis.model_building.examples.make_depth_axis(max_depth=5000.0, sample_count=5)

    assert depth_axis.name == "z"
    assert depth_axis.attrs["units"] == "m"
    assert float(depth_axis.isel(z=0).item()) == 0.0
    assert float(depth_axis.isel(z=-1).item()) == -5000.0
    assert float(depth_axis["z"].isel(z=0).item()) == 0.0
    assert float(depth_axis["z"].isel(z=-1).item()) == 5000.0


def test_format_depth_axis_displays_depth_downward():
    """Depth formatting helper should put shallow values at the top of the plot."""
    fig, ax = plt.subplots()

    try:
        depth_axis = preseis.model_building.examples.make_depth_axis(max_depth=5000.0, sample_count=5)
        preseis.model_building.examples.format_depth_axis(ax, depth_axis["z"])

        ymin, ymax = ax.get_ylim()
        assert ymin == 5000.0
        assert ymax == 0.0
        assert ax.get_ylabel() == "Depth (m)"
    finally:
        plt.close(fig)


def test_make_polyline_section_line_uses_constant_spacing():
    """Polyline sections should be sampled at equal cumulative-distance steps."""
    section = preseis.model_building.examples.make_polyline_section_line(
        [6.60, 6.92, 6.84],
        [53.25, 53.27, 53.39],
        point_count=7,
    )

    distance_km = section["distance_km"].values
    spacing_km = np.diff(distance_km)

    assert section.sizes["inline"] == 7
    assert np.isclose(distance_km[0], 0.0)
    assert np.allclose(spacing_km, spacing_km[0])
    assert np.all(np.diff(distance_km) > 0.0)


def test_make_local_volume_grid_is_centered_on_requested_point():
    """Local volume grids should be square and centered on the requested location."""
    grid = preseis.model_building.examples.make_local_volume_grid(6.8, 53.4, half_width_km=2.0, point_count=5)

    assert grid["longitude"].dims == ("northing_km", "easting_km")
    assert grid["latitude"].dims == ("northing_km", "easting_km")
    assert grid.sizes["easting_km"] == 5
    assert grid.sizes["northing_km"] == 5
    assert np.isclose(float(grid["easting_km"].min().item()), -2.0)
    assert np.isclose(float(grid["easting_km"].max().item()), 2.0)
    assert np.isclose(float(grid["northing_km"].min().item()), -2.0)
    assert np.isclose(float(grid["northing_km"].max().item()), 2.0)
    assert np.isclose(
        float(grid["longitude"].sel(easting_km=0.0, northing_km=0.0).item()),
        6.8,
    )
    assert np.isclose(
        float(grid["latitude"].sel(easting_km=0.0, northing_km=0.0).item()),
        53.4,
    )


def test_get_config_path_default():
    """Test default config path."""
    config_path = get_config_path()
    assert config_path.exists()
    assert config_path.suffix in [".yaml", ".yml"]


def test_preferred_and_compat_import_paths_expose_same_api():
    """Preferred and compatibility import paths should expose the same root API."""
    assert model_building.sample_velocity_model is legacy_model_building.sample_velocity_model
    assert model_building.download_models is legacy_model_building.download_models
    assert model_building.load_model_dataset is legacy_model_building.load_model_dataset


def test_get_config_path_custom():
    """Test custom config path."""
    custom_path = Path("/custom/path/config.yaml")
    result = get_config_path(custom_path)
    assert result == custom_path


def test_load_config():
    """Test loading configuration file."""
    config = load_config()
    assert isinstance(config, dict)
    assert "models" in config
    assert isinstance(config["models"], dict)


def test_get_public_model_name_velmod_alias():
    """Test deriving a public name for a configured VELMOD model."""
    assert get_public_model_name("velmod31") == "velmod-3.1"


def test_get_available_model_names_includes_variant():
    """Test supported public model names are config driven."""
    available_models = get_available_model_names()
    assert "velmod-3.1" in available_models
    assert "groningen-no-anhydrite" in available_models


def test_default_model_names_include_no_anhydrite_variant():
    """Test default setup model names include no-anhydrite variant."""
    default_models = get_default_model_names()
    assert "groningen" in default_models
    assert "groningen-no-anhydrite" in default_models


def test_normalize_model_name_alias():
    """Test public names resolve back to config keys."""
    assert normalize_model_name("velmod-3.1") == "velmod31"
    assert normalize_model_name("groningen-no-anhydrite") == "groningen"


def test_expand_model_dependencies_from_config():
    """Test setup model dependencies come from config."""
    expanded_models = expand_model_dependencies(["velmod-3.1"])
    assert expanded_models == ["velmod-3.1", "dgm"]


def test_get_model_output_file_variant():
    """Test processed output filenames are resolved from config."""
    assert get_model_output_file("velmod-3.1") == "VELMOD31_UTM31.h5"
    assert get_model_output_file("groningen-no-anhydrite") == "GRONINGEN_2017_RD_no_anhydrite.h5"


def test_get_model_config_dgm():
    """Test getting DGM model configuration."""
    dgm_config = get_model_config("dgm")
    assert isinstance(dgm_config, dict)
    assert "name" in dgm_config


def test_get_model_config_invalid():
    """Test that invalid model key raises KeyError."""
    with pytest.raises(KeyError, match="not found"):
        get_model_config("invalid_model_name_xyz")


def test_get_velmod_config_31():
    """Test getting VELMOD 3.1 configuration."""
    config = get_velmod_config("3.1")
    assert isinstance(config, dict)
    assert "name" in config


def test_get_velmod_config_32():
    """Test getting VELMOD 3.2 configuration."""
    config = get_velmod_config("3.2")
    assert isinstance(config, dict)
    assert "name" in config


def test_get_velmod_config_invalid():
    """Test that invalid VELMOD version raises ValueError."""
    with pytest.raises((ValueError, KeyError)):
        get_velmod_config("99.9")
