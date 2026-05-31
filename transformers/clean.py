"""
Data cleaning transformer.
Handles missing values and duplicate removal.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


class CleanTransformer:
    """Transformer for data cleaning operations."""

    def __init__(self, config: dict):
        self.strategy = config.get("strategy", "fill")
        self.fill_value = config.get("fill_value", None)
        self.columns = config.get("columns", None)  # specific columns to clean
        self.drop_duplicates = config.get("drop_duplicates", False)
        self.duplicate_subset = config.get("duplicate_subset", None)

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Execute cleaning transformations."""
        df = self._handle_missing(df)
        if self.drop_duplicates:
            df = self._remove_duplicates(df)
        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values based on strategy."""
        if self.strategy == "drop":
            subset = self.columns if self.columns else None
            before = len(df)
            df = df.dropna(subset=subset)
            after = len(df)
            logger.info(f"Dropped {before - after} rows with missing values")
        elif self.strategy == "fill":
            target_cols = self.columns if self.columns else df.columns
            for col in target_cols:
                if col not in df.columns:
                    continue
                if self.fill_value is not None:
                    df[col] = df[col].fillna(self.fill_value)
                elif pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].mean())
                    logger.info(f"Filled missing in '{col}' with mean ({df[col].mean():.2f})")
                else:
                    df[col] = df[col].fillna(df[col].mode().iloc[0] if not df[col].mode().empty else "Unknown")
                    logger.info(f"Filled missing in '{col}' with mode")
        elif self.strategy == "ffill":
            df = df.fillna(method="ffill")
        elif self.strategy == "bfill":
            df = df.fillna(method="bfill")
        else:
            logger.warning(f"Unknown fill strategy: {self.strategy}")
        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate rows."""
        subset = self.duplicate_subset if self.duplicate_subset else None
        before = len(df)
        df = df.drop_duplicates(subset=subset, keep="first")
        after = len(df)
        logger.info(f"Removed {before - after} duplicate rows")
        return df
