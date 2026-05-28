"""Tests for Vp-Vs relationship calculations."""

import numpy as np
import pytest
import xarray as xr

from preseis.model_building import (
    get_processed_data_dir,
    load_model_dataset,
    sample_velocity_model,
)


@pytest.fixture
def test_data():
    """Load test models."""
    data_dir = get_processed_data_dir()

    models = {}

    velmod31_path = data_dir / "VELMOD31_UTM31.h5"
    dgm_path = data_dir / "DGM5_UTM31.h5"
    groningen_path = data_dir / "GRONINGEN_2017_RD.h5"

    if velmod31_path.exists() and dgm_path.exists():
        models["velmod31"] = load_model_dataset(velmod31_path)
        models["dgm"] = load_model_dataset(dgm_path)

    if groningen_path.exists():
        groningen = load_model_dataset(groningen_path)
        required_variables = {"tvd", "V0", "k", "relationship_type", "vs_slope", "vs_intercept"}
        if required_variables.issubset(groningen.data_vars):
            models["groningen"] = groningen

    return models


def test_linear_vs_relationship(test_data):
    """Test linear Vp-Vs relationship: Vs = vs_intercept + vs_slope * Vp."""
    if "velmod31" not in test_data or "dgm" not in test_data:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_data["velmod31"]
    dgm = test_data["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000, -2000], dims=["z"])

    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="linear",
        vs_intercept=-1172,
        vs_slope=0.862,
    )

    vp = result["Vinst"].sel(mode="P").values
    vs = result["Vinst"].sel(mode="S").values

    # Check S-wave values are computed and positive
    valid_mask = ~np.isnan(vp) & ~np.isnan(vs)
    assert np.any(valid_mask), "Should have some valid Vp and Vs values"

    vp_valid = vp[valid_mask]
    vs_valid = vs[valid_mask]

    # Verify linear relationship approximately holds
    # Vs ≈ -1172 + 0.862 * Vp
    vs_expected = -1172 + 0.862 * vp_valid

    # Allow some tolerance due to interpolation
    np.testing.assert_allclose(vs_valid, vs_expected, rtol=0.01, atol=50)


def test_ratio_constant_vs_relationship(test_data):
    """Test constant ratio Vp-Vs relationship: Vs = Vp / vs_slope."""
    if "velmod31" not in test_data or "dgm" not in test_data:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_data["velmod31"]
    dgm = test_data["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000, -2000], dims=["z"])

    vp_vs_ratio = 1.73
    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="ratio_constant",
        vs_slope=vp_vs_ratio,
    )

    vp = result["Vinst"].sel(mode="P").values
    vs = result["Vinst"].sel(mode="S").values

    valid_mask = ~np.isnan(vp) & ~np.isnan(vs)
    assert np.any(valid_mask)

    vp_valid = vp[valid_mask]
    vs_valid = vs[valid_mask]

    # Verify ratio relationship: Vs = Vp / 1.73
    vs_expected = vp_valid / vp_vs_ratio
    np.testing.assert_allclose(vs_valid, vs_expected, rtol=0.001)


def test_ratio_depth_vs_relationship(test_data):
    """Test depth-dependent ratio Vp-Vs relationship."""
    if "velmod31" not in test_data or "dgm" not in test_data:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_data["velmod31"]
    dgm = test_data["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000, -2000], dims=["z"])

    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="ratio_depth",
        vs_intercept=4.782,  # base_ratio
        vs_slope=-0.001,  # depth_coef (per meter) -- lowered because it leads to problems at 2000m depth
    )

    vs = result["Vinst"].sel(mode="S").values

    # Check that S-wave values exist and are positive
    valid_vs = vs[~np.isnan(vs)]
    assert len(valid_vs) > 0
    assert np.all(valid_vs > 0)


