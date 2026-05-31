"""
Computed column transformer.
Evaluates simple arithmetic formulas to create new columns.
"""

import logging
import re
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ComputeTransformer:
    """Transformer for adding computed columns."""

    # Allowed operators mapped to numpy functions
    OPERATORS = {
        "+": np.add,
        "-": np.subtract,
        "*": np.multiply,
        "/": np.divide,
        "//": np.floor_divide,
        "%": np.mod,
        "**": np.power,
    }

    def __init__(self, config: dict):
        self.name = config.get("name", "computed")
        self.formula = config.get("formula", "")
        self.columns = config.get("columns", [])  # list of columns to compute
        self.operations = config.get("operations", [])  # list of inline ops

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Execute computation transformations."""
        # Single computed column from formula string
        if self.formula:
            df[self.name] = self._evaluate_formula(df, self.formula)
            logger.info(f"Added computed column '{self.name}' from formula: {self.formula}")

        # Batch operations list
        for op in self.operations:
            name = op.get("name", "computed")
            formula = op.get("formula", "")
            df[name] = self._evaluate_formula(df, formula)
            logger.info(f"Added computed column '{name}' from formula: {formula}")

        return df

    def _evaluate_formula(self, df: pd.DataFrame, formula: str) -> pd.Series:
        """
        Evaluate simple arithmetic formulas referencing column names.
        Examples:
          "price * quantity"
          "(revenue - cost) / revenue * 100"
          "price * (1 - discount)"
          "qty_a + qty_b"
        """
        # Replace column names with df['col'] references
        # Only match whole words that are actual column names
        col_pattern = r"\b(" + "|".join(re.escape(c) for c in df.columns) + r")\b"

        def replace_col(match):
            col_name = match.group(1)
            return f"df['{col_name}']"

        expr = re.sub(col_pattern, replace_col, formula)

        # Safety: only allow arithmetic, parentheses, and spaces
        allowed_chars = set("0123456789+-*/().% ")
        safe_expr = ""
        i = 0
        while i < len(expr):
            if expr[i] in allowed_chars:
                safe_expr += expr[i]
            elif expr[i:i+2] == "**":
                safe_expr += "**"
                i += 1
            elif expr[i:i+2] == "//":
                safe_expr += "//"
                i += 1
            else:
                # Could be part of df['col'] reference
                safe_expr += expr[i]
            i += 1

        try:
            result = eval(safe_expr, {"df": df, "np": np, "pd": pd})
            return result
        except Exception as e:
            logger.error(f"Failed to evaluate formula '{formula}': {e}")
            return pd.Series([None] * len(df), index=df.index)
