import numpy as np
import pyproj
import rioxarray  # noqa
import xarray as xr


def _validate_and_transform_coordinates(x, y, model, crs):
    """
    Transform input coordinates to model's CRS if necessary.

    Parameters
    ----------
    x, y : array_like
        Input coordinates
    model : xr.Dataset
        Dataset with CRS information
    crs : Any
        Input coordinate reference system

    Returns
    -------
    tuple
        (x_interp, y_interp, model_crs) - transformed coordinates and model's CRS
    """
    # Determine the CRS of input coordinates
    model_crs = model.rio.crs
    input_crs = crs
    if input_crs is None:
        try:
            input_crs = x.rio.crs
        except AttributeError:
            # No CRS in x or argument, assume input is in model's CRS
            input_crs = model_crs

    # Transform x, y to model's CRS if necessary
    if input_crs is not None and input_crs != model_crs:
        # Need to transform coordinates
        transformer = pyproj.Transformer.from_crs(input_crs, model_crs, always_xy=True)
        # Use xr.apply_ufunc to preserve xarray structure
        x_interp, y_interp = xr.apply_ufunc(
            transformer.transform,
            x,
            y,
            output_core_dims=[[], []],
            vectorize=True,
            keep_attrs=True,
        )
    else:
        # No transformation needed - x, y are already in model's CRS
        x_interp, y_interp = x, y

    return x_interp, y_interp


def _extract_velocity_parameters(velocity_model_itp):
    """
    Extract V0 and optionally standard deviation from interpolated velocity model.

    Returns
    -------
    tuple
        (v0, sd) - velocity and standard deviation (sd may be None)
    """
    if "summary_statistic" in velocity_model_itp["V0_filled"].dims:
        # Select mean for v0, sd for sd if available
        v0 = velocity_model_itp["V0_filled"].sel(
            {"summary_statistic": "mean"}, drop=True
        )
        if "sd" in velocity_model_itp["V0_filled"].summary_statistic:
            sd = velocity_model_itp["V0_filled"].sel(
                {"summary_statistic": "sd"}, drop=True
            )
        else:
            sd = None
    else:
        # No summary_statistic dimension (VELMOD 4, Groningen), use directly
        v0 = velocity_model_itp["V0_filled"]
        sd = None

    return v0, sd


