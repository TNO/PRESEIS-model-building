"""Convert DGM and VELMOD ZMAP files to xarray format."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import zmapio
from tqdm import tqdm

from .utils import (
    get_model_config,
    get_package_root,
    get_processed_data_dir,
    get_raw_data_dir,
    get_velmod_config,
)

# UTM31 CRS (original format for DGM and VELMOD)
CRS_UTM31 = "epsg:23031"  # https://epsg.io/23031

NETCDF_ENGINE = "h5netcdf"
NETCDF_FORMAT = "NETCDF4"
NETCDF_COMPRESSION = {
    "compression": "gzip",
    "compression_opts": 4,
    "shuffle": True,
}

# Canonical ordering of stratigraphic units (top to bottom)
UNIT_CANONICAL_ORDER = [
    "N",
    "NU",
    "NLNM",
    "NM",
    "NL",
    "NLM",
    "CK",
    "KN",
    "KNG",
    "KNGL",
    "KNN",
    "S",
    "SL",
    "SG",
    "SK",
    "ATPO",
    "AT",
    "S+AT",
    "TR",
    "RN",
    "RB",
    "RN+RB",
    "ZE",
    "RO",
    "DCC",
    "DC",
    "CL",
]


def _is_string_like_object_array(values) -> bool:
    """Return True when an object array only contains string-like values."""
    flat_values = np.asarray(values, dtype=object).ravel()
    return all(
        value is None or isinstance(value, (str, bytes, np.str_))
        for value in flat_values
    )


def _normalize_string_array(values):
    """Normalize an object array of strings to a NumPy unicode array."""
    normalized = []
    for value in np.asarray(values, dtype=object).ravel():
        if value is None:
            normalized.append("")
        elif isinstance(value, bytes):
            normalized.append(value.decode())
        else:
            normalized.append(str(value))

    return np.asarray(normalized, dtype=str).reshape(values.shape)


def _coerce_string_variables(dataset: xr.Dataset) -> xr.Dataset:
    """Convert object string variables to native unicode arrays before writing."""
    dataset = dataset.copy()

    for variable_name in list(dataset.variables):
        variable = dataset[variable_name]
        if variable.dtype != object or not _is_string_like_object_array(variable.values):
            continue

        normalized_values = _normalize_string_array(variable.values)
        replacement = xr.Variable(variable.dims, normalized_values, attrs=variable.attrs)

        if variable_name in dataset.coords:
            dataset = dataset.assign_coords({variable_name: replacement})
        else:
            dataset = dataset.assign({variable_name: replacement})

    return dataset


def _build_netcdf_encoding(dataset: xr.Dataset) -> dict:
    """Build a consistent NetCDF encoding for model exports."""
    encoding = {}
    for variable_name, variable in dataset.data_vars.items():
        if variable.ndim > 0 and np.issubdtype(variable.dtype, np.number):
            encoding[variable_name] = dict(NETCDF_COMPRESSION)
    return encoding


def _prepare_model_dataset(
    dataset: xr.Dataset,
    *,
    title: str,
    description: str,
    crs: str,
    variant: str = None,
) -> xr.Dataset:
    """Apply consistent metadata and string normalization before export."""
    dataset = dataset.copy()
    if "spatial_ref" in dataset and "spatial_ref" not in dataset.coords:
        dataset = dataset.set_coords("spatial_ref")

    dataset = _coerce_string_variables(dataset)

    attrs = dict(dataset.attrs)
    attrs.update(
        {
            "title": title,
            "summary": description,
            "generated_by": "preseis.model_building.convert",
            "repository": "preseis-model-building",
            "coordinate_reference_system": crs,
        }
    )
    if variant is not None:
        attrs["variant"] = variant

    dataset.attrs = attrs
    return dataset


def _write_model_dataset(
    dataset: xr.Dataset,
    output_path,
    *,
    title: str,
    description: str,
    crs: str,
    variant: str = None,
):
    """Write a processed model dataset with consistent NetCDF settings."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_dataset = _prepare_model_dataset(
        dataset,
        title=title,
        description=description,
        crs=crs,
        variant=variant,
    )
    export_dataset.to_netcdf(
        output_path,
        engine=NETCDF_ENGINE,
        mode="w",
        format=NETCDF_FORMAT,
        encoding=_build_netcdf_encoding(export_dataset),
    )

    return output_path


