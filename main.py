#!/usr/bin/env python3
"""
data-pipeline-tool — CLI entry point.

Usage:
    python main.py --config config.yaml
    python main.py extract --source data.csv
    python main.py transform --config transform.yaml
    python main.py load --output report.xlsx
"""

import argparse
import logging
import sys
from pathlib import Path

from pipeline import Pipeline, load_yaml

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data-pipeline-tool",
        description="Lightweight ETL pipeline for data processing automation.",
    )
    parser.add_argument("--config", "-c", help="Path to pipeline YAML config")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Set logging level")

    sub = parser.add_subparsers(dest="command", title="commands")

    # --- extract ---
    ext = sub.add_parser("extract", help="Extract data from source")
    ext.add_argument("--source", "-s", required=True, help="Source file path or URL")
    ext.add_argument("--type", help="Source type (csv/json/sqlite/api)")
    ext.add_argument("--query", help="SQL query for SQLite source")

    # --- transform ---
    tra = sub.add_parser("transform", help="Apply transformations to data")
    tra.add_argument("--config", "-c", required=True, help="Transform config YAML")
    tra.add_argument("--input", "-i", help="Input file (parquet/feather intermediate)")

    # --- load ---
    lod = sub.add_parser("load", help="Load data to output")
    lod.add_argument("--output", "-o", required=True, help="Output file path")
    lod.add_argument("--format", "-f", choices=["excel", "csv", "json", "sqlite"],
                     help="Output format")

    return parser


def cmd_full_pipeline(args):
    """--config mode: run full pipeline from YAML."""
    cfg = load_yaml(args.config)
    pipeline = Pipeline(cfg)
    pipeline.run()


def cmd_extract(args):
    """extract command: load data and print summary."""
    source = {"path": args.source}
    if args.type:
        source["type"] = args.type
    if args.query:
        source["query"] = args.query

    pipeline = Pipeline({"pipeline": {"name": "CLI Extract"}})
    df = pipeline.extract(source)
    # Cache for next step
    df.to_pickle(".pipeline_cache.pkl")
    print(f"\nExtracted {len(df)} rows × {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")
    print(f"\nFirst 5 rows:\n{df.head().to_string(index=False)}")
    print(f"\nMissing values:\n{df.isnull().sum().to_string()}")


def cmd_transform(args):
    """transform command: apply transformations to an input file."""
    from pipeline import load_yaml as _load_yaml

    transform_cfg = _load_yaml(args.config)
    # Support both nested (pipeline.transformations) and flat (transformations) config
    transformations = (
        transform_cfg.get("pipeline", {}).get("transformations")
        or transform_cfg.get("transformations", [])
    )

    import pandas as pd
    cache_path = ".pipeline_cache.pkl"

    if args.input:
        ext = Path(args.input).suffix.lower()
        if ext == ".parquet":
            df = pd.read_parquet(args.input)
        elif ext == ".feather":
            df = pd.read_feather(args.input)
        else:
            df = pd.read_pickle(args.input)
    else:
        # Read from intermediate cache
        try:
            df = pd.read_pickle(cache_path)
        except FileNotFoundError:
            print("No input specified and no cache found. Run 'extract' first or use --input.")
            sys.exit(1)

    pipeline = Pipeline({"pipeline": {"name": "CLI Transform"}})
    pipeline.df = df
    pipeline.transform(transformations)

    # Save intermediate result
    pipeline.df.to_pickle(cache_path)
    print(f"\nTransformed: {len(pipeline.df)} rows × {len(pipeline.df.columns)} columns")
    print(f"\nFirst 5 rows:\n{pipeline.df.head().to_string(index=False)}")


def cmd_load(args):
    """load command: save data to output format."""
    import pandas as pd
    try:
        df = pd.read_pickle(".pipeline_cache.pkl")
    except FileNotFoundError:
        print("No cached data found. Run 'extract' and 'transform' first.")
        sys.exit(1)

    output = {"path": args.output}
    if args.format:
        output["format"] = args.format

    # Infer format from extension if not specified
    if "format" not in output:
        ext = Path(args.output).suffix.lower()
        fmt_map = {".xlsx": "excel", ".csv": "csv", ".json": "json", ".db": "sqlite", ".sqlite": "sqlite"}
        output["format"] = fmt_map.get(ext, "csv")

    pipeline = Pipeline({"pipeline": {"name": "CLI Load"}})
    pipeline.df = df
    path = pipeline.load(output)
    print(f"Data saved to: {path}")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
def main():
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "transform":
        cmd_transform(args)
    elif args.command == "load":
        cmd_load(args)
    else:
        # Default: full pipeline via --config
        if args.config:
            cmd_full_pipeline(args)
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