def _compute_s_wave_velocity(
    unit_vinst,
    z,
    velocity_model_itp,
    v0,
    unit_mask,
    vs_relationship_type=None,
    vs_intercept=None,
    vs_slope=None,
):
    """
    Compute S-wave velocity based on relationship parameters.

    Returns
    -------
    xarray.DataArray or None
        S-wave velocity field, or None if parameters are not available
    """
    has_vs_params = all(
        var in velocity_model_itp.data_vars
        for var in ["relationship_type", "vs_slope", "vs_intercept"]
    )
    # User provides uniform VS if they specify relationship type and at least one parameter
    use_uniform_vs = vs_relationship_type is not None and (
        vs_intercept is not None or vs_slope is not None
    )

    if not (has_vs_params or use_uniform_vs):
        return None

    # Get parameters from model or use uniform values
    if has_vs_params:
        # Model has embedded Vp-Vs parameters (e.g., Groningen)
        # Groningen format: vs_slope, vs_intercept
        rel_type = velocity_model_itp["relationship_type"]
        vs_slope = velocity_model_itp["vs_slope"]
        vs_intercept = velocity_model_itp["vs_intercept"]
        use_model_params = True
    else:
        # Using uniform user-provided parameters (e.g., VELMOD)
        # User parameters: vs_intercept, vs_slope (for linear)
        rel_type = xr.full_like(v0, vs_relationship_type, dtype=object)
        vs_slope = xr.full_like(v0, vs_slope if vs_slope is not None else 0.0)
        vs_intercept = xr.full_like(v0, vs_intercept)
        use_model_params = False

    # Compute S-wave velocity for each unit based on relationship type
    unit_vs = xr.zeros_like(unit_vinst)

    for unit_name in unit_vinst["unit"].values:
        # Get P-wave velocity for this unit
        vp_unit = unit_vinst.sel(unit=unit_name)

        # Get parameters for this unit
        rel_type_unit = rel_type.sel(unit=unit_name)
        vs_slope_unit = vs_slope.sel(unit=unit_name)
        vs_intercept_unit = vs_intercept.sel(unit=unit_name)

        # Compute Vs based on relationship type
        if use_model_params:
            # From model - should be consistent per unit
            rel_type_val = str(
                rel_type_unit.values.item()
                if rel_type_unit.size == 1
                else rel_type_unit.values.flat[0]
            )
        else:
            rel_type_val = vs_relationship_type

        if rel_type_val == "ratio_constant":
            # Vs = Vp / vs_slope
            vs_unit = vp_unit / vs_slope_unit
        elif rel_type_val == "ratio_depth":
            if use_model_params:
                # Groningen: vs_slope=depth_coef, vs_intercept=base_ratio
                # Formula: Vs = Vp / (vs_intercept + vs_slope*depth)
                vs_unit = vp_unit / (vs_intercept_unit + vs_slope_unit * (-z))
            else:
                # User params: vs_intercept=base_ratio, vs_slope=depth_coef
                # Formula: Vs = Vp / (vs_intercept + vs_slope*depth)
                vs_unit = vp_unit / (vs_intercept_unit + vs_slope_unit * (-z))
        elif rel_type_val == "linear":
            if use_model_params:
                # Groningen: vs_slope=slope, vs_intercept=intercept
                # Formula: Vs = vs_slope*Vp + vs_intercept
                vs_unit = vs_slope_unit * vp_unit + vs_intercept_unit
            else:
                # User params: vs_intercept, vs_slope
                # Formula: Vs = vs_intercept + vs_slope*Vp
                vs_unit = vs_intercept_unit + vs_slope_unit * vp_unit
        elif rel_type_val == "constant":
            # Vs = vs_slope (for constant, only first parameter used)
            vs_unit = xr.full_like(vp_unit, vs_slope_unit)
        else:
            # Unknown type - raise error
            raise ValueError(
                f"Unknown vs_relationship_type: {rel_type_val}. "
                f"Valid types are: 'ratio_constant', 'ratio_depth', 'linear', 'constant'"
            )

        unit_vs.loc[{"unit": unit_name}] = vs_unit

    # Apply mask and sum (S-wave velocity)
    vinst_s = unit_vs.where(unit_mask, 0.0).sum("unit")
    return vinst_s


