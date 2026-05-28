"""Shared helpers for example notebooks and exploratory model comparisons."""

import warnings
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd
import pyproj
import xarray as xr

from .sampling import sample_velocity_model
from .utils import get_model_output_file, get_processed_data_dir, load_model_dataset


KNMI_STATION_URL = "http://rdsa.knmi.nl/fdsnws/station/1/query?network=NL&format=text"
DEFAULT_VS_PARAMETERS = {
    "vs_relationship_type": "linear",
    "vs_intercept": -1172.0,
    "vs_slope": 0.862,
}
DEFAULT_EXAMPLE_MODELS = (
    "dgm",
    "velmod-3.1",
    "velmod-3.2",
    "velmod-4",
    "groningen",
    "groningen-no-anhydrite",
)


def load_example_models(
    model_names: Optional[Sequence[str]] = None,
    *,
    data_dir: Optional[Path] = None,
) -> dict:
    """Load processed model datasets used by the example notebooks."""
    requested_model_names = list(dict.fromkeys(model_names or DEFAULT_EXAMPLE_MODELS))
    resolved_data_dir = Path(data_dir) if data_dir is not None else get_processed_data_dir()

    return {
        model_name: load_model_dataset(
            resolved_data_dir / get_model_output_file(model_name)
        )
        for model_name in requested_model_names
    }


def load_knmi_stations(url: str = KNMI_STATION_URL) -> xr.Dataset:
    """Load KNMI station metadata as an xarray dataset indexed by station code."""
    station_frame = pd.read_csv(url, sep="|", index_col=1).rename_axis(index="Station")
    station_frame = station_frame.loc[~station_frame.index.duplicated(keep="first")]
    return xr.Dataset.from_dataframe(station_frame).sortby("Station")


def make_depth_axis(max_depth: float = 5000.0, sample_count: int = 500) -> xr.DataArray:
    """Return sampling depths with a positive-down meter coordinate for plotting."""
    depth_values = np.linspace(0.0, -float(max_depth), sample_count)
    return xr.DataArray(
        depth_values,
        dims=["z"],
        coords={"z": -depth_values},
        name="z",
        attrs={"units": "m"},
    )


def make_local_volume_grid(
    center_lon: float,
    center_lat: float,
    *,
    half_width_km: float = 3.0,
    point_count: int = 25,
    x_dim: str = "easting_km",
    y_dim: str = "northing_km",
) -> xr.Dataset:
    """Return a small regular longitude/latitude grid around one center point."""
    if point_count < 2:
        raise ValueError("point_count must be at least 2.")

    half_width_m = 1000.0 * float(half_width_km)
    if not np.isfinite(half_width_m) or half_width_m <= 0.0:
        raise ValueError("half_width_km must be a positive finite number.")

    to_xy = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_lonlat = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    center_x_m, center_y_m = to_xy.transform(float(center_lon), float(center_lat))

    offsets_m = np.linspace(-half_width_m, half_width_m, int(point_count))
    grid_x_m, grid_y_m = np.meshgrid(center_x_m + offsets_m, center_y_m + offsets_m)
    longitude_values, latitude_values = to_lonlat.transform(grid_x_m, grid_y_m)
    offsets_km = offsets_m / 1000.0

    return xr.Dataset(
        data_vars={
            "longitude": xr.DataArray(
                longitude_values,
                dims=[y_dim, x_dim],
                coords={y_dim: offsets_km, x_dim: offsets_km},
                attrs={"units": "degrees_east"},
            ),
            "latitude": xr.DataArray(
                latitude_values,
                dims=[y_dim, x_dim],
                coords={y_dim: offsets_km, x_dim: offsets_km},
                attrs={"units": "degrees_north"},
            ),
        },
        coords={
            x_dim: xr.DataArray(offsets_km, dims=[x_dim], attrs={"units": "km"}),
            y_dim: xr.DataArray(offsets_km, dims=[y_dim], attrs={"units": "km"}),
        },
        attrs={
            "center_longitude": float(center_lon),
            "center_latitude": float(center_lat),
            "crs": "EPSG:4326",
        },
    )


