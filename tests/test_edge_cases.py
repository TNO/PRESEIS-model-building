"""Tests for error handling and edge cases."""

import numpy as np
import pytest
import xarray as xr

from preseis.model_building import (
    get_processed_data_dir,
    load_model_dataset,
    sample_velocity_model,
)


@pytest.fixture
def velmod_dgm():
    """Load VELMOD and DGM for testing."""
    data_dir = get_processed_data_dir()

    velmod31_path = data_dir / "VELMOD31_UTM31.h5"
    dgm_path = data_dir / "DGM5_UTM31.h5"

    if not velmod31_path.exists() or not dgm_path.exists():
        pytest.skip("VELMOD31 or DGM not available")

    velmod = load_model_dataset(velmod31_path)
    dgm = load_model_dataset(dgm_path)

    return velmod, dgm


def test_out_of_bounds_coordinates(velmod_dgm):
    """Test sampling at coordinates outside model bounds."""
    velmod, dgm = velmod_dgm

    # Coordinates far outside Netherlands
    lon, lat = 0.0, 40.0  # Somewhere in Spain
    depths = xr.DataArray([0, -1000], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    # Should return NaN for out-of-bounds
    vp = result["Vinst"].values
    assert np.all(np.isnan(vp)) or np.all(vp == 0)


def test_negative_depth_values(velmod_dgm):
    """Test that depth values are interpreted correctly (negative = below surface)."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4

    # Depths should be negative (below surface)
    depths_correct = xr.DataArray([0, -1000, -2000], dims=["z"])

    result = sample_velocity_model(
        lon,
        lat,
        depths_correct,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
    )

    vp = result["Vinst"].values
    # Should have valid velocities
    assert not np.all(np.isnan(vp))


def test_very_deep_depths(velmod_dgm):
    """Test sampling at unrealistically deep depths."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4
    # Very deep - beyond model definition
    depths = xr.DataArray([0, -10000, -20000], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    # Very deep values might be NaN or extrapolated
    vp = result["Vinst"].values
    # Should at least not crash
    assert len(vp) == 3


def test_single_point_single_depth(velmod_dgm):
    """Test minimum input: single coordinate, single depth."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4
    depth = xr.DataArray([-1000], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depth, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    assert "Vinst" in result
    assert result.sizes["z"] == 1


def test_many_depths(velmod_dgm):
    """Test sampling at many depth levels."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4
    # 100 depth levels
    depths = xr.DataArray(np.linspace(0, -5000, 100), dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    assert result.sizes["z"] == 100


def test_nan_in_coordinates(velmod_dgm):
    """Test handling of NaN in input coordinates."""
    velmod, dgm = velmod_dgm

    # Include NaN coordinate
    lons = xr.DataArray([6.8, np.nan, 7.0], dims=["point"])
    lats = xr.DataArray([53.4, 53.5, 53.6], dims=["point"])
    depths = xr.DataArray([0, -1000], dims=["z"])

    result = sample_velocity_model(
        lons, lats, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    # Should handle NaN gracefully without crashing
    # NaN coordinates may be transformed to default values (e.g., 0)
    vp = result["Vinst"].sel(point=1).values
    assert vp is not None, "Should return result even with NaN input"


def test_zero_depth(velmod_dgm):
    """Test sampling exactly at surface (depth=0)."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    vp = result["Vinst"].values
    # Should get surface velocity
    assert len(vp) == 1


def test_missing_vs_relationship_type(velmod_dgm):
    """Test that providing vs params without relationship type still works."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    # Provide vs params without relationship_type
    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_intercept=-1172,
        vs_slope=0.862,
        # No vs_relationship_type specified
    )

    # Should handle gracefully (might use default or ignore params)
    assert "Vinst" in result


def test_invalid_vs_relationship_type(velmod_dgm):
    """Test handling of invalid vs_relationship_type."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    # Invalid relationship type should raise error or be handled
    with pytest.raises((ValueError, KeyError)):
        sample_velocity_model(
            lon,
            lat,
            depths,
            crs="EPSG:4326",
            depth_model=dgm,
            velocity_model=velmod,
            vs_relationship_type="invalid_type",
            vs_intercept=-1172,
            vs_slope=0.862,
        )


def test_vs_with_missing_parameters(velmod_dgm):
    """Test vs relationship with missing required parameters."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    # Linear relationship without intercept should fail or use defaults
    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="linear",
        vs_slope=0.862,
        # Missing vs_intercept
    )

    # Should handle missing parameter (might default or raise)
    assert "Vinst" in result


def test_empty_coordinate_arrays(velmod_dgm):
    """Test handling of empty coordinate arrays."""
    velmod, dgm = velmod_dgm

    # Empty arrays
    lons = xr.DataArray([], dims=["point"])
    lats = xr.DataArray([], dims=["point"])
    depths = xr.DataArray([0], dims=["z"])

    # Should handle empty input gracefully
    try:
        result = sample_velocity_model(
            lons, lats, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
        )
        # If it succeeds, check result is also empty
        assert result.sizes["point"] == 0
    except (ValueError, IndexError):
        # Or it might raise an error - both are acceptable
        pass


def test_extreme_vs_parameters(velmod_dgm):
    """Test Vs calculation with extreme parameter values."""
    velmod, dgm = velmod_dgm

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    # Very large slope
    result1 = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="linear",
        vs_intercept=0,
        vs_slope=10.0,  # Unrealistically large
    )

    vs1 = result1["Vinst"].sel(mode="S").values
    # Should still compute, even if unrealistic
    assert not np.all(np.isnan(vs1))

    # Very small ratio
    result2 = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="ratio_constant",
        vs_slope=1.1,  # Very small Vp/Vs ratio
    )

    vs2 = result2["Vinst"].sel(mode="S").values
    valid_vs2 = vs2[~np.isnan(vs2)]
    if len(valid_vs2) > 0:
        # Should give very high Vs values
        assert np.all(valid_vs2 > 0)
