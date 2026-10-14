"""Advanced tests for velocity sampling functionality."""

import numpy as np
import pytest
import xarray as xr

from preseis.model_building import (
    get_processed_data_dir,
    load_model_dataset,
    sample_velocity_model,
)


@pytest.fixture
def test_models():
    """Load test models."""
    data_dir = get_processed_data_dir()

    # Load available models
    models = {}

    velmod31_path = data_dir / "VELMOD31_UTM31.h5"
    if velmod31_path.exists():
        models["velmod31"] = load_model_dataset(velmod31_path)

    velmod32_path = data_dir / "VELMOD32_UTM31.h5"
    if velmod32_path.exists():
        models["velmod32"] = load_model_dataset(velmod32_path)

    velmod4_path = data_dir / "VELMOD4_UTM31.h5"
    if velmod4_path.exists():
        models["velmod4"] = load_model_dataset(velmod4_path)

    dgm_path = data_dir / "DGM5_UTM31.h5"
    if dgm_path.exists():
        models["dgm"] = load_model_dataset(dgm_path)

    groningen_path = data_dir / "GRONINGEN_2017_RD.h5"
    if groningen_path.exists():
        groningen = load_model_dataset(groningen_path)
        required_variables = {"tvd", "V0", "k", "relationship_type", "vs_slope", "vs_intercept"}
        if required_variables.issubset(groningen.data_vars):
            models["groningen"] = groningen

    return models


def test_sample_velocity_model_basic(test_models):
    """Test basic velocity sampling."""
    if "velmod31" not in test_models or "dgm" not in test_models:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_models["velmod31"]
    dgm = test_models["dgm"]

    # Sample at a single point
    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000, -2000], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    # Check output structure
    assert "Vinst" in result
    assert "mode" in result.coords or "mode" in result.dims
    # VELMOD 3.1 doesn't have built-in S-wave parameters, so only P-wave is computed
    assert result.mode.values == "P"


def test_sample_velocity_model_with_vs_params(test_models):
    """Test velocity sampling with custom Vp-Vs parameters."""
    if "velmod31" not in test_models or "dgm" not in test_models:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_models["velmod31"]
    dgm = test_models["dgm"]

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

    # Check S-wave velocities are computed
    vs = result["Vinst"].sel(mode="S").values
    assert not np.all(np.isnan(vs))
    # S-wave velocities should be positive
    assert np.all(vs[~np.isnan(vs)] > 0)


def test_sample_velocity_model_groningen(test_models):
    """Test Groningen model sampling with embedded Vp-Vs."""
    if "groningen" not in test_models:
        pytest.skip("Groningen model not available")

    groningen = test_models["groningen"]

    # Use coordinates in Groningen region (RD system)
    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000, -2000], dims=["z"])

    result = sample_velocity_model(lon, lat, depths, crs="EPSG:4326", velocity_model=groningen)

    # Check S-wave velocities from embedded relationships
    vs = result["Vinst"].sel(mode="S").values
    # Should have valid S-wave velocities
    valid_vs = vs[~np.isnan(vs)]
    if len(valid_vs) > 0:
        assert np.all(valid_vs > 0), "S-wave velocities should be positive"


def test_sample_velocity_model_groningen_exact_deepest_boundary(test_models):
    """Exact deepest-boundary samples should stay in the deepest Groningen unit."""
    if "groningen" not in test_models:
        pytest.skip("Groningen model not available")

    groningen = test_models["groningen"]

    lon, lat = 6.8, 53.4
    shallow_result = sample_velocity_model(
        lon,
        lat,
        None,
        crs="EPSG:4326",
        velocity_model=groningen,
    )
    deepest_boundary = float(-shallow_result["depth"].sel(unit="Carboniferous").item())
    depths = xr.DataArray([-deepest_boundary], dims=["z"], coords={"z": [deepest_boundary]})

    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        velocity_model=groningen,
    )

    assert result["unit_samples"].sel(z=deepest_boundary).item() == "Carboniferous"


def test_sample_velocity_model_array_input(test_models):
    """Test sampling with array of coordinates."""
    if "velmod31" not in test_models or "dgm" not in test_models:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_models["velmod31"]
    dgm = test_models["dgm"]

    # Multiple points
    lons = xr.DataArray([6.8, 7.0], dims=["point"])
    lats = xr.DataArray([53.4, 53.5], dims=["point"])
    depths = xr.DataArray([0, -1000], dims=["z"])

    result = sample_velocity_model(
        lons, lats, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    # Check dimensions
    assert "point" in result.dims
    assert "z" in result.dims
    assert result.sizes["point"] == 2
    assert result.sizes["z"] == 2


def test_sample_velocity_model_crs_transform(test_models):
    """Test coordinate transformation between CRS."""
    if "velmod31" not in test_models or "dgm" not in test_models:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_models["velmod31"]
    dgm = test_models["dgm"]

    # Sample using WGS84 coordinates (should be transformed to UTM)
    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",  # WGS84
        depth_model=dgm,
        velocity_model=velmod,
    )

    assert "Vinst" in result
    # Should successfully transform and sample