def make_section_line(
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float,
    *,
    point_count: int = 100,
    dim: str = "inline",
) -> xr.Dataset:
    """Return longitude/latitude samples and cumulative distance for a straight section."""
    return make_polyline_section_line(
        [start_lon, end_lon],
        [start_lat, end_lat],
        point_count=point_count,
        dim=dim,
    )


def make_polyline_section_line(
    longitudes,
    latitudes,
    *,
    point_count: int = 100,
    dim: str = "inline",
) -> xr.Dataset:
    """Return equally spaced samples along a polyline section in longitude/latitude."""
    longitude_values = np.asarray(longitudes, dtype=float)
    latitude_values = np.asarray(latitudes, dtype=float)
    if longitude_values.ndim != 1 or latitude_values.ndim != 1:
        raise ValueError("Section waypoints must be one-dimensional sequences.")
    if longitude_values.shape != latitude_values.shape:
        raise ValueError("Longitude and latitude waypoint arrays must have matching shapes.")
    if longitude_values.size < 2:
        raise ValueError("At least two section waypoints are required.")

    section_index = np.arange(point_count)
    geod = pyproj.Geod(ellps="WGS84")
    _, _, segment_length_m = geod.inv(
        longitude_values[:-1],
        latitude_values[:-1],
        longitude_values[1:],
        latitude_values[1:],
    )
    cumulative_distance_m = np.concatenate(([0.0], np.cumsum(segment_length_m)))
    total_distance_m = float(cumulative_distance_m[-1])
    if np.isclose(total_distance_m, 0.0):
        raise ValueError("Section waypoints must span a non-zero distance.")

    sample_distance_m = np.linspace(0.0, total_distance_m, point_count)
    lon = xr.DataArray(
        np.interp(sample_distance_m, cumulative_distance_m, longitude_values),
        dims=[dim],
        coords={dim: section_index},
        name="longitude",
    )
    lat = xr.DataArray(
        np.interp(sample_distance_m, cumulative_distance_m, latitude_values),
        dims=[dim],
        coords={dim: section_index},
        name="latitude",
    )

    return xr.Dataset(
        data_vars={"longitude": lon, "latitude": lat},
        coords={dim: section_index, "distance_km": (dim, sample_distance_m / 1000.0)},
    )


def sample_processed_model(
    model: xr.Dataset,
    x,
    y,
    z,
    *,
    crs=None,
    depth_model: Optional[xr.Dataset] = None,
    vs_parameters: Optional[dict] = None,
) -> xr.Dataset:
    """Sample a processed model with sensible defaults for the example workflows."""
    sampling_kwargs = {
        "x": x,
        "y": y,
        "z": z,
        "crs": crs,
        "velocity_model": model,
    }

    if depth_model is not None and "tvd" not in model.data_vars:
        sampling_kwargs["depth_model"] = depth_model

    has_embedded_vs = all(
        var_name in model.data_vars
        for var_name in ("relationship_type", "vs_slope", "vs_intercept")
    )
    if vs_parameters is None:
        vs_parameters = DEFAULT_VS_PARAMETERS
    if vs_parameters is not None and not has_embedded_vs:
        sampling_kwargs.update(vs_parameters)

    return sample_velocity_model(**sampling_kwargs)


def sample_model_collection(
    models: Mapping[str, xr.Dataset],
    model_names: Sequence[str],
    x,
    y,
    z,
    *,
    crs=None,
    depth_model: Optional[xr.Dataset] = None,
    depth_model_name: str = "dgm",
    vs_parameters: Optional[dict] = None,
) -> dict:
    """Sample a group of processed models on the same coordinates."""
    resolved_depth_model = depth_model if depth_model is not None else models.get(depth_model_name)
    return {
        model_name: sample_processed_model(
            models[model_name],
            x,
            y,
            z,
            crs=crs,
            depth_model=resolved_depth_model,
            vs_parameters=vs_parameters,
        )
        for model_name in model_names
    }