def sample_velocity_model(
    x,
    y,
    z,
    velocity_model: xr.Dataset,
    depth_model: xr.Dataset = None,
    crs=None,
    vs_relationship_type: str = None,
    vs_intercept: float = None,
    vs_slope: float = None,
) -> xr.Dataset:
    """
    Create a collection of (interpolated) samples of the velocity model optionally including depth samples.

    Parameters
    ----------
    x, y : array_like
        Spatial coordinates of points where interpolation of velocity models is requested.
        The `x` and `y` values can be arranged in an arbitrary number of dimensions, most conveniently
        in an xarray structure. The dimensions and coordinates can have an arbitrary logical meaning,
        such as a simple list of locations, or a grid structure. The grid structure may have its own
        coordinate system, such as (inline, x-line) or spatial coordinates in a certain coordinate
        reference system (CRS). The CRS can be different from the CRS of the DGM/VELMOD models - the
        function will automatically transform coordinates if needed. CRS is detected from `x.rio.crs`
        (if available) or from the `crs` parameter. If neither is provided, coordinates are assumed
        to be in velmod's CRS. Any `y.crs` will be ignored.

    z : array_like or None
        Array of vertical locations where instantaneous velocities are requested. The vertical reference is
        NAP (sea level). Negative is down. If `z` equals None, the velocity model maps will be interpolated
        without an explicit extrapolation to depth.

    velmod: xarray.Dataset
        Represents a VELMOD model (3.1, 3.2, 4, or Groningen) as generated by the convert.py script.
        VELMOD 3.1/3.2 require separate DGM for depth data. VELMOD 4 and Groningen include their own
        depth data (tvd variable) and do not require DGM.

    dgm: xarray.Dataset, optional
        Represents the DGM-5 model as generated by the convert.py script.
        Required for VELMOD 3.1/3.2 (which lack depth data). Optional for VELMOD 4 and Groningen
        (which have built-in depth data). If None and velmod has tvd, dgm will be set equal to velmod.

    crs: Any, Optional
        The coordinate reference system (CRS) for the input `x` and `y` coordinates.
        Accepts any CRS specifier recognized by pyproj (e.g., EPSG code, CRS object).
        If not provided, the CRS is auto-detected from `x.rio.crs` (if available).
        If neither is provided, input coordinates are assumed to be in velocity_model's CRS.
        If the input CRS differs from velocity_model's CRS, coordinates are automatically transformed.

    vs_relationship_type: str, Optional
        Uniform S-wave relationship type to apply if velocity_model doesn't have S-wave parameters.
        Options: 'ratio_constant', 'ratio_depth', 'linear', 'constant'.

    vs_a: float, Optional
        Parameter 'a' for uniform S-wave relationship.

    vs_b: float, Optional
        Parameter 'b' for uniform S-wave relationship (used by ratio_depth and linear).

    Returns
    -------
    xarray.Dataset
        Dataset with the interpolated velocity model data and (optional) vertical depth samples.
        Includes P-wave velocities (Vinst) and optionally S-wave velocities (Vinst_s).

    Raises
    ------
    ValueError
        If depth_model is None and velocity_model does not contain depth data (tvd variable).
        This occurs when using VELMOD 3.1/3.2 without providing a depth model (e.g., DGM).

    """
    # Ensure spatial_ref is a coordinate (not a data variable) for rio accessor
    if "spatial_ref" in velocity_model and "spatial_ref" not in velocity_model.coords:
        velocity_model = velocity_model.set_coords("spatial_ref")
    if (
        depth_model is not None
        and "spatial_ref" in depth_model
        and "spatial_ref" not in depth_model.coords
    ):
        depth_model = depth_model.set_coords("spatial_ref")

    # Check if depth_model is needed
    has_velocity_model_depth = "tvd" in velocity_model.data_vars
    depth_model_provided = depth_model is not None

    if not depth_model_provided and not has_velocity_model_depth:
        # VELMOD 3.1/3.2 require separate depth model
        model_name = velocity_model.attrs.get("model", "Unknown")
        raise ValueError(
            f"Depth model dataset is required for {model_name}. "
            f"VELMOD 3.1 and 3.2 do not contain depth data and require a separate depth model dataset (e.g., DGM). "
            f"Either provide the depth_model parameter or use VELMOD 4/Groningen which include depth data."
        )

    # Warn if user provides vs_intercept/vs_slope but model already has Vp-Vs relationships
    has_vs_params = all(
        var in velocity_model.data_vars
        for var in ["relationship_type", "vs_slope", "vs_intercept"]
    )
    user_provided_vs_params = vs_intercept is not None or vs_slope is not None

    if has_vs_params and user_provided_vs_params:
        import warnings

        model_name = velocity_model.attrs.get("model", "Unknown model")
        warnings.warn(
            f"{model_name} already contains layer-specific Vp-Vs relationships "
            f"(relationship_type, vs_slope, vs_intercept parameters). "
            f"The provided vs_intercept={vs_intercept} and/or vs_slope={vs_slope} "
            f"will be ignored, and the model's embedded relationships will be used instead.",
            UserWarning,
            stacklevel=2,
        )

    # Transform coordinates to velocity_model's CRS and interpolate
    x_interp_vel, y_interp_vel = _validate_and_transform_coordinates(
        x, y, velocity_model, crs
    )

    import warnings

    # Suppress scipy interpolation warnings when encountering NaN values
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "invalid value encountered", RuntimeWarning)

        # Interpolate velocity model
        velocity_model_itp = velocity_model.interp(
            {"x": x_interp_vel, "y": y_interp_vel},
            method="linear",
            kwargs={"bounds_error": False, "fill_value": np.nan},
        ).sortby("ordering")

    # Handle depth model
    if depth_model_provided:
        # Separate depth model - transform and interpolate separately
        x_interp_depth, y_interp_depth = _validate_and_transform_coordinates(
            x, y, depth_model, crs
        )

        # Determine common units between velocity and depth models
        sel_units_depth = np.intersect1d(depth_model["unit"], velocity_model["unit"])

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", "invalid value encountered", RuntimeWarning
            )

            # Interpolate depth model
            depth_model_itp = (
                depth_model.sel({"unit": sel_units_depth})
                .interp(
                    {"x": x_interp_depth, "y": y_interp_depth},
                    method="linear",
                    kwargs={"bounds_error": False, "fill_value": np.nan},
                )
                .sortby("ordering")
            )

        # Re-select velocity model to match common units
        velocity_model_itp = velocity_model_itp.sel({"unit": sel_units_depth})
    else:
        # VELMOD 4 or Groningen - depth data is in velocity_model
        depth_model_itp = velocity_model_itp

    # Extract velocity parameters
    v0, sd = _extract_velocity_parameters(velocity_model_itp)

    # Use depth data from depth_model_itp (either actual depth model or velocity_model for VELMOD 4/Groningen)
    layer_depth = depth_model_itp["tvd"]

    # Build output dataset with basic parameters
    velocity_samples = xr.Dataset(
        {
            "V0": v0,
            "k": velocity_model_itp["k"],
            "depth": layer_depth,
            "ordering": (
                velocity_model_itp["ordering"]
                if "ordering" in velocity_model_itp.data_vars
                else depth_model_itp["ordering"]
            ),
        }
    )
    if sd is not None:
        velocity_samples["V0_sd"] = sd

    # Compute depth profiles if z is provided
    if z is not None:
        # Convert z to xarray if it's not already, to enable proper broadcasting
        if not isinstance(z, xr.DataArray):
            z = xr.DataArray(z, dims=["z"] if np.ndim(z) > 0 else [])

        # Create depth profiles for each unit (P-wave)
        unit_vinst = v0 - velocity_model_itp["k"] * z

        # Determine which unit is present at which depth.
        # Use <= so exact deepest-horizon samples stay in the deepest modeled unit
        # instead of falling back to the first unit when no strictly deeper surface exists.
        unit = (layer_depth <= z).idxmax("unit")
        velocity_samples["unit_samples"] = unit

        # Check if depth is below the deepest horizon
        # z < layer_depth.min() means we're deeper (more negative) than the deepest layer
        # Filter out -inf values from the DC layer before computing min
        deepest_layer = layer_depth.where(layer_depth > -np.inf).min("unit")
        below_model = z < deepest_layer

        # Check where depth data is completely missing (all NaN or non-finite) - these are invalid vertical profiles
        # This ensures consistency: no velocities where there's no depth model coverage
        # Use ~isfinite to catch both NaN and -inf values
        depth_invalid = (~np.isfinite(layer_depth)).all("unit")

        # At locations where depth is invalid, set below_model to True for all z
        # Use .where() to keep below_model where depth is valid, set True where invalid
        below_model = below_model.where(~depth_invalid, True)

        # Create corresponding mask
        unit_mask = unit_vinst["unit"] == unit
        velocity_samples["unit_mask"] = unit_mask

        # Combine to get P-wave velocity
        vinst_p = unit_vinst.where(unit_mask, 0.0).sum("unit")

        # Set velocity to NaN where we're below the deepest horizon or depth data is missing
        vinst_p = vinst_p.where(~below_model, np.nan)

        # Build velocity modes list
        vinst_modes = [vinst_p]
        mode_labels = ["P"]

        # Compute S-wave velocity if parameters are available
        vinst_s = _compute_s_wave_velocity(
            unit_vinst,
            z,
            velocity_model_itp,
            v0,
            unit_mask,
            vs_relationship_type,
            vs_intercept,
            vs_slope,
        )
        if vinst_s is not None:
            # Set S-wave velocity to NaN where we're below the deepest horizon
            vinst_s = vinst_s.where(~below_model, np.nan)
            vinst_modes.append(vinst_s)
            mode_labels.append("S")

        # Stack into a single DataArray with mode dimension
        vinst_modes_da = xr.concat(vinst_modes, dim="mode")
        vinst_modes_da = vinst_modes_da.assign_coords(mode=("mode", mode_labels))
        # Only squeeze if there's a single mode
        if len(mode_labels) == 1:
            velocity_samples["Vinst"] = vinst_modes_da.squeeze("mode")
        else:
            velocity_samples["Vinst"] = vinst_modes_da

    return velocity_samples


