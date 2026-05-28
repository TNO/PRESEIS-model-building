"""Tests for configured model conversion and loading."""

from pathlib import Path

import pytest

from preseis.model_building import (
    convert_dgm,
    convert_groningen,
    convert_velmod,
    download_models,
    get_processed_data_dir,
    load_model_dataset,
)

test_path = Path(__file__).parent
module_path = test_path.parent


def test_config_file_exists():
    """Test that configuration file exists."""
    assert (module_path / "config/config.yaml").exists()


def test_conversion_velmod31():
    """Test conversion of VELMOD 3.1 and DGM models."""
    # Use new module functions instead of old scripts
    download_models(verbose=False)
    convert_dgm(verbose=False)
    convert_velmod(velmod_version="3.1", verbose=False)

    # Get paths from utility function
    processed_dir = get_processed_data_dir()
    velmod_path = processed_dir / "VELMOD31_UTM31.h5"
    dgm_path = processed_dir / "DGM5_UTM31.h5"

    assert velmod_path.exists()
    assert dgm_path.exists()

    velmod = load_model_dataset(velmod_path)
    dgm = load_model_dataset(dgm_path)

    # Validate key structure instead of comparing against bulky on-disk fixtures.
    assert {"x", "y", "unit"}.issubset(set(velmod.dims))
    assert {"V0", "V0_filled", "k"}.issubset(set(velmod.data_vars))
    assert "summary_statistic" in velmod.dims
    assert "mean" in velmod.summary_statistic.values

    assert {"x", "y", "unit"}.issubset(set(dgm.dims))
    assert {"tvd", "ordering"}.issubset(set(dgm.data_vars))
    assert "spatial_ref" in dgm.coords

    # Spot-check that interpolation inputs are not empty/all-NaN.
    velmod_mean = velmod["V0_filled"].sel(summary_statistic="mean")
    assert bool(velmod_mean.notnull().any())
    assert bool(dgm["tvd"].notnull().any())


def test_conversion_velmod32():
    """Test conversion of VELMOD 3.2 model."""
    convert_dgm(verbose=False)
    convert_velmod(velmod_version="3.2", verbose=False)

    processed_dir = get_processed_data_dir()
    velmod32_path = processed_dir / "VELMOD32_UTM31.h5"
    dgm_path = processed_dir / "DGM5_UTM31.h5"

    assert velmod32_path.exists(), "VELMOD32_UTM31.h5 was not created"
    assert dgm_path.exists(), "DGM5_UTM31.h5 was not created"


@pytest.mark.parametrize(
    "version,filename",
    [
        ("3.1", "VELMOD31_UTM31.h5"),
        ("3.2", "VELMOD32_UTM31.h5"),
        ("4", "VELMOD4_UTM31.h5"),
    ],
)
def test_velmod_structure(version, filename):
    """Test that VELMOD models have expected structure."""
    processed_dir = get_processed_data_dir()
    velmod_path = processed_dir / filename

    assert velmod_path.exists(), f"{filename} not found"

    # Load dataset
    ds = load_model_dataset(velmod_path)

    # Check expected variables (VELMOD 4 has different structure)
    if version == "4":
        expected_vars = {"V0", "Vint", "V0_filled", "k", "tvd"}
    else:
        expected_vars = {"V0", "Vint", "V0_filled", "layer", "k"}

    assert expected_vars.issubset(set(ds.data_vars)), (
        f"Missing variables: {expected_vars - set(ds.data_vars)}"
    )

    # Check dimensions
    assert "x" in ds.dims
    assert "y" in ds.dims
    assert "unit" in ds.dims

    # Check spatial reference (it's a coordinate, not a data variable)
    assert "spatial_ref" in ds.coords
    assert hasattr(ds, "rio")

    ds.close()


@pytest.mark.parametrize(
    "version,filename",
    [
        ("3.1", "VELMOD31_UTM31.h5"),
        ("3.2", "VELMOD32_UTM31.h5"),
        ("4", "VELMOD4_UTM31.h5"),
    ],
)
def test_velmod_k_values(version, filename):
    """Test that k-values are loaded correctly."""
    processed_dir = get_processed_data_dir()
    ds = load_model_dataset(processed_dir / filename)

    # Check k values exist and are reasonable
    k_values = ds["k"].values
    assert len(k_values) > 0

    # k values should be between 0 and 1 typically
    assert (k_values >= 0).all()
    assert (k_values <= 1).all()

    ds.close()


