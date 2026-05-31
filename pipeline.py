"""
data-pipeline-tool — Lightweight ETL Pipeline for Data Processing Automation.

Orchestrates extract → transform → load workflows with YAML configuration.
Supports CSV, JSON, SQLite, and HTTP API sources.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from transformers import (
    CleanTransformer,
    NormalizeTransformer,
    ComputeTransformer,
    FilterTransformer,
)

logger = logging.getLogger(__name__)

# Registry mapping transformer type names to handler classes
TRANSFORMER_REGISTRY = {
    "clean_missing": CleanTransformer,
    "normalize_columns": NormalizeTransformer,
    "add_column": ComputeTransformer,
    "compute": ComputeTransformer,
    "filter": FilterTransformer,
}


def load_yaml(path: str) -> dict:
    """Load and parse a YAML configuration file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


class Pipeline:
    """
    Main ETL pipeline.

    Usage:
        config = load_yaml("config.yaml")
        pipeline = Pipeline(config)
        pipeline.run()
    """

    def __init__(self, config: dict):
        self.config = config
        pipeline_cfg = config.get("pipeline", config)  # support nested or flat
        self.name = pipeline_cfg.get("name", "Unnamed Pipeline")
        self.source = pipeline_cfg.get("source", {})
        self.transformations = pipeline_cfg.get("transformations", [])
        self.output = pipeline_cfg.get("output", {})

        self.df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # EXTRACT
    # ------------------------------------------------------------------
    def extract(self, source=None) -> pd.DataFrame:
        """
        Load data from CSV, JSON, SQLite, or HTTP API.

        Args:
            source: Override source config (dict or file path string).
                    Defaults to config's 'source' field.

        Returns:
            pd.DataFrame
        """
        if source is None:
            source = self.source
        if isinstance(source, str):
            source = {"path": source}
        if isinstance(source, dict):
            path = source.get("path", "")
            filetype = source.get("type", self._infer_type(path))
            url = source.get("url", "")
            query = source.get("query", "")
        else:
            raise ValueError(f"Invalid source: {source}")

        if url:
            self.df = self._extract_api(url, source)
        elif path.lower().endswith(".csv") or filetype == "csv":
            self.df = self._extract_csv(path, source)
        elif path.lower().endswith(".json") or filetype == "json":
            self.df = self._extract_json(path, source)
        elif path.lower().endswith((".db", ".sqlite", ".sqlite3")) or filetype == "sqlite":
            self.df = self._extract_sqlite(path, query, source)
        elif query:
            self.df = self._extract_sqlite(path, query, source)
        else:
            raise ValueError(f"Unsupported source: {path}")

        logger.info(f"Extracted {len(self.df)} rows from {path or url}")
        return self.df

    # noinspection PyMethodMayBeStatic
    def _extract_csv(self, path: str, cfg: dict) -> pd.DataFrame:
        path = self._resolve_path(path)
        kwargs = {
            "encoding": cfg.get("encoding", "utf-8"),
            "sep": cfg.get("delimiter", ","),
            "dtype": cfg.get("dtypes", None),
        }
        if "parse_dates" in cfg:
            kwargs["parse_dates"] = cfg["parse_dates"]
        return pd.read_csv(path, **kwargs)

    # noinspection PyMethodMayBeStatic
    def _extract_json(self, path: str, cfg: dict) -> pd.DataFrame:
        path = self._resolve_path(path)
        if "orient" in cfg:
            with open(path, "r") as f:
                data = json.load(f)
            return pd.json_normalize(data) if isinstance(data, list) else pd.DataFrame.from_dict(data, orient=cfg["orient"])
        return pd.read_json(path, encoding=cfg.get("encoding", "utf-8"))

    # noinspection PyMethodMayBeStatic
    def _extract_sqlite(self, path: str, query: str, cfg: dict) -> pd.DataFrame:
        path = self._resolve_path(path)
        query = query or cfg.get("query", "SELECT * FROM data")
        conn = sqlite3.connect(path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    # noinspection PyMethodMayBeStatic
    def _extract_api(self, url: str, cfg: dict) -> pd.DataFrame:
        import requests
        headers = cfg.get("headers", {})
        params = cfg.get("params", {})
        resp = requests.get(url, headers=headers, params=params, timeout=cfg.get("timeout", 30))
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return pd.json_normalize(data)
        if isinstance(data, dict):
            key = cfg.get("data_key", None)
            records = data[key] if key and key in data else data
            if isinstance(records, list):
                return pd.json_normalize(records)
            return pd.DataFrame.from_dict(records, orient="index")
        raise ValueError(f"Unexpected API response type: {type(data)}")

    # ------------------------------------------------------------------
    # TRANSFORM
    # ------------------------------------------------------------------
    def transform(self, transformations: Optional[list] = None) -> pd.DataFrame:
        """
        Apply a list of transformations sequentially.

        Args:
            transformations: List of transformation config dicts.
                             Defaults to config's 'transformations'.

        Returns:
            pd.DataFrame (also stored in self.df)
        """
        if self.df is None:
            raise RuntimeError("No data loaded. Call extract() first.")

        transformations = transformations or self.transformations
        logger.info(f"Applying {len(transformations)} transformation(s)")

        for i, t_cfg in enumerate(transformations):
            t_type = t_cfg.get("type", "")
            t_cls = TRANSFORMER_REGISTRY.get(t_type)

            if t_cls is None:
                logger.warning(f"Unknown transformer type: '{t_type}' — skipping")
                continue

            transformer = t_cls(t_cfg)
            self.df = transformer.run(self.df)
            logger.info(f"  [{i + 1}/{len(transformations)}] '{t_type}' → {len(self.df)} rows")

        return self.df

    # ------------------------------------------------------------------
    # LOAD
    # ------------------------------------------------------------------
    def load(self, output: Optional[dict] = None) -> str:
        """
        Save processed data to file.

        Args:
            output: Output config dict. Defaults to config's 'output'.

        Returns:
            Path to the saved file.
        """
        if self.df is None:
            raise RuntimeError("No data to save. Run extract() and transform() first.")

        output = output or self.output
        fmt = output.get("format", "csv")
        path = self._resolve_path(output.get("path", f"output.{fmt}"), create_parent=True)

        if fmt == "excel" or fmt == "xlsx":
            self._write_excel(path, output)
        elif fmt == "csv":
            kwargs = {"encoding": output.get("encoding", "utf-8"), "index": output.get("index", False)}
            self.df.to_csv(path, **kwargs)
        elif fmt == "json":
            orient = output.get("orient", "records")
            self.df.to_json(path, orient=orient, indent=2)
        elif fmt == "sqlite":
            self._write_sqlite(path, output)
        else:
            raise ValueError(f"Unsupported output format: {fmt}")

        logger.info(f"Saved {len(self.df)} rows → {path}")
        return path

    # noinspection PyMethodMayBeStatic
    def _write_excel(self, path: str, cfg: dict):
        import openpyxl.utils
        sheet_name = cfg.get("sheet_name", "Sheet1")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            self.df.to_excel(writer, sheet_name=sheet_name, index=cfg.get("index", False))
            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(self.df.columns, 1):
                # Convert to string safely, handling NaN/NaT
                str_vals = self.df[col_name].dropna().astype(str)
                data_max = str_vals.map(len).max() if not str_vals.empty else 0
                max_len = max(data_max, len(str(col_name))) + 2
                worksheet.column_dimensions[
                    openpyxl.utils.get_column_letter(col_idx)
                ].width = min(max_len, 60)

    # noinspection PyMethodMayBeStatic
    def _write_sqlite(self, path: str, cfg: dict):
        table_name = cfg.get("table_name", "data")
        if_exists = cfg.get("if_exists", "replace")
        conn = sqlite3.connect(path)
        self.df.to_sql(table_name, conn, if_exists=if_exists, index=cfg.get("index", False))
        conn.close()

    # ------------------------------------------------------------------
    # RUN (full pipeline)
    # ------------------------------------------------------------------
    def run(self, source: Optional[dict] = None,
            transformations: Optional[list] = None,
            output: Optional[dict] = None) -> pd.DataFrame:
        """Run the full ETL pipeline: extract → transform → load."""
        logger.info(f"=== Pipeline: {self.name} ===")
        self.extract(source)
        self.transform(transformations)
        result_path = self.load(output)
        logger.info(f"=== Done → {result_path} ===")
        return self.df

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    @staticmethod
    def _infer_type(path: str) -> str:
        ext = Path(path).suffix.lower()
        return {"csv": "csv", "json": "json", "db": "sqlite", "sqlite": "sqlite", "sqlite3": "sqlite"}.get(ext, "csv")

    @staticmethod
    def _resolve_path(path: str, create_parent: bool = False) -> str:
        """Resolve relative paths to the project root."""
        p = Path(path)
        if not p.is_absolute():
            p = Path.cwd() / p
        if create_parent:
            p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)