def convert_dgm(raw_dir=None, processed_dir=None, force=False, verbose=False):
    """
    Convert DGM-diep V5 ZMAP files to xarray format.

    Reads ZMAP files from the raw data directory and converts them to
    NetCDF (.h5) format in the processed data directory. If file already
    exists, it is skipped unless force=True.

    Parameters
    ----------
    raw_dir : Path or str, optional
        Directory containing raw ZMAP files.
        If None, uses the default from get_raw_data_dir().
    processed_dir : Path or str, optional
        Directory for output .h5 files.
        If None, uses the default from get_processed_data_dir().
    force : bool, optional
        If True, reconvert file even if it already exists. Default False.
    verbose : bool, optional
        If True, print progress messages. Default False.

    Returns
    -------
    Path
        Path to the output file
    """
    raw_dir = Path(raw_dir) if raw_dir else get_raw_data_dir()
    output_dir = Path(processed_dir) if processed_dir else get_processed_data_dir()

    dgm_config = get_model_config("dgm")
    out_dgm = output_dir / dgm_config["output_file"]

    # Check if already converted
    if not force and out_dgm.exists():
        if verbose:
            print(f"✓ DGM already converted: {out_dgm}")
            print("  Use force=True to reconvert")
        return out_dgm

    dgm_zmap_list = list(raw_dir.glob("dgmdeep5/**/*tvd*merge_*UTM31.zmap"))

    if not dgm_zmap_list:
        raise FileNotFoundError(
            f"No DGM ZMAP files found in {raw_dir / 'dgmdeep5'}. Run download_models() first."
        )

    if verbose:
        print("Converting DGM5 to xarray format...")

    dgmds = [
        _dgm_zmap_to_xarray(zm, CRS_UTM31)
        for zm in tqdm(dgm_zmap_list, disable=not verbose)
    ]

    # Add bottom layer at -infinity
    last = xr.full_like(dgmds[0], -math.inf)
    last["unit"] = "DC"
    dgmds.append(last)

    # Concatenate and organize
    dgmxrc = (
        xr.concat(dgmds, dim="unit_var", join="outer")
        .set_index({"unit_var": ["unit", "var"]})
        .unstack()
        .dropna(dim="x", how="all")
        .dropna(dim="y", how="all")
    )

    dgmxrds = dgmxrc.to_dataset("var")

    # Add canonical ordering
    dgm_ordering = xr.zeros_like(dgmxrds["unit"], dtype=int).rename("ordering")
    for u in dgm_ordering.coords["unit"]:
        dgm_ordering.loc[{"unit": u}] = UNIT_CANONICAL_ORDER.index(u)
    dgm_utm = xr.merge([dgmxrds, dgm_ordering], compat="no_conflicts").sortby("ordering")

    _write_model_dataset(
        dgm_utm,
        out_dgm,
        title=f"{dgm_config['name']} processed xarray model",
        description=dgm_config["description"],
        crs=CRS_UTM31,
    )
    if verbose:
        print(f"  ✓ Wrote {out_dgm.name}")

    return out_dgm