def test_vs_relationship_types(test_models):
    """Test different Vp-Vs relationship types."""
    if "velmod31" not in test_models or "dgm" not in test_models:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_models["velmod31"]
    dgm = test_models["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    # Test linear relationship
    result_linear = sample_velocity_model(
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

    vs_linear = result_linear["Vinst"].sel(mode="S").values
    assert not np.all(np.isnan(vs_linear))

    # Test ratio_constant relationship
    result_ratio = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        depth_model=dgm,
        velocity_model=velmod,
        vs_relationship_type="ratio_constant",
        vs_slope=1.73,  # Typical Vp/Vs ratio
    )

    vs_ratio = result_ratio["Vinst"].sel(mode="S").values
    assert not np.all(np.isnan(vs_ratio))


def test_sample_at_surface(test_models):
    """Test sampling at surface (depth=0)."""
    if "velmod31" not in test_models or "dgm" not in test_models:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_models["velmod31"]
    dgm = test_models["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    # Should get velocities even at surface
    vp = result["Vinst"].values
    assert len(vp) == 1


def test_sample_deep_depths(test_models):
    """Test sampling at deep depths."""
    if "velmod31" not in test_models or "dgm" not in test_models:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_models["velmod31"]
    dgm = test_models["dgm"]

    lon, lat = 6.8, 53.4
    # Test at various depths
    depths = xr.DataArray([0, -1000, -2000, -3000, -5000], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    vp = result["Vinst"].values
    # Deeper velocities should generally be higher (with some possible NaN)
    valid_vp = vp[~np.isnan(vp)]
    if len(valid_vp) > 1:
        # At least some increasing trend in velocity with depth
        assert valid_vp[-1] >= valid_vp[0] * 0.8  # Allow some variation


def test_kriging_types(test_models):
    """Test different kriging types."""
    if "velmod31" not in test_models or "dgm" not in test_models:
        pytest.skip("VELMOD31 or DGM not available")

    velmod = test_models["velmod31"]
    dgm = test_models["dgm"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000], dims=["z"])

    result = sample_velocity_model(
        lon, lat, depths, crs="EPSG:4326", depth_model=dgm, velocity_model=velmod
    )

    # Check kriging types are present
    if "kriging_type" in result.dims:
        assert "sk" in result.kriging_type.values
        # Test selecting specific kriging type
        result_sk = result
        assert "Vinst" in result_sk


def test_sample_velocity_model_velmod4(test_models):
    """Test sampling with VELMOD 4.0 (standalone, no DGM needed)."""
    if "velmod4" not in test_models:
        pytest.skip("VELMOD 4.0 not available")

    velmod4 = test_models["velmod4"]

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000, -2000], dims=["z"])

    # VELMOD 4 doesn't need DGM (has its own tvd)
    result = sample_velocity_model(
        lon,
        lat,
        depths,
        crs="EPSG:4326",
        velocity_model=velmod4,
        vs_relationship_type="linear",
        vs_intercept=-1172,
        vs_slope=0.862,
    )

    # Check output structure
    assert "Vinst" in result
    assert "mode" in result.coords or "mode" in result.dims
    assert "P" in result.mode.values
    assert "S" in result.mode.values

    # Check velocities are reasonable
    vp = result["Vinst"].values
    vs = result["Vinst"].sel(mode="S").values

    valid_vp = vp[~np.isnan(vp)]
    valid_vs = vs[~np.isnan(vs)]

    if len(valid_vp) > 0:
        assert np.all(valid_vp > 0), "P-wave velocities should be positive"
    if len(valid_vs) > 0:
        assert np.all(valid_vs > 0), "S-wave velocities should be positive"


def test_sample_groningen_multiple_depths(test_models):
    """Test Groningen sampling at multiple depth levels."""
    if "groningen" not in test_models:
        pytest.skip("Groningen model not available")

    groningen = test_models["groningen"]

    # Groningen region coordinates
    lon, lat = 6.8, 53.4
    # Test multiple depths to hit different formations
    depths = xr.DataArray([0, -500, -1000, -1500, -2000, -2500, -3000], dims=["z"])

    result = sample_velocity_model(lon, lat, depths, crs="EPSG:4326", velocity_model=groningen)

    # Check S-wave velocities from embedded relationships
    vp = result["Vinst"].sel(mode="P").values
    vs = result["Vinst"].sel(mode="S").values

    # Should have valid velocities at multiple depths
    valid_vp = vp[~np.isnan(vp)]
    valid_vs = vs[~np.isnan(vs)]

    assert len(valid_vp) > 0, "Should have valid P-wave velocities"
    assert len(valid_vs) > 0, "Should have valid S-wave velocities"

    # All valid velocities should be positive
    if len(valid_vp) > 0:
        assert np.all(valid_vp > 0), "P-wave velocities should be positive"
    if len(valid_vs) > 0:
        assert np.all(valid_vs > 0), "S-wave velocities should be positive"

    # Vs should generally be less than Vp
    common_valid = ~np.isnan(vp) & ~np.isnan(vs)
    if np.any(common_valid):
        assert np.all(vs[common_valid] < vp[common_valid]), "Vs should be less than Vp"


def test_compare_velmod_versions(test_models):
    """Test that different VELMOD versions can be sampled and compared."""
    available_velmods = [k for k in ["velmod31", "velmod32", "velmod4"] if k in test_models]

    if len(available_velmods) < 2:
        pytest.skip("Need at least 2 VELMOD versions")

    lon, lat = 6.8, 53.4
    depths = xr.DataArray([0, -1000, -2000], dims=["z"])

    results = {}
    for velmod_key in available_velmods:
        velmod = test_models[velmod_key]

        # VELMOD 3.x needs DGM, VELMOD 4 doesn't
        if velmod_key in ["velmod31", "velmod32"]:
            if "dgm" not in test_models:
                continue
            result = sample_velocity_model(
                lon,
                lat,
                depths,
                crs="EPSG:4326",
                depth_model=test_models["dgm"],
                velocity_model=velmod,
            )
        else:  # velmod4
            result = sample_velocity_model(lon, lat, depths, crs="EPSG:4326", velocity_model=velmod)

        results[velmod_key] = result

    # All results should have the same structure
    for key, result in results.items():
        assert "Vinst" in result, f"{key} should have Vinst"
        assert "mode" in result.coords or "mode" in result.dims, f"{key} should have mode"