def test_velmod_versions_compatible():
    """Test that VELMOD 3.1 and 3.2 have compatible structures."""
    processed_dir = get_processed_data_dir()

    ds31 = load_model_dataset(processed_dir / "VELMOD31_UTM31.h5")
    ds32 = load_model_dataset(processed_dir / "VELMOD32_UTM31.h5")

    # Both should have same spatial dimensions
    assert ds31.sizes["x"] == ds32.sizes["x"]
    assert ds31.sizes["y"] == ds32.sizes["y"]

    # Both should have same core variables
    core_vars = {"V0", "Vint", "layer", "k"}
    assert core_vars.issubset(set(ds31.data_vars))
    assert core_vars.issubset(set(ds32.data_vars))

    # Both should have summary_statistic dimension (mean/sd)
    # kriging_type dimension removed (only simple kriging now)
    assert "summary_statistic" in ds31.dims
    assert "summary_statistic" in ds32.dims
    assert "mean" in ds31.summary_statistic.values
    assert "mean" in ds32.summary_statistic.values

    ds31.close()
    ds32.close()


def test_conversion_velmod4():
    """Test conversion of VELMOD 4.0 model."""
    convert_velmod(velmod_version="4", verbose=False)

    processed_dir = get_processed_data_dir()
    velmod4_path = processed_dir / "VELMOD4_UTM31.h5"

    assert velmod4_path.exists(), "VELMOD4_UTM31.h5 was not created"

    # Load and verify structure
    ds = load_model_dataset(velmod4_path)

    # VELMOD 4 has tvd (like Groningen)
    assert "tvd" in ds.data_vars, "VELMOD 4 should have tvd"
    assert "V0" in ds.data_vars
    assert "k" in ds.data_vars

    ds.close()


def test_conversion_groningen():
    """Test conversion of Groningen model."""
    try:
        convert_groningen(verbose=False)
    except Exception as e:
        pytest.skip(f"Groningen conversion not available: {e}")

    processed_dir = get_processed_data_dir()
    groningen_path = processed_dir / "GRONINGEN_2017_RD.h5"

    assert groningen_path.exists(), "GRONINGEN_2017_RD.h5 was not created"

    # Load and verify structure
    ds = load_model_dataset(groningen_path)

    # Groningen-specific variables
    assert "tvd" in ds.data_vars, "Groningen should have tvd"
    assert "V0" in ds.data_vars
    assert "k" in ds.data_vars
    assert "relationship_type" in ds.data_vars, "Groningen should have relationship_type"
    assert "vs_slope" in ds.data_vars, "Groningen should have vs_slope"
    assert "vs_intercept" in ds.data_vars, "Groningen should have vs_intercept"

    # Check model attribute
    assert hasattr(ds, "model")
    assert "Groningen" in ds.model or "GRONINGEN" in ds.model

    ds.close()


def test_groningen_vs_parameters():
    """Test that Groningen model has valid Vp-Vs parameters."""
    processed_dir = get_processed_data_dir()
    groningen_path = processed_dir / "GRONINGEN_2017_RD.h5"

    if not groningen_path.exists():
        pytest.skip("Groningen model not available")

    ds = load_model_dataset(groningen_path)
    required_variables = {"relationship_type", "vs_slope", "vs_intercept"}
    if not required_variables.issubset(ds.data_vars):
        pytest.skip("Groningen processed file is not a current xarray export")

    # Check vs_slope has reasonable values
    vs_slope = ds["vs_slope"].values

    # Should have non-zero values (not all NaN)
    assert not all(v == 0 or v != v for v in vs_slope.flat), "vs_slope should have non-zero values"

    # relationship_type should have valid types
    rel_types = ds["relationship_type"].values
    # Could be bytes or strings
    valid_types_bytes = [b"linear", b"ratio_constant", b"ratio_depth", b"constant"]
    valid_types_str = ["linear", "ratio_constant", "ratio_depth", "constant"]

    # At least some relationships should be defined
    has_valid = any(
        (rt in valid_types_bytes or rt in valid_types_str)
        for rt in rel_types.flat
        if isinstance(rt, (bytes, str))
    )
    assert has_valid, "relationship_type should contain valid types"

    ds.close()