def convert_velmod(
    velmod_version, raw_dir=None, processed_dir=None, force=False, verbose=False
):
    """
    Convert VELMOD ZMAP files to xarray format.

    Reads ZMAP files from the raw data directory and converts them to
    NetCDF (.h5) format in the processed data directory. If file already
    exists, it is skipped unless force=True.

    IMPORTANT: VELMOD 4 includes depth (tvd) data in its source files and does NOT
    require DGM for depth information. VELMOD 3.1/3.2 do not have depth data and
    require DGM depths.

    Parameters
    ----------
    velmod_version : str
        VELMOD version to convert: "3.1", "3.2", "4", or "velmod-3.1", "velmod-3.2", "velmod-4".
        If "velmod-" prefix is provided, it will be stripped.
    raw_dir : Path or str, optional
        Directory containing raw ZMAP files.
        If None, uses the default from get_raw_data_dir().
    processed_dir : Path or str, optional
        Directory for output .h5 files.
        If None, uses the default from get_processed_data_dir().
    force : bool, optional
        If True, reconvert file even if it already exists. Default False.
    verbose : bool, optional
        If True, print progress messages. Default False.

    Returns
    -------
    Path
        Path to the output file
    """
    # Strip "velmod-" prefix if present (e.g., "velmod-3.1" -> "3.1")
    if velmod_version.startswith("velmod-"):
        velmod_version = velmod_version.split("-")[1]

    raw_dir = Path(raw_dir) if raw_dir else get_raw_data_dir()
    output_dir = Path(processed_dir) if processed_dir else get_processed_data_dir()
    package_root = get_package_root()

    # Load model configurations
    velmod_config = get_velmod_config(velmod_version)

    velmod_dir = velmod_config["directory"]
    k_file = velmod_config["k_file"]
    output_filename = velmod_config["output_file"]
    model_name = velmod_config["name"]

    velmod_k_file = package_root / "config" / k_file
    out_velmod = output_dir / output_filename

    # Check if already converted
    if not force and out_velmod.exists():
        if verbose:
            print(f"✓ {model_name} already converted: {out_velmod}")
            print("  Use force=True to reconvert")
        return out_velmod

    # All VELMOD versions use .dat format
    # Only read simple kriging (_sk) files, skip cokriging (_cok) and ordinary kriging (_ok)
    all_files = list(raw_dir.glob(f"{velmod_dir}/**/*.dat"))
    velmod_zmap_list = [
        f for f in all_files if "_cok" not in f.stem and "_ok" not in f.stem
    ]

    if not velmod_zmap_list:
        raise FileNotFoundError(
            f"No {model_name} ZMAP files found in {raw_dir / velmod_dir}.\n"
            f"Run download_models() first to download the data from NLOG."
        )

    if verbose:
        skipped = len(all_files) - len(velmod_zmap_list)
        if skipped > 0:
            print(
                f"  Skipping {skipped} cokriging/ordinary kriging files (using simple kriging only)"
            )

    # Convert VELMOD
    if verbose:
        print(f"Converting {model_name} to xarray format...")

    # Read k values from config CSV
    # Read the CSV and set 'unit' as the index for proper merging
    k_df = pd.read_csv(velmod_k_file, delimiter=";")
    k_df = k_df.set_index("unit")
    velmoddata = xr.Dataset(k_df)

    # Read and convert all ZMAP files
    velmodds = [
        _velmod_zmap_to_xarray(zm, CRS_UTM31, model_name)
        for zm in tqdm(velmod_zmap_list, disable=not verbose)
    ]

    # Check if this is VELMOD 4
    is_velmod4 = velmod_version == "4"

    # Concatenate and organize based on version
    if is_velmod4:
        # VELMOD 4: no kriging_type or summary_statistic dimensions
        velmodxrc = (
            xr.concat(velmodds, dim="u_v", join="outer")
            .set_index({"u_v": ["unit", "variable"]})
            .unstack()
            .dropna(dim="x", how="all")
            .dropna(dim="y", how="all")
        )
    else:
        # VELMOD 3.1/3.2: has summary_statistic dimension (mean/sd)
        # No kriging_type dimension since we only read _sk files
        velmodxrc = (
            xr.concat(velmodds, dim="u_v_s", join="outer")
            .set_index({"u_v_s": ["unit", "variable", "summary_statistic"]})
            .unstack()
            .dropna(dim="x", how="all")
            .dropna(dim="y", how="all")
        )

    # Convert velmodxrc to dataset using variable coordinate
    velmodxrc_ds = velmodxrc.to_dataset("variable")

    # Align velmoddata with velmodxrc units (only keep units that exist in ZMAP data)
    common_units = [
        u
        for u in velmodxrc_ds.coords["unit"].values
        if u in velmoddata.coords["unit"].values
    ]
    velmoddata_aligned = velmoddata.sel(unit=common_units)

    # Merge datasets
    velmodxrds = xr.merge([velmodxrc_ds, velmoddata_aligned], compat="no_conflicts")

    # Add canonical ordering
    ordering = xr.zeros_like(velmodxrds["unit"], dtype=int).rename("ordering")
    for u in ordering.coords["unit"]:
        ordering.loc[{"unit": u}] = UNIT_CANONICAL_ORDER.index(u)
    velmod_utm = xr.merge((velmodxrds, ordering), compat="no_conflicts").sortby("ordering")

    # Integrate ZE unit (V0=Vint, k=0)
    # For ZE, copy all available Vint data to V0 where V0 is NaN
    ze_vint = velmod_utm["Vint"].sel({"unit": "ZE"})
    ze_v0 = velmod_utm["V0"].sel({"unit": "ZE"})
    # Copy Vint to V0 where V0 is NaN
    velmod_utm["V0"].loc[{"unit": "ZE"}] = ze_v0.fillna(ze_vint)

    # Fill missing values with unit mean
    velmod_utm["V0_filled"] = velmod_utm["V0"].fillna(velmod_utm["V0"].mean(["x", "y"]))

    # Debug: check if spatial_ref exists
    if verbose:
        print(f"  spatial_ref present: {'spatial_ref' in velmod_utm.coords}")
        print(f"  coords: {list(velmod_utm.coords)}")

    # Write to disk
    _write_model_dataset(
        velmod_utm,
        out_velmod,
        title=f"{model_name} processed xarray model",
        description=velmod_config["description"],
        crs=CRS_UTM31,
    )
    if verbose:
        print(f"  ✓ Wrote {out_velmod.name}")

    return out_velmod


