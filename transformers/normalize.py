"""
Column normalization transformer.
Handles column renaming, type casting, and value normalization.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


class NormalizeTransformer:
    """Transformer for column normalization."""

    def __init__(self, config: dict):
        self.column_mapping = config.get("mapping", {})
        self.drop_unmapped = config.get("drop_unmapped", False)
        self.type_casts = config.get("type_casts", {})
        self.strip_whitespace = config.get("strip_whitespace", True)
        self.lowercase_columns = config.get("lowercase_columns", False)

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Execute normalization transformations."""
        if self.lowercase_columns:
            df.columns = [str(c).lower().strip() for c in df.columns]
            logger.info("Lowercased all column names")

        if self.column_mapping:
            df = self._rename_columns(df)

        if self.strip_whitespace:
            df = self._strip_all_strings(df)

        if self.type_casts:
            df = self._cast_types(df)

        return df

    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns based on mapping dict."""
        # Only rename columns that exist
        rename_map = {k: v for k, v in self.column_mapping.items() if k in df.columns}
        if not rename_map:
            logger.warning("No columns matched the rename mapping")
            return df

        df = df.rename(columns=rename_map)
        logger.info(f"Renamed columns: {rename_map}")

        if self.drop_unmapped:
            keep_cols = list(self.column_mapping.values())
            cols_to_drop = [c for c in df.columns if c not in keep_cols]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)
                logger.info(f"Dropped unmapped columns: {cols_to_drop}")

        return df

    def _strip_all_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Strip whitespace from all string columns."""
        str_cols = df.select_dtypes(include=["object", "string"]).columns
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()
        return df

    def _cast_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cast columns to specified types."""
        for col, dtype in self.type_casts.items():
            if col not in df.columns:
                continue
            try:
                if dtype == "float":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif dtype == "int":
                    df[col] = pd.to_numeric(df[col], errors="coerce").round(0).astype("Int64")
                elif dtype == "str":
                    df[col] = df[col].astype(str)
                elif dtype == "datetime":
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                elif dtype == "bool":
                    df[col] = df[col].astype(bool)
                else:
                    df[col] = df[col].astype(dtype)
                logger.info(f"Cast '{col}' to {dtype}")
            except Exception as e:
                logger.warning(f"Failed to cast '{col}' to {dtype}: {e}")
        return df
