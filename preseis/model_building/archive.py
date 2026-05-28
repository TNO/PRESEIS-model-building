"""Helpers for staging processed model files for archive publishing."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .utils import (
    get_available_model_names,
    get_default_model_names,
    get_model_output_file,
    get_package_root,
    get_processed_data_dir,
    load_config,
    open_model_dataset,
)


def _is_publishable_model_file(model_path: Path) -> bool:
    """Return True when a processed model file can be opened with the canonical backend."""
    dataset = None
    try:
        dataset = open_model_dataset(model_path, fallback_to_default=False)
        return True
    except Exception:
        return False
    finally:
        if dataset is not None:
            dataset.close()


def get_archive_output_dir(output_dir=None) -> Path:
    """Return the gitignored output directory for staged archive artifacts."""
    return Path(output_dir) if output_dir else get_package_root() / "build" / "zenodo"


def stage_processed_models_for_archive(
    processed_dir=None,
    output_dir=None,
    config_path=None,
    include_variants=True,
    strict=False,
):
    """Stage processed model files and build a publishable archive manifest."""
    config = load_config(config_path)
    processed_dir = Path(processed_dir) if processed_dir else get_processed_data_dir()
    output_dir = get_archive_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    archive_name = config.get("xarray_archive", {}).get("filename")
    if not archive_name:
        archive_name = "preseis-model-building-xarray-models.zip"

    requested_models = (
        get_available_model_names(config=config)
        if include_variants
        else get_default_model_names(config=config)
    )
    expected_files = [get_model_output_file(model_name, config=config) for model_name in requested_models]

    stage_dir = output_dir / "staged-files"
    stage_dir.mkdir(parents=True, exist_ok=True)
    for existing_file in stage_dir.iterdir():
        if existing_file.is_file():
            existing_file.unlink()

    staged_files = []
    missing_files = []
    invalid_files = []
    for filename in expected_files:
        source_path = processed_dir / filename
        target_path = stage_dir / filename
        if source_path.exists():
            if _is_publishable_model_file(source_path):
                shutil.copy2(source_path, target_path)
                staged_files.append(filename)
            else:
                invalid_files.append(filename)
        else:
            missing_files.append(filename)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_processed_dir": str(processed_dir.resolve()),
        "archive_name": archive_name,
        "requested_models": requested_models,
        "staged_files": staged_files,
        "missing_files": missing_files,
        "invalid_files": invalid_files,
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    summary_path = output_dir / "README.txt"
    summary_lines = [
        "Zenodo xarray archive staging",
        f"Source processed directory: {processed_dir.resolve()}",
        f"Archive name: {archive_name}",
        f"Staged files: {len(staged_files)}",
        f"Missing files: {len(missing_files)}",
        f"Invalid files: {len(invalid_files)}",
    ]
    if missing_files:
        summary_lines.append("")
        summary_lines.append("Missing files:")
        summary_lines.extend(f"- {filename}" for filename in missing_files)
    if invalid_files:
        summary_lines.append("")
        summary_lines.append("Invalid files:")
        summary_lines.extend(f"- {filename}" for filename in invalid_files)
    summary_path.write_text("\n".join(summary_lines) + "\n")

    archive_path = output_dir / archive_name
    if staged_files:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(manifest_path, arcname="manifest.json")
            for filename in staged_files:
                archive.write(stage_dir / filename, arcname=filename)
    elif archive_path.exists():
        archive_path.unlink()

    if strict and (missing_files or invalid_files):
        raise FileNotFoundError(
            "Missing or invalid processed model files for archive packaging: "
            f"missing={missing_files}, invalid={invalid_files}"
        )

    return {
        "archive_path": archive_path if staged_files else None,
        "manifest_path": manifest_path,
        "summary_path": summary_path,
        "stage_dir": stage_dir,
        "staged_files": staged_files,
        "missing_files": missing_files,
        "invalid_files": invalid_files,
    }