def _dgm_zmap_to_xarray(zmap_file, crs):
    """Convert a DGM ZMAP file to xarray DataArray."""
    name = zmap_file.stem
    name_list = name.split("_")
    unit = name_list[0]
    var = name_list[1]

    zm = zmapio.ZMAPGrid(zmap_file.as_posix())
    zmds = xr.Dataset.from_dataframe(zm.to_pandas())
    zmda = zmds.set_index({"index": ["X", "Y"]}).unstack()["Z"].T
    zmda = (
        zmda.expand_dims("unit_var")
        .assign_coords(
            {
                "unit": ("unit_var", [unit]),
                "var": ("unit_var", [var.strip("_")]),
            }
        )
        .rename({"X": "x", "Y": "y"})
        .rio.write_crs(crs)
        .rio.write_coordinate_system()
        .assign_attrs({"model": "DGM5"})
    )
    return zmda


def _velmod_zmap_to_xarray(zmap_file, crs, model_name="VELMOD3.1"):
    """Convert a VELMOD ZMAP file to xarray DataArray."""
    name = zmap_file.stem

    # Handle different filename patterns for VELMOD 3.1, 3.2, and 4
    # VELMOD 3.1: unit_f_variable[_kriging[_summary]]
    # VELMOD 3.2: unit_f_variable[_kriging[_summary]]_zmap
    # VELMOD 4: unit_variable_step_5[_03_2020] (no kriging dimensions)
    parts = name.split("_")

    # Check if this is VELMOD 4 format (has "step" in parts)
    is_velmod4 = "step" in parts

    # Only apply naming fixes for VELMOD 3.x files
    if not is_velmod4:
        # VELMOD 3.x: standardize unit names
        name = name.replace("NLM", "NLNM")  # Fix NLM -> NLNM
        parts = name.split("_")

    zm = zmapio.ZMAPGrid(zmap_file.as_posix())
    zmds = xr.Dataset.from_dataframe(zm.to_pandas())
    zmda = zmds.set_index({"index": ["X", "Y"]}).unstack()["Z"].T

    if is_velmod4:
        # VELMOD 4 format: unit_variable_step_5[_03_2020]
        # Keep original unit names as they appear in files (S+AT, RN+RB, etc.)
        unit = parts[0]
        var = parts[1]
        # VELMOD 4 includes depth data in its source files.
        # Map VELMOD 4 "depth" variable to "tvd" for consistency with DGM
        # and negate depth values (positive depth in files -> negative tvd, below sea level)
        if var == "depth":
            var = "tvd"
            # Change the sign: VELMOD 4 files have positive depth, we need negative (below NAP)
            zmda = -1 * zmda

        zmda = (
            zmda.expand_dims("u_v")
            .assign_coords(
                {
                    "unit": ("u_v", [unit]),
                    "variable": ("u_v", [var]),
                }
            )
            .rename({"X": "x", "Y": "y"})
            .rio.write_crs(crs)
            .rio.write_coordinate_system()
            .assign_attrs({"model": model_name})
        )
    else:
        # VELMOD 3.1/3.2 format with summary statistics
        # Remove "_zmap" suffix if present (VELMOD 3.2)
        if parts[-1] == "zmap":
            parts = parts[:-1]

        # Parse filename parts with flexible structure
        unit = parts[0]
        var = parts[2]

        # Parse summary statistic part
        # VELMOD 3.1: *_sk.dat, *_sk_sd.dat (only reading _sk files now)
        # VELMOD 3.2: *_sk_zmap.dat (mean), *_sk_sd_zmap.dat (sd)
        summary_statistic = "mean"  # default to mean

        if len(parts) >= 4:
            # Skip the "sk" part (always present since we filter for it)
            # Check if there's an "sd" part
            if len(parts) >= 5 and parts[4] == "sd":
                summary_statistic = "sd"
            elif parts[3] == "sd":
                summary_statistic = "sd"

        zmda = (
            zmda.expand_dims("u_v_s")
            .assign_coords(
                {
                    "unit": ("u_v_s", [unit]),
                    "variable": ("u_v_s", [var]),
                    "summary_statistic": ("u_v_s", [summary_statistic]),
                }
            )
            .rename({"X": "x", "Y": "y"})
            .rio.write_crs(crs)
            .rio.write_coordinate_system()
            .assign_attrs({"model": model_name})
        )

    return zmda


