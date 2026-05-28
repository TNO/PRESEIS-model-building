"""Download raw model archives or preconverted xarray model files."""

import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

import wget

from .utils import (
    get_available_model_names,
    get_model_output_file,
    get_processed_data_dir,
    get_raw_data_dir,
    load_config,
    normalize_model_name,
)


def _resolve_requested_model_keys(models, config):
    """Resolve requested model names to config keys."""
    requested_models = list(config["models"].keys()) if models is None else list(models)
    resolved_models = []

    for model_name in requested_models:
        model_key = normalize_model_name(model_name, config=config)
        if model_key not in config["models"]:
            available = get_available_model_names(config=config)
            raise KeyError(
                f"Model '{model_name}' not found. Available models: {available}"
            )
        if model_key not in resolved_models:
            resolved_models.append(model_key)

    return resolved_models


def _resolve_requested_output_files(models, config):
    """Resolve requested setup model names to processed output filenames."""
    requested_models = list(config["models"].keys()) if models is None else list(models)
    output_files = []

    for model_name in requested_models:
        output_file = get_model_output_file(model_name, config=config)

        if output_file not in output_files:
            output_files.append(output_file)

    return output_files


def _download_file(url, destination, force=False, verbose=False):
    """Download a file to a destination path."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not force:
        if verbose:
            print(f"  ✓ {destination.name} exists (skipped)")
        return destination

    if verbose:
        print(f"  → Downloading {destination.name}...")

    tmpfile = wget.download(url, out=str(destination))
    tmpfile_path = Path(tmpfile)
    if tmpfile_path.resolve() != destination.resolve():
        if destination.exists():
            destination.unlink()
        tmpfile_path.replace(destination)

    if verbose:
        print()

    return destination


def _get_safe_member_path(member_name):
    """Return a safe relative path for an archive member."""
    member_path = PurePosixPath(member_name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError(f"Unsafe archive member path: {member_name}")

    safe_parts = [part for part in member_path.parts if part not in {"", "."}]
    return Path(*safe_parts)


def _write_stream_to_path(source, destination):
    """Write an extracted archive member to disk."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        shutil.copyfileobj(source, handle)


def _extract_zip_member(archive, member_name, target_path, force=False, verbose=False):
    """Extract a single ZIP member to disk."""
    if target_path.exists() and not force:
        if verbose:
            print(f"  ✓ {target_path.name} exists (skipped)")
        return target_path

    if verbose:
        print(f"  → Extracting {target_path.name}...")

    with archive.open(member_name) as source:
        _write_stream_to_path(source, target_path)

    return target_path


def _extract_tar_member(archive, member, target_path, force=False, verbose=False):
    """Extract a single TAR member to disk."""
    if target_path.exists() and not force:
        if verbose:
            print(f"  ✓ {target_path.name} exists (skipped)")
        return target_path

    if verbose:
        print(f"  → Extracting {target_path.name}...")

    source = archive.extractfile(member)
    if source is None:
        raise FileNotFoundError(f"Could not extract archive member: {member.name}")

    with source:
        _write_stream_to_path(source, target_path)

    return target_path


def _extract_selected_processed_zip(
    archive_path, output_dir, output_files, force=False, verbose=False
):
    """Extract selected processed model files from a ZIP archive."""
    with zipfile.ZipFile(archive_path) as archive:
        members_by_name = {
            PurePosixPath(member_name).name: member_name
            for member_name in archive.namelist()
            if not member_name.endswith("/")
        }

        missing = [name for name in output_files if name not in members_by_name]
        if missing:
            raise FileNotFoundError(
                f"Processed model files not found in {archive_path.name}: {missing}"
            )

        for output_file in output_files:
            member_name = members_by_name[output_file]
            target_path = output_dir / output_file
            _extract_zip_member(
                archive,
                member_name,
                target_path,
                force=force,
                verbose=verbose,
            )


def _extract_selected_processed_tar(
    archive_path, output_dir, output_files, force=False, verbose=False
):
    """Extract selected processed model files from a TAR archive."""
    with tarfile.open(archive_path, "r:*") as archive:
        members_by_name = {
            PurePosixPath(member.name).name: member
            for member in archive.getmembers()
            if member.isfile()
        }

        missing = [name for name in output_files if name not in members_by_name]
        if missing:
            raise FileNotFoundError(
                f"Processed model files not found in {archive_path.name}: {missing}"
            )

        for output_file in output_files:
            member = members_by_name[output_file]
            target_path = output_dir / output_file
            _extract_tar_member(
                archive,
                member,
                target_path,
                force=force,
                verbose=verbose,
            )


def _extract_raw_archives(filelist, force=False, verbose=False):
    """Extract raw archive downloads into their per-model folders."""
    if verbose:
        print("\nExtracting model files...")

    for archive_path in filelist:
        folder = archive_path.parent
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path) as archive:
                for member_name in archive.namelist():
                    if member_name.endswith("/"):
                        continue
                    if not member_name.endswith(
                        ("on_offshore_merge_DGM50_ED50_UTM31.zmap", ".dat")
                    ):
                        continue

                    relative_path = _get_safe_member_path(member_name)
                    target_path = folder / relative_path
                    _extract_zip_member(
                        archive,
                        member_name,
                        target_path,
                        force=force,
                        verbose=verbose,
                    )
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, "r:*") as archive:
                for member in archive.getmembers():
                    if not member.isfile():
                        continue
                    relative_path = _get_safe_member_path(member.name)
                    target_path = folder / relative_path
                    _extract_tar_member(
                        archive,
                        member,
                        target_path,
                        force=force,
                        verbose=verbose,
                    )


