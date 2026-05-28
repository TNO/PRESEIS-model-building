"""Tests for download functionality."""

import pytest

from preseis.model_building import download_models, get_raw_data_dir


@pytest.mark.slow
def test_download_models_basic():
    """Test basic download functionality."""
    # This test may be slow - consider marking as slow
    raw_dir = get_raw_data_dir()

    # Download with verbose=False to reduce output
    download_models(verbose=False, force=False)

    # Check that raw directory has content
    assert raw_dir.exists()
    contents = list(raw_dir.iterdir())
    # Should have downloaded at least some files
    assert len(contents) > 0


@pytest.mark.slow
def test_download_models_with_force():
    """Test download with force=True."""
    # Download again with force to ensure re-download works
    download_models(verbose=False, force=True)

    raw_dir = get_raw_data_dir()
    assert raw_dir.exists()
    contents = list(raw_dir.iterdir())
    assert len(contents) > 0


@pytest.mark.slow
def test_download_all_models():
    """Test downloading all configured models."""
    # This downloads everything - mark as slow
    download_models(verbose=True, force=False)

    raw_dir = get_raw_data_dir()

    # Check for expected subdirectories/files
    # (Adjust based on actual structure)
    assert raw_dir.exists()
    assert any(raw_dir.iterdir()), "Raw data directory should not be empty"
