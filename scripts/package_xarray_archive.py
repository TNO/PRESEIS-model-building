#!/usr/bin/env python
"""Stage processed xarray model files for Zenodo publishing."""

import argparse
import sys
from pathlib import Path

from preseis.model_building.archive import stage_processed_models_for_archive


def main():
    parser = argparse.ArgumentParser(
        description="Stage processed xarray model files and build a Zenodo archive"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent.parent / "config" / "config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        help="Directory containing processed .h5 model files (default: data/processed)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "build" / "zenodo",
        help="Gitignored output directory for staged archive files (default: build/zenodo)",
    )
    parser.add_argument(
        "--no-variants",
        action="store_true",
        help="Exclude optional variants such as groningen-no-anhydrite from the archive manifest",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any expected processed model files are missing",
    )

    args = parser.parse_args()

    try:
        result = stage_processed_models_for_archive(
            processed_dir=args.processed_dir,
            output_dir=args.output_dir,
            config_path=args.config,
            include_variants=not args.no_variants,
            strict=args.strict,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Staging directory: {result['stage_dir']}")
    print(f"Manifest: {result['manifest_path']}")
    print(f"Summary: {result['summary_path']}")
    print(f"Staged files: {len(result['staged_files'])}")
    if result["archive_path"] is not None:
        print(f"Archive: {result['archive_path']}")
    else:
        print("Archive: not created (no processed model files were available)")
    if result["missing_files"]:
        print("Missing files:")
        for filename in result["missing_files"]:
            print(f"  - {filename}")

    return 0


if __name__ == "__main__":
    sys.exit(main())