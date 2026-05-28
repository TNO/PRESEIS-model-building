#!/usr/bin/env python
"""Complete setup for configured PRESEIS model data."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for preseis import
sys.path.insert(0, str(Path(__file__).parent.parent))

from preseis.model_building import (
    convert_dgm,
    convert_groningen,
    convert_velmod,
    download_models,
    load_model_dataset,
)
from preseis.model_building.utils import (
    expand_model_dependencies,
    get_available_model_names,
    get_default_model_names,
    get_model_output_file,
    normalize_model_name,
)


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
    default_models = get_default_model_names(config_path=config_path)

    parser = argparse.ArgumentParser(
        description="Download and convert configured PRESEIS model data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Setup all models from preconverted xarray files (Zenodo) - DEFAULT
    # Includes Groningen standard and Groningen no-anhydrite variants
  python scripts/setup_data.py
  python scripts/setup_data.py --all

    # Build from raw source archives (advanced)
    python scripts/setup_data.py --download-source raw

  # Setup only DGM depth model
  python scripts/setup_data.py --version dgm

  # Setup specific VELMOD version (automatically includes DGM for 3.1/3.2)
  python scripts/setup_data.py --version velmod-3.1
  python scripts/setup_data.py --version velmod-4

  # Setup Groningen variants
  python scripts/setup_data.py --version groningen
  python scripts/setup_data.py --version groningen-no-anhydrite

    # Download preconverted xarray files from a Zenodo archive and skip conversion
    python scripts/setup_data.py --download-source xarray --zenodo-url <zenodo-archive-url>

    # Force re-download
  python scripts/setup_data.py --force

Note: VELMOD 3.1 and 3.2 require DGM-5 for depth data and will include it automatically.
      VELMOD 4 and Groningen have built-in depth data and don't require DGM.
        """,
    )
    parser.add_argument(
        "--version",
        choices=supported_models,
        help="Specific model to setup (VELMOD, Groningen variants, or DGM)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Setup all models: VELMOD 3.1/3.2/4, Groningen, Groningen no-anhydrite, and DGM (default behavior)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download and reconversion",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=config_path,
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        help="Directory for raw data (default: data/raw)",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        help="Directory for processed data (default: data/processed)",
    )
    parser.add_argument(
        "--download-source",
        choices=["raw", "xarray"],
        default="xarray",
        help="Download raw source archives or preconverted xarray files (default: xarray)",
    )
    parser.add_argument(
        "--zenodo-url",
        help="Override URL for the processed xarray archive when --download-source=xarray",
    )

    args = parser.parse_args()

    # Determine which models to process
    if args.version:
        versions = [args.version]
    else:
        versions = list(default_models)

    versions = expand_model_dependencies(versions, config_path=args.config)

    print("=" * 70)
    print("PRESEIS Model Data Setup")
    print("=" * 70)
    print(f"\nModels to process: {', '.join(versions).upper()}")

    try:
        total_steps = 1 if args.download_source == "xarray" else 2

        print(f"\nStep 1/{total_steps}: Downloading model data...")
        print("-" * 70)
        # Download only the selected models.
        download_models(
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            force=args.force,
            verbose=True,
            config_path=args.config,
            models=versions,
            source=args.download_source,
            zenodo_url=args.zenodo_url,
        )

        if args.download_source == "raw":
            print("\n" + "=" * 70)
            print("Step 2/2: Converting to xarray format...")
            print("-" * 70)

            # Convert models in order
            for version in versions:
                if version == "dgm":
                    print("\nConverting DGM5...")
                    convert_dgm(
                        raw_dir=args.raw_dir,
                        processed_dir=args.processed_dir,
                        force=args.force,
                        verbose=True,
                    )
                elif version == "groningen":
                    print("\nConverting Groningen (standard)...")
                    ret = convert_groningen(
                        config_path=args.config,
                        raw_dir=args.raw_dir,
                        processed_dir=args.processed_dir,
                        remove_anhydrite=False,
                        verbose=True,
                    )
                    if ret != 0:
                        raise RuntimeError(f"Groningen conversion failed with code {ret}")
                elif version == "groningen-no-anhydrite":
                    print("\nConverting Groningen (no-anhydrite variant)...")
                    ret = convert_groningen(
                        config_path=args.config,
                        raw_dir=args.raw_dir,
                        processed_dir=args.processed_dir,
                        remove_anhydrite=True,
                        verbose=True,
                    )
                    if ret != 0:
                        raise RuntimeError(
                            f"Groningen no-anhydrite conversion failed with code {ret}"
                        )
                else:
                    # VELMOD: strip velmod- prefix
                    velmod_version = version.split("-")[1]
                    model_name = f"VELMOD {velmod_version}"
                    print(f"\nConverting {model_name}...")
                    convert_velmod(
                        velmod_version=version,
                        raw_dir=args.raw_dir,
                        processed_dir=args.processed_dir,
                        force=args.force,
                        verbose=True,
                    )
        else:
            print("\nSkipping conversion step: using preconverted xarray model files.")

        print("\n" + "=" * 70)
        print("✓ Setup complete!")
        print("=" * 70)

        example_data_dir = Path(args.processed_dir) if args.processed_dir else None

        print("\nYou can now use the models in your code:")
        if example_data_dir is None:
            print(
                "  from preseis.model_building import sample_velocity_model, get_processed_data_dir, load_model_dataset"
            )
            print("  data_dir = get_processed_data_dir()")
        else:
            print(
                "  from pathlib import Path"
            )
            print(
                "  from preseis.model_building import sample_velocity_model, load_model_dataset"
            )
            print(f"  data_dir = Path({str(example_data_dir)!r})")

        for v in versions:
            variable_name = normalize_model_name(v, config_path=args.config)
            if v.endswith("-no-anhydrite"):
                variable_name = f"{variable_name}_no_anhydrite"
            output_file = get_model_output_file(v, config_path=args.config)
            print(f"  {variable_name} = load_model_dataset(data_dir / '{output_file}')")

        return 0

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