def select_mode(sampled_model: xr.Dataset, mode: str = "P") -> xr.DataArray:
    """Return one velocity mode from a sampled model dataset."""
    velocity = sampled_model["Vinst"]
    if "mode" not in velocity.dims:
        if mode != "P":
            raise KeyError(f"Requested mode {mode!r} from a P-wave-only sample.")
        return velocity
    return velocity.sel(mode=mode)


def with_distance_km(sampled_model: xr.Dataset, section: xr.Dataset) -> xr.Dataset:
    """Attach cumulative section distance and use it as the inline dimension."""
    return sampled_model.assign_coords(distance_km=section["distance_km"]).swap_dims(
        {"inline": "distance_km"}
    )


def plot_section_map(
    ax,
    stations: xr.Dataset,
    section: xr.Dataset,
    *,
    basemap_provider=None,
    zoom="auto",
):
    """Plot KNMI stations and a cross-section trace on a tiled web basemap."""
    try:
        import contextily as ctx
    except ImportError as exc:
        raise ImportError(
            "plot_section_map requires contextily. Install notebook dependencies "
            "with `uv pip install -e '.[dev]'`."
        ) from exc

    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    station_names = [str(name) for name in stations["Station"].values]
    station_lon = np.asarray(stations["Longitude"].values, dtype=float)
    station_lat = np.asarray(stations["Latitude"].values, dtype=float)
    station_x, station_y = transformer.transform(station_lon, station_lat)

    section_lon = np.asarray(section["longitude"].values, dtype=float)
    section_lat = np.asarray(section["latitude"].values, dtype=float)
    section_x, section_y = transformer.transform(section_lon, section_lat)

    ax.plot(section_x, section_y, color="C3", linewidth=2.5, zorder=3)
    ax.scatter(
        station_x,
        station_y,
        s=52,
        color="white",
        edgecolor="black",
        linewidth=1.0,
        zorder=4,
    )

    for station_name, x_coord, y_coord in zip(station_names, station_x, station_y):
        ax.annotate(
            station_name,
            (x_coord, y_coord),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 1.5},
            zorder=5,
        )

    all_x = np.concatenate([station_x, section_x])
    all_y = np.concatenate([station_y, section_y])
    x_center = float(np.mean([np.min(all_x), np.max(all_x)]))
    y_center = float(np.mean([np.min(all_y), np.max(all_y)]))
    max_span = max(float(np.ptp(all_x)), float(np.ptp(all_y)), 1000.0)
    half_span = max_span * 0.6
    ax.set_xlim(x_center - half_span, x_center + half_span)
    ax.set_ylim(y_center - half_span, y_center + half_span)

    provider = basemap_provider or ctx.providers.CartoDB.Positron
    try:
        ctx.add_basemap(ax, source=provider, zoom=zoom, attribution_size=6)
    except Exception as exc:
        warnings.warn(f"Could not load basemap tiles: {exc}", stacklevel=2)

    ax.set_aspect("equal")
    ax.set_axis_off()
    return ax


def format_depth_axis(ax, depth_values, label: str = "Depth (m)"):
    """Label a depth axis and force a positive-down display in meters."""
    depth_array = np.asarray(depth_values)
    ax.set_ylabel(label)
    ax.set_ylim(float(np.nanmax(depth_array)), float(np.nanmin(depth_array)))
    return ax


__all__ = [
    "DEFAULT_EXAMPLE_MODELS",
    "DEFAULT_VS_PARAMETERS",
    "format_depth_axis",
    "KNMI_STATION_URL",
    "load_example_models",
    "load_knmi_stations",
    "make_depth_axis",
    "make_local_volume_grid",
    "make_polyline_section_line",
    "make_section_line",
    "plot_section_map",
    "sample_model_collection",
    "sample_processed_model",
    "select_mode",
    "with_distance_km",
]