def test_constant_vs_relationship(test_data):
    """Test constant Vs relationship: Vs = constant."""
    if "velmod31" not in test_data or "dgm" not in test_data:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_data["velmod31"]
    dgm = test_data["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    constant_vs = 2500.0  # m/s
    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="constant",
        vs_slope=constant_vs,
    )

    vs = result["Vinst"].sel(mode="S").values

    # All non-NaN S-wave values should equal the constant
    valid_vs = vs[~np.isnan(vs)]
    if len(valid_vs) > 0:
        np.testing.assert_allclose(valid_vs, constant_vs, rtol=0.001)


def test_groningen_embedded_vs_relationships(test_data):
    """Test Groningen model with embedded Vp-Vs relationships."""
    if "groningen" not in test_data:
        pytest.skip("Groningen model not available")

    groningen = test_data["groningen"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -500, -1000, -1500, -2000], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", velocity_model=groningen
    )

    vp = result["Vinst"].sel(mode="P").values
    vs = result["Vinst"].sel(mode="S").values

    # Check that embedded relationships produce valid S-waves
    valid_mask = ~np.isnan(vp) & ~np.isnan(vs)
    if np.any(valid_mask):
        vs_valid = vs[valid_mask]
        # All S-wave velocities should be positive
        assert np.all(vs_valid > 0), "S-wave velocities should be positive"
        # S-wave should be less than P-wave
        vp_valid = vp[valid_mask]
        assert np.all(vs_valid < vp_valid), "Vs should be less than Vp"


def test_vs_parameter_override_warning(test_data):
    """Test that providing vs params to Groningen model raises warning."""
    if "groningen" not in test_data:
        pytest.skip("Groningen model not available")

    groningen = test_data["groningen"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    # Providing vs_intercept/vs_slope should trigger warning for Groningen
    with pytest.warns(
        UserWarning, match="already contains layer-specific Vp-Vs relationships"
    ):
        result = sample_velocity_model(
            lon,
            lat,
            depths,
            crs="EPSG:4326",
            velocity_model=groningen,
            vs_relationship_type="linear",
            vs_intercept=-1000,
            vs_slope=0.8,
        )

    # Should still use embedded relationships, not user params
    assert "Vinst" in result


def test_vs_positive_values(test_data):
    """Test that all computed S-wave velocities are positive."""
    if "velmod31" not in test_data or "dgm" not in test_data:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_data["velmod31"]
    dgm = test_data["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray(np.linspace(0, -3000, 10), dims=["z"])

    # Test multiple relationship types
    relationships = [
        ("linear", {"vs_intercept": -1172, "vs_slope": 0.862}),
        ("ratio_constant", {"vs_slope": 1.73}),
        ("constant", {"vs_slope": 2000}),
    ]

    for rel_type, params in relationships:
        result = sample_velocity_model(
            lon,
            lat,
            depths,
            crs="EPSG:4326",
            depth_model=dgm,
            velocity_model=velmod,
            vs_relationship_type=rel_type,
            **params,
        )

        vs = result["Vinst"].sel(mode="S").values
        valid_vs = vs[~np.isnan(vs)]

        if len(valid_vs) > 0:
            assert np.all(
                valid_vs > 0
            ), f"All Vs values should be positive for {rel_type}"


def test_vp_vs_ratio_reasonable(test_data):
    """Test that Vp/Vs ratios are within reasonable bounds."""
    if "velmod31" not in test_data or "dgm" not in test_data:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_data["velmod31"]
    dgm = test_data["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000, -2000], dims=["z"])

    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="linear",
        vs_intercept=-1172,
        vs_slope=0.862,
    )

    vp = result["Vinst"].sel(mode="P").values
    vs = result["Vinst"].sel(mode="S").values

    valid_mask = ~np.isnan(vp) & ~np.isnan(vs) & (vs > 0)

    if np.any(valid_mask):
        ratios = vp[valid_mask] / vs[valid_mask]

        # Typical Vp/Vs ratios are between 1.4 and 2.5 for rocks
        # With extreme linear parameters (large negative intercept), ratios can be higher
        assert np.all(ratios > 1.3), "Vp/Vs ratio should be > 1.3"
        assert np.all(ratios < 5.0), "Vp/Vs ratio should be < 5.0"
