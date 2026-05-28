#!/usr/bin/env python
"""Download raw model archives or preconverted xarray model files."""

import argparse
import sys
from pathlib import Path

from preseis.model_building import download_models
from preseis.model_building.utils import get_available_model_names


def _get_config_path_from_argv(argv):
    """Read the config path early so model choices come from that config."""
    default_config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=default_config_path)
    known_args, _ = pre_parser.parse_known_args(argv)
    return known_args.config


def main():
    config_path = _get_config_path_from_argv(sys.argv[1:])
    supported_models = get_available_model_names(config_path=config_path)

    parser = argparse.ArgumentParser(
        description="Download raw model archives or preconverted xarray model files"
    )
    parser.add_argument(
        "--model",
        nargs="+",
        choices=supported_models,
        help="Subset of models to download",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress information",
    )
    parser.add_argument(
        "--download-source",
        choices=["raw", "xarray"],
        default="xarray",
        help="Download raw source archives or preconverted xarray files (default: xarray)",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        help="Directory for raw data downloads (default: data/raw)",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        help="Directory for processed xarray files (default: data/processed)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=config_path,
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--zenodo-url",
        help="Override URL for the processed xarray archive when --download-source=xarray",
    )

    args = parser.parse_args()

    try:
        download_models(
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            force=args.force,
            verbose=args.verbose,
            config_path=args.config,
            models=args.model,
            source=args.download_source,
            zenodo_url=args.zenodo_url,
        )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
