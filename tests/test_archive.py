from pathlib import Path
import json
import zipfile

import xarray as xr
import yaml

from preseis.model_building.archive import stage_processed_models_for_archive


def _write_config(tmp_path):
    config = {
        "models": {
            "dgm": {
                "output_file": "DGM5_UTM31.h5",
            },
            "velmod31": {
                "version": "3.1",
                "output_file": "VELMOD31_UTM31.h5",
            },
            "groningen": {
                "version": "groningen",
                "output_file": "GRONINGEN_2017_RD.h5",
            },
        },
        "xarray_archive": {
            "filename": "archive.zip",
        },
    }

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    return config_path


def _write_valid_model_file(path: Path, value: float) -> None:
    xr.Dataset({"value": (("x",), [value])}, coords={"x": [0.0]}).to_netcdf(
        path,
        engine="h5netcdf",
    )


def test_stage_processed_models_for_archive_creates_manifest_and_archive(tmp_path):
    config_path = _write_config(tmp_path)
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_valid_model_file(processed_dir / "DGM5_UTM31.h5", 1.0)
    _write_valid_model_file(processed_dir / "VELMOD31_UTM31.h5", 2.0)

    result = stage_processed_models_for_archive(
        processed_dir=processed_dir,
        output_dir=tmp_path / "out",
        config_path=config_path,
    )

    assert result["archive_path"] is not None
    assert result["archive_path"].exists()
    assert result["manifest_path"].exists()
    assert result["summary_path"].exists()
    assert result["staged_files"] == ["DGM5_UTM31.h5", "VELMOD31_UTM31.h5"]
    assert "GRONINGEN_2017_RD.h5" in result["missing_files"]
    assert "GRONINGEN_2017_RD_no_anhydrite.h5" in result["missing_files"]
    assert result["invalid_files"] == []

    manifest = json.loads(result["manifest_path"].read_text())
    assert manifest["archive_name"] == "archive.zip"
    assert manifest["staged_files"] == ["DGM5_UTM31.h5", "VELMOD31_UTM31.h5"]
    assert manifest["invalid_files"] == []

    with zipfile.ZipFile(result["archive_path"]) as archive:
        names = set(archive.namelist())
    assert {"manifest.json", "DGM5_UTM31.h5", "VELMOD31_UTM31.h5"}.issubset(names)


def test_stage_processed_models_for_archive_strict_mode_fails_on_missing_files(tmp_path):
    config_path = _write_config(tmp_path)
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_valid_model_file(processed_dir / "DGM5_UTM31.h5", 1.0)

    try:
        stage_processed_models_for_archive(
            processed_dir=processed_dir,
            output_dir=tmp_path / "out",
            config_path=config_path,
            strict=True,
        )
    except FileNotFoundError as exc:
        assert "Missing or invalid processed model files" in str(exc)
    else:
        raise AssertionError("Strict archive staging should fail when files are missing")


def test_stage_processed_models_for_archive_marks_invalid_files(tmp_path):
    config_path = _write_config(tmp_path)
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_valid_model_file(processed_dir / "DGM5_UTM31.h5", 1.0)
    (processed_dir / "VELMOD31_UTM31.h5").write_bytes(b"not-a-model")

    result = stage_processed_models_for_archive(
        processed_dir=processed_dir,
        output_dir=tmp_path / "out",
        config_path=config_path,
    )

    assert result["staged_files"] == ["DGM5_UTM31.h5"]
    assert result["invalid_files"] == ["VELMOD31_UTM31.h5"]
    assert "GRONINGEN_2017_RD.h5" in result["missing_files"]

    manifest = json.loads(result["manifest_path"].read_text())
    assert manifest["invalid_files"] == ["VELMOD31_UTM31.h5"]