def sample_dgm_velmod(
    x,
    y,
    z,
    velmod: xr.Dataset = None,
    dgm: xr.Dataset = None,
    crs=None,
    vs_relationship_type: str = None,
    vs_a: float = None,
    vs_b: float = None,
    # New generalized parameter names (preferred)
    velocity_model: xr.Dataset = None,
    depth_model: xr.Dataset = None,
    vs_intercept: float = None,
    vs_slope: float = None,
) -> xr.Dataset:
    """
    Create a collection of (interpolated) samples of the velocity model optionally including depth samples.

    .. deprecated:: 1.0.0
        Use :func:`sample_velocity_model` instead. This function is kept for backward compatibility
        and will be removed in a future version. The parameters `velmod` and `dgm` are deprecated;
        use `velocity_model` and `depth_model` instead.

    Parameters
    ----------
    x, y : array_like
        Spatial coordinates of points where interpolation of velocity models is requested.
        The `x` and `y` values can be arranged in an arbitrary number of dimensions, most conveniently
        in an xarray structure. The dimensions and coordinates can have an arbitrary logical meaning,
        such as a simple list of locations, or a grid structure. The grid structure may have its own
        coordinate system, such as (inline, x-line) or spatial coordinates in a certain coordinate
        reference system (CRS). The CRS can be different from the CRS of the DGM/VELMOD models - the
        function will automatically transform coordinates if needed. CRS is detected from `x.rio.crs`
        (if available) or from the `crs` parameter. If neither is provided, coordinates are assumed
        to be in velocity_model's CRS. Any `y.crs` will be ignored.

    z : array_like or None
        Array of vertical locations where instantaneous velocities are requested. The vertical reference is
        NAP (sea level). Negative is down. If `z` equals None, the velocity model maps will be interpolated
        without an explicit extrapolation to depth.

    velmod: xarray.Dataset, deprecated
        Deprecated. Use `velocity_model` instead.
        Represents a VELMOD model (3.1, 3.2, 4, or Groningen) as generated by the convert.py script.

    dgm: xarray.Dataset, optional, deprecated
        Deprecated. Use `depth_model` instead.
        Represents the DGM-5 model as generated by the convert.py script.

    velocity_model: xarray.Dataset
        Represents a velocity model (e.g., VELMOD 3.1, 3.2, 4, or Groningen) as generated by the convert.py script.
        VELMOD 3.1/3.2 require separate depth model for depth data. VELMOD 4 and Groningen include their own
        depth data (tvd variable) and do not require a separate depth model.

    depth_model: xarray.Dataset, optional
        Represents a depth model (e.g., DGM-5) as generated by the convert.py script.
        Required for VELMOD 3.1/3.2 (which lack depth data). Optional for VELMOD 4 and Groningen
        (which have built-in depth data). If None and velocity_model has tvd, uses velocity_model for depth.

    crs: Any, Optional
        The coordinate reference system (CRS) for the input `x` and `y` coordinates.
        Accepts any CRS specifier recognized by pyproj (e.g., EPSG code, CRS object).
        If not provided, the CRS is auto-detected from `x.rio.crs` (if available).
        If neither is provided, input coordinates are assumed to be in velocity_model's CRS.
        If the input CRS differs from velocity_model's CRS, coordinates are automatically transformed.

    vs_relationship_type: str, Optional
        Uniform S-wave relationship type to apply if velocity_model doesn't have S-wave parameters.
        Options: 'ratio_constant', 'ratio_depth', 'linear', 'constant'.

    vs_a: float, Optional
        Parameter 'a' for uniform S-wave relationship.

    vs_b: float, Optional
        Parameter 'b' for uniform S-wave relationship (used by ratio_depth and linear).

    Returns
    -------
    xarray.Dataset
        Dataset with the interpolated velocity model data and (optional) vertical depth samples.
        Includes P-wave velocities (Vinst) and optionally S-wave velocities (Vinst_s).

    Raises
    ------
    ValueError
        If depth_model is None and velocity_model does not contain depth data (tvd variable).
        This occurs when using VELMOD 3.1/3.2 without providing a depth model.

    """
    import warnings

    warnings.warn(
        "sample_dgm_velmod is deprecated and will be removed in a future version. "
        "Use sample_velocity_model instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Handle backward compatibility: map old parameter names to new ones
    if velmod is not None and velocity_model is None:
        velocity_model = velmod
    if dgm is not None and depth_model is None:
        depth_model = dgm
    # Handle deprecated vs_a/vs_b parameters
    if vs_a is not None and vs_intercept is None:
        vs_intercept = vs_a
    if vs_b is not None and vs_slope is None:
        vs_slope = vs_b

    return sample_velocity_model(
        x,
        y,
        z,
        velocity_model,
        depth_model,
        crs,
        vs_relationship_type,
        vs_intercept,
        vs_slope,
    )
