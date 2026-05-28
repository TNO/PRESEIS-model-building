from pathlib import Path

import numpy as np
import pyproj as prj
import pytest
import xarray as xr
import xarray.testing as xrt

from preseis.model_building import (
    get_processed_data_dir,
    load_model_dataset,
    sample_velocity_model,
)

test_path = Path(__file__).parent
module_path = test_path.parent


def test_config_file_exists():
    """Test that configuration file exists."""
    assert (module_path / "config/config.yaml").exists()


def test_sampling(create=False):
    """Test velocity sampling on a grid with coordinate transformation."""
    data_dir = get_processed_data_dir()
    velmod_path = data_dir / "VELMOD31_UTM31.h5"
    dgm_path = data_dir / "DGM5_UTM31.h5"

    if not velmod_path.exists() or not dgm_path.exists():
        pytest.skip("VELMOD31 or DGM not available")

    assert velmod_path.exists()
    assert dgm_path.exists()

    velmod = load_model_dataset(velmod_path)
    dgm = load_model_dataset(dgm_path)

    crs_UTM, crs_RD = (
        prj.CRS("EPSG:23031"),
        prj.CRS("EPSG:28992"),
    )
    RD_to_UTM = prj.Transformer.from_crs(crs_RD, crs_UTM)

    # Define grid in RD
    # X,Y samples
    xsmp_RD = np.linspace(100000.0, 110000.0, 41)
    ysmp_RD = np.linspace(450000.0, 460000.0, 41)
    zsmp = np.linspace(-5000.0, 0.0, 51)

    # Prepare xarray representation, without data, just coordinates
    grid = (
        xr.Dataset(coords={"x": xsmp_RD, "y": ysmp_RD, "z": zsmp})
        .rio.write_crs(crs_RD.to_epsg())
        .rio.write_coordinate_system()
    )

    # Determine UTM coordinates for all grid points
    x_UTM, y_UTM = xr.apply_ufunc(
        RD_to_UTM.transform,
        grid["x"],
        grid["y"],
        output_core_dims=[[], []],
        vectorize=True,  # prj Transformers do not broadcast
        keep_attrs=True,
    )

    # Sample models to cube, no need to pass CRS since it is represented in the x_UTM data structure
    velocity_cube = sample_velocity_model(
        x_UTM,
        y_UTM,
        grid["z"],
        depth_model=dgm,
        velocity_model=velmod,
        crs=crs_UTM,
    )

    # Determinism check: same inputs should produce identical output.
    velocity_cube_again = sample_velocity_model(
        x_UTM,
        y_UTM,
        grid["z"],
        depth_model=dgm,
        velocity_model=velmod,
        crs=crs_UTM,
    )

    xrt.assert_identical(velocity_cube, velocity_cube_again)
    assert "Vinst" in velocity_cube.data_vars
    assert bool(velocity_cube["Vinst"].notnull().any())