# ============================================================================
# Groningen Model Conversion
# ============================================================================

# RD coordinate system (Rijksdriehoekscoördinaten / Amersfoort)
CRS_RD = "epsg:28992"  # https://epsg.io/28992


def _load_horizons_groningen(
    horizons_file: Path, verbose: bool = False
) -> pd.DataFrame:
    """Load horizon depth data from horizons.txt for Groningen model."""
    if verbose:
        print(f"Loading horizon data from {horizons_file.name}...")

    df = pd.read_csv(horizons_file, sep=r"\s+")

    if verbose:
        print(f"  Loaded {len(df)} grid points")
        print(
            f"  Horizons: {[col for col in df.columns if col not in ['XSSP', 'YSSP', 'Trk', 'Bin']]}"
        )

    return df


def _load_vo_maps_groningen(vo_file: Path, verbose: bool = False) -> pd.DataFrame:
    """Load reference velocity (V0) data from Vo_maps.txt for Groningen model."""
    if verbose:
        print(f"Loading V0 maps from {vo_file.name}...")

    df = pd.read_csv(vo_file, sep=r"\s+")

    if verbose:
        print(f"  Loaded {len(df)} grid points")
        print(
            f"  Formations: {[col for col in df.columns if col not in ['XSSP', 'YSSP', 'Trk', 'Bin']]}"
        )

    return df