def _download_raw_models(config, raw_dir, models=None, force=False, verbose=False):
    """Download raw source archives for selected models."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    model_keys = _resolve_requested_model_keys(models, config)

    if verbose:
        print("Downloading raw model files...")
        print(f"Data directory: {raw_dir}")

    filelist = []
    for model_key in model_keys:
        model_config = config["models"][model_key]
        folder = raw_dir / model_config["directory"]
        folder.mkdir(parents=True, exist_ok=True)

        for entry in model_config["downloads"]:
            if isinstance(entry, dict):
                url = entry["url"]
                filename = folder / entry["filename"]
            else:
                url = entry
                filename = folder / wget.detect_filename(url)

            _download_file(url, filename, force=force, verbose=verbose)
            filelist.append(filename)

    _extract_raw_archives(filelist, force=force, verbose=verbose)

    if verbose:
        print(f"\n✓ Download complete! Files in: {raw_dir}")

    return raw_dir


def _download_processed_models(
    config,
    processed_dir,
    models=None,
    force=False,
    verbose=False,
    zenodo_url=None,
):
    """Download selected preconverted processed model files."""
    processed_dir.mkdir(parents=True, exist_ok=True)

    archive_config = config.get("xarray_archive", {})
    archive_url = zenodo_url or archive_config.get("url")
    if not archive_url:
        raise ValueError(
            "No xarray archive URL configured. Set xarray_archive.url in config/config.yaml "
            "or pass zenodo_url."
        )

    archive_filename = archive_config.get("filename")
    if not archive_filename:
        archive_filename = Path(archive_url.split("?")[0]).name or "xarray_models.zip"

    output_files = _resolve_requested_output_files(models, config)

    if verbose:
        print("Downloading preconverted xarray model files...")
        print(f"Processed data directory: {processed_dir}")

    archive_path = processed_dir / archive_filename
    _download_file(archive_url, archive_path, force=force, verbose=verbose)

    if zipfile.is_zipfile(archive_path):
        _extract_selected_processed_zip(
            archive_path,
            processed_dir,
            output_files,
            force=force,
            verbose=verbose,
        )
    elif tarfile.is_tarfile(archive_path):
        _extract_selected_processed_tar(
            archive_path,
            processed_dir,
            output_files,
            force=force,
            verbose=verbose,
        )
    else:
        raise ValueError(
            f"Unsupported processed archive format for {archive_path.name}. "
            "Use a ZIP or TAR archive."
        )

    if verbose:
        print(f"\n✓ Download complete! Files in: {processed_dir}")

    return processed_dir


def download_models(
    raw_dir=None,
    force=False,
    verbose=False,
    config_path=None,
    processed_dir=None,
    models=None,
    source="raw",
    zenodo_url=None,
):
    """
    Download raw model archives or preconverted xarray model files.

    Supports two sources:
    - ``raw``: download raw ZIP/TAR archives and extract ZMAP/dat inputs.
    - ``xarray``: download a preconverted processed archive (for example from
      Zenodo) and extract selected ``.h5`` model files.

    Parameters
    ----------
    raw_dir : Path or str, optional
        Directory for raw archive downloads and extractions.
        If None, uses the default from get_raw_data_dir().
    force : bool, optional
        If True, re-download files even if they already exist. Default False.
    verbose : bool, optional
        If True, print progress messages. Default False.
    config_path : str or Path, optional
        Path to config file. If None, defaults to config/config.yaml.
    processed_dir : Path or str, optional
        Directory for processed xarray model files.
        If None, uses the default from get_processed_data_dir().
    models : sequence of str, optional
        Subset of models to download. Accepts config keys (``velmod31``) or
        setup aliases (``velmod-3.1``, ``groningen-no-anhydrite``).
    source : {"raw", "xarray"}, optional
        Download source. ``raw`` downloads source archives, ``xarray``
        downloads a preconverted processed archive. Default ``raw``.
    zenodo_url : str, optional
        Override URL for the processed xarray archive when ``source='xarray'``.

    Returns
    -------
    Path
        Path to the directory containing the downloaded files
    """
    config = load_config(config_path)

    if source == "raw":
        downloads_dir = Path(raw_dir) if raw_dir else get_raw_data_dir()
        return _download_raw_models(
            config,
            downloads_dir,
            models=models,
            force=force,
            verbose=verbose,
        )

    if source == "xarray":
        output_dir = Path(processed_dir) if processed_dir else get_processed_data_dir()
        return _download_processed_models(
            config,
            output_dir,
            models=models,
            force=force,
            verbose=verbose,
            zenodo_url=zenodo_url,
        )

    raise ValueError("source must be either 'raw' or 'xarray'")
