from pathlib import Path
import zipfile

import yaml

from preseis.model_building import download_models


def _write_config(tmp_path, archive_url="https://example.test/processed.zip"):
    config = {
        "models": {
            "dgm": {
                "directory": "dgmdeep5",
                "output_file": "DGM5_UTM31.h5",
                "downloads": ["https://example.test/dgm.zip"],
            },
            "velmod31": {
                "directory": "velmod31",
                "output_file": "VELMOD31_UTM31.h5",
                "downloads": ["https://example.test/velmod31.zip"],
            },
            "groningen": {
                "directory": "groningen_velocity_model",
                "output_file": "GRONINGEN_2017_RD.h5",
                "downloads": [
                    {
                        "url": "https://example.test/groningen.tar",
                        "filename": "groningen.tar",
                    }
                ],
            },
        },
        "xarray_archive": {
            "url": archive_url,
            "filename": "processed.zip",
        },
    }

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    return config_path


def test_download_models_downloads_only_selected_raw_model(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    calls = []

    def fake_download(url, out):
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        calls.append((url, out_path.name))
        with zipfile.ZipFile(out_path, "w") as archive:
            archive.writestr("nested/NU_f_V0_sk.dat", "velmod31")
        return str(out_path)

    monkeypatch.setattr("preseis.model_building.download.wget.download", fake_download)

    raw_dir = tmp_path / "raw"
    download_models(
        raw_dir=raw_dir,
        config_path=config_path,
        models=["velmod-3.1"],
    )

    assert calls == [("https://example.test/velmod31.zip", "velmod31.zip")]
    assert (raw_dir / "velmod31" / "nested" / "NU_f_V0_sk.dat").exists()
    assert not (raw_dir / "dgmdeep5").exists()


def test_download_models_extracts_only_requested_xarray_outputs(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)

    def fake_download(url, out):
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w") as archive:
            archive.writestr("VELMOD31_UTM31.h5", "velmod31")
            archive.writestr("GRONINGEN_2017_RD.h5", "groningen")
            archive.writestr("GRONINGEN_2017_RD_no_anhydrite.h5", "groningen-no-anhydrite")
            archive.writestr("DGM5_UTM31.h5", "dgm")
        return str(out_path)

    monkeypatch.setattr("preseis.model_building.download.wget.download", fake_download)

    processed_dir = tmp_path / "processed"
    download_models(
        processed_dir=processed_dir,
        config_path=config_path,
        models=["velmod-3.1", "groningen-no-anhydrite"],
        source="xarray",
    )

    assert (processed_dir / "VELMOD31_UTM31.h5").exists()
    assert (processed_dir / "GRONINGEN_2017_RD_no_anhydrite.h5").exists()
    assert not (processed_dir / "GRONINGEN_2017_RD.h5").exists()
    assert not (processed_dir / "DGM5_UTM31.h5").exists()


def test_download_models_rejects_unsafe_archive_paths(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)

    def fake_download(url, out):
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w") as archive:
            archive.writestr("../escape.dat", "bad")
        return str(out_path)

    monkeypatch.setattr("preseis.model_building.download.wget.download", fake_download)

    raw_dir = tmp_path / "raw"
    try:
        download_models(
            raw_dir=raw_dir,
            config_path=config_path,
            models=["velmod-3.1"],
        )
    except ValueError as exc:
        assert "Unsafe archive member path" in str(exc)
    else:
        raise AssertionError("Unsafe archive member path should raise ValueError")