def _horizons_to_xarray_groningen(
    df: pd.DataFrame, horizon_cols: list, crs: str
) -> xr.Dataset:
    """Convert horizon DataFrame to xarray Dataset for Groningen model."""
    df_work = df.rename(columns={"XSSP": "x", "YSSP": "y"})

    horizon_data = df_work.melt(
        id_vars=["x", "y"],
        value_vars=horizon_cols,
        var_name="horizon",
        value_name="depth",
    )

    ds = xr.Dataset.from_dataframe(horizon_data.set_index(["x", "y", "horizon"]))
    ds = ds.unstack()
    ds = ds.rio.write_crs(crs)

    return ds


def _vo_to_xarray_groningen(df: pd.DataFrame, vo_cols: list, crs: str) -> xr.Dataset:
    """Convert V0 DataFrame to xarray Dataset for Groningen model."""
    df_work = df.rename(columns={"XSSP": "x", "YSSP": "y"})

    vo_data = df_work.melt(
        id_vars=["x", "y"], value_vars=vo_cols, var_name="vo_formation", value_name="V0"
    )

    ds = xr.Dataset.from_dataframe(vo_data.set_index(["x", "y", "vo_formation"]))
    ds = ds.unstack()
    ds = ds.rio.write_crs(crs)

    return ds


