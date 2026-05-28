#!/usr/bin/env python
"""Convert configured PRESEIS model data to HDF5 format."""

import argparse
import sys
from pathlib import Path

from preseis.model_building import convert_dgm, convert_groningen, convert_velmod
from preseis.model_building.utils import get_available_model_names


def _get_config_path_from_argv(argv):
    """Read the config path early so model choices come from that config."""
    default_config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=default_config_path)
    known_args, _ = pre_parser.parse_known_args(argv)
    return known_args.config


def main():
    """Command-line interface for model conversion."""
    config_path = _get_config_path_from_argv(sys.argv[1:])
    supported_models = get_available_model_names(config_path=config_path)
    default_model = next(
        (model_name for model_name in supported_models if model_name.startswith("velmod-")),
        supported_models[0],
    )

    parser = argparse.ArgumentParser(
        description="Convert DGM and VELMOD models to HDF5 format"
    )
    parser.add_argument(
        "--model",
        choices=supported_models,
        default=default_model,
        help="Model to convert: VELMOD (velmod-3.1, velmod-3.2, velmod-4), DGM, or Groningen variants",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        help="Directory containing raw ZMAP files (default: data/raw)",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        help="Directory for output HDF5 files (default: data/processed)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=config_path,
        help="Config file path (for Groningen model, default: config/config.yaml)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reconversion even if files exist",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print progress messages",
    )

    args = parser.parse_args()

    try:
        if args.model == "groningen":
            result = convert_groningen(
                config_path=args.config,
                raw_dir=args.raw_dir,
                processed_dir=args.processed_dir,
                remove_anhydrite=False,
                verbose=args.verbose,
            )
            sys.exit(result)
        elif args.model == "groningen-no-anhydrite":
            result = convert_groningen(
                config_path=args.config,
                raw_dir=args.raw_dir,
                processed_dir=args.processed_dir,
                remove_anhydrite=True,
                verbose=args.verbose,
            )
            sys.exit(result)
        elif args.model == "dgm":
            convert_dgm(
                raw_dir=args.raw_dir,
                processed_dir=args.processed_dir,
                force=args.force,
                verbose=args.verbose,
            )
            sys.exit(0)
        else:
            convert_velmod(
                velmod_version=args.model,
                raw_dir=args.raw_dir,
                processed_dir=args.processed_dir,
                force=args.force,
                verbose=args.verbose,
            )
            sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