def _build_groningen_model(
    horizons_ds: xr.Dataset,
    vo_ds: xr.Dataset,
    k_config: pd.DataFrame,
    vp_vs_config: pd.DataFrame,
    remove_anhydrite: bool = False,
    verbose: bool = False,
) -> xr.Dataset:
    """Build Groningen velocity model following VELMOD4 structure."""
    formations = [
        "Upper_NS",
        "Lower_NS",
        "Chalk",
        "KN_JW_TR",
        "ZE_Halite_1",
        "ZE_Anhydrite_Floater",
        "ZE_Halite_2",
        "ZE_Anhydrite",
        "Rotliegend",
        "Carboniferous",
    ]

    if verbose:
        print(f"\nBuilding model with {len(formations)} formations...")

    # Build V0
    v0_ds = xr.Dataset()
    if "NS" in vo_ds["vo_formation"]:
        v0_ns = vo_ds["V0"].sel(vo_formation="NS", drop=True)
        v0_ds["Upper_NS"] = v0_ns
        v0_ds["Lower_NS"] = v0_ns
    if "CK" in vo_ds["vo_formation"]:
        v0_ds["Chalk"] = vo_ds["V0"].sel(vo_formation="CK", drop=True)
    if "ME" in vo_ds["vo_formation"]:
        v0_ds["KN_JW_TR"] = vo_ds["V0"].sel(vo_formation="ME", drop=True)

    for unit in [
        "ZE_Halite_1",
        "ZE_Anhydrite_Floater",
        "ZE_Halite_2",
        "ZE_Anhydrite",
        "Rotliegend",
        "Carboniferous",
    ]:
        v0_val = vp_vs_config.loc[vp_vs_config["unit"] == unit, "v0"].values[0]
        if pd.notnull(v0_val) and v0_val != "":
            v0_ds[unit] = float(v0_val)

    V0 = v0_ds.to_array("unit")  # noqa: N806

    # Build TVD
    tvd_ds = xr.Dataset()
    formation_to_bottom_horizon = {
        "Upper_NS": "NU_B",
        "Lower_NS": "NS_B",
        "Chalk": "CK_B",
        "KN_JW_TR": "ZE_T",
        "ZE_Halite_1": "float_T",
        "ZE_Anhydrite_Floater": "float_B",
        "ZE_Halite_2": "ZEZ2A_T",
        "ZE_Anhydrite": "RO_T",
        "Rotliegend": "DC_T",
    }

    for formation, horizon in formation_to_bottom_horizon.items():
        tvd_ds[formation] = -horizons_ds["depth"].sel(horizon=horizon, drop=True)

    tvd_ds["Carboniferous"] = -4500.0
    tvd = tvd_ds.to_array("unit")

    # K-factors, Vp-Vs parameters, and ordering
    k = xr.DataArray(
        [k_config.loc[k_config["unit"] == f, "k"].values[0] for f in formations],
        dims=["unit"],
        coords={"unit": formations},
    )

    relationship_type = xr.DataArray(
        [
            vp_vs_config.loc[vp_vs_config["unit"] == f, "relationship_type"].values[0]
            for f in formations
        ],
        dims=["unit"],
        coords={"unit": formations},
    )

    # Read from CSV columns "slope" and "intercept" (Groningen naming convention)
    # Store as "vs_slope" and "vs_intercept" in the model
    vs_slope = xr.DataArray(
        [
            vp_vs_config.loc[vp_vs_config["unit"] == f, "slope"].values[0]
            for f in formations
        ],
        dims=["unit"],
        coords={"unit": formations},
    )

    vs_intercept = xr.DataArray(
        [
            vp_vs_config.loc[vp_vs_config["unit"] == f, "intercept"].values[0]
            for f in formations
        ],
        dims=["unit"],
        coords={"unit": formations},
    )

    ordering = xr.DataArray(
        np.arange(len(formations)), dims=["unit"], coords={"unit": formations}
    )

    V0_filled = V0.fillna(V0.mean(dim=["x", "y"]))  # noqa: N806

    ds = xr.Dataset(
        {
            "tvd": tvd,
            "V0": V0,
            "V0_filled": V0_filled,
            "k": k,
            "relationship_type": relationship_type,
            "vs_slope": vs_slope,
            "vs_intercept": vs_intercept,
            "ordering": ordering,
        }
    )
    ds.attrs["model"] = "Groningen_2017"
    ds.attrs["source"] = "NAM September 2017 Groningen velocity model"
    ds = ds.rio.write_crs(CRS_RD)

    # Replace anhydrite velocities with ZE_Halite_2 values if requested
    if remove_anhydrite:
        if verbose:
            print("  Replacing anhydrite velocities with ZE_Halite_2 values...")

        # Get indices for anhydrite formations
        anhydrite_indices = [
            formations.index("ZE_Anhydrite_Floater"),
            formations.index("ZE_Anhydrite"),
        ]
        halite_2_index = formations.index("ZE_Halite_2")

        # Copy V0 values
        ds["V0"].values[anhydrite_indices] = ds["V0"].values[halite_2_index]
        ds["V0_filled"].values[anhydrite_indices] = ds["V0_filled"].values[
            halite_2_index
        ]

        # Copy k values
        ds["k"].values[anhydrite_indices] = ds["k"].values[halite_2_index]

        # Copy Vp-Vs relationship parameters
        ds["relationship_type"].values[anhydrite_indices] = ds[
            "relationship_type"
        ].values[halite_2_index]
        ds["vs_slope"].values[anhydrite_indices] = ds["vs_slope"].values[halite_2_index]
        ds["vs_intercept"].values[anhydrite_indices] = ds["vs_intercept"].values[
            halite_2_index
        ]

    if verbose:
        print(f"  Grid shape: {horizons_ds.sizes['x']} × {horizons_ds.sizes['y']}")
        print(f"  Formations: {len(formations)}")

    return ds


def convert_groningen(
    config_path=None,
    raw_dir=None,
    processed_dir=None,
    remove_anhydrite=False,
    verbose=False,
):
    """
    Convert Groningen 2017 velocity model to VELMOD4-compatible format.

    Parameters
    ----------
    config_path : Path or str, optional
        Path to config file. If None, uses default config/config.yaml.
    raw_dir : Path or str, optional
        Directory containing raw data. If None, uses data/raw from package root.
    processed_dir : Path or str, optional
        Directory for processed output. If None, uses data/processed from package root.
    remove_anhydrite : bool, optional
        If True, replace anhydrite layer velocities with ZE_Halite_2 values.
        Removes unrealistic fast paths from thin anhydrite layers. Default False.
    verbose : bool, optional
        If True, print progress messages. Default False.

    Returns
    -------
    int
        0 on success, 1 on error
    """
    from .utils import get_package_root, load_config

    if config_path is None:
        config_path = get_package_root() / "config" / "config.yaml"
    else:
        config_path = Path(config_path)

    config = load_config(config_path)
    groningen_config = config["models"]["groningen"]

    # Determine directories
    if raw_dir:
        raw_base_dir = Path(raw_dir)
    else:
        raw_base_dir = get_package_root() / "data" / "raw"

    if processed_dir:
        processed_dir = Path(processed_dir)
    else:
        processed_dir = get_package_root() / "data" / "processed"

    # Get Groningen-specific paths from config
    groningen_raw_dir = raw_base_dir / groningen_config["directory"]
    config_dir = Path(config_path).parent

    # Check input files
    horizons_file = groningen_raw_dir / "horizons.txt"
    vo_file = groningen_raw_dir / "Vo_maps.txt"
    k_file = config_dir / groningen_config["k_file"]
    vp_vs_file = config_dir / groningen_config["vp_vs_file"]
    output_file = processed_dir / groningen_config["output_file"]

    for file, desc in [
        (horizons_file, f"horizons.txt (expected in {groningen_raw_dir})"),
        (vo_file, f"Vo_maps.txt (expected in {groningen_raw_dir})"),
        (k_file, groningen_config["k_file"]),
        (vp_vs_file, groningen_config["vp_vs_file"]),
    ]:
        if not file.exists():
            raise FileNotFoundError(f"{desc} not found")

    if verbose:
        print("NAM Groningen 2017 Velocity Model Conversion")
        print("=" * 50)

    # Load data
    horizons_df = _load_horizons_groningen(horizons_file, verbose)
    vo_df = _load_vo_maps_groningen(vo_file, verbose)
    k_config = pd.read_csv(k_file)
    vp_vs_config = pd.read_csv(vp_vs_file)

    # Convert to xarray
    if verbose:
        print("\nConverting to xarray format...")

    horizon_cols = [
        "NU_B",
        "NS_B",
        "CK_B",
        "ZE_T",
        "float_T",
        "float_B",
        "ZEZ2A_T",
        "RO_T",
        "DC_T",
    ]
    horizons_ds = _horizons_to_xarray_groningen(horizons_df, horizon_cols, CRS_RD)
    vo_ds = _vo_to_xarray_groningen(vo_df, ["NS", "CK", "ME"], CRS_RD)

    # Build both variants: standard and without anhydrite
    if verbose:
        print("\nBuilding models...")

    model_standard = _build_groningen_model(
        horizons_ds,
        vo_ds,
        k_config,
        vp_vs_config,
        remove_anhydrite=False,
        verbose=verbose,
    )

    model_no_anhydrite = _build_groningen_model(
        horizons_ds, vo_ds, k_config, vp_vs_config, remove_anhydrite=True, verbose=False
    )

    # Save both variants
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save standard version
    if verbose:
        print(f"\nSaving standard version to {output_file}...")

    _write_model_dataset(
        model_standard,
        output_file,
        title=f"{groningen_config['name']} processed xarray model",
        description=groningen_config["description"],
        crs=CRS_RD,
        variant="standard",
    )

    if verbose:
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"  ✓ Wrote {output_file.name} ({file_size_mb:.1f} MB)")

    # Save no-anhydrite variant
    output_file_no_anhydrite = output_file.parent / output_file.name.replace(
        ".h5", "_no_anhydrite.h5"
    )
    if verbose:
        print(f"\nSaving no-anhydrite variant to {output_file_no_anhydrite}...")

    _write_model_dataset(
        model_no_anhydrite,
        output_file_no_anhydrite,
        title=f"{groningen_config['name']} processed xarray model",
        description=groningen_config["description"],
        crs=CRS_RD,
        variant="no_anhydrite",
    )

    if verbose:
        file_size_mb = output_file_no_anhydrite.stat().st_size / (1024 * 1024)
        print(f"  ✓ Wrote {output_file_no_anhydrite.name} ({file_size_mb:.1f} MB)")
        print("\n✓ Conversion complete!")

    return 0
