"""
Row filter transformer.
Filters DataFrame rows based on conditions.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


class FilterTransformer:
    """Transformer for filtering rows by conditions."""

    def __init__(self, config: dict):
        self.condition = config.get("condition", "")
        self.conditions = config.get("conditions", [])
        self.mode = config.get("mode", "and")  # 'and' or 'or' for multiple conditions
        self.drop_na = config.get("drop_na", False)

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Execute filter transformations."""
        if df.empty:
            logger.warning("Empty DataFrame — skipping filter")
            return df

        if self.condition:
            df = self._apply_single_condition(df, self.condition)

        for cond in self.conditions:
            df = self._apply_single_condition(df, cond)

        if self.drop_na:
            before = len(df)
            df = df.dropna()
            logger.info(f"Dropped {before - len(df)} rows with any NA")

        return df

    def _apply_single_condition(self, df: pd.DataFrame, condition: str) -> pd.DataFrame:
        """
        Apply a single filter condition.
        Supports operators: >, <, >=, <=, ==, !=, in, not in, isnull, notnull
        Examples:
          "price > 0"
          "status == 'active'"
          "category in ('A', 'B', 'C')"
          "email notnull"
          "name not in ('', 'None', 'null')"
        """
        condition = condition.strip()
        before = len(df)

        try:
            if " not in " in condition:
                col, values_str = condition.split(" not in ", 1)
                col = col.strip()
                values = self._parse_values(values_str)
                df = df[~df[col].isin(values)]
            elif " in " in condition:
                col, values_str = condition.split(" in ", 1)
                col = col.strip()
                values = self._parse_values(values_str)
                df = df[df[col].isin(values)]
            elif condition.endswith(" isnull"):
                col = condition.replace(" isnull", "").strip()
                df = df[df[col].isna()]
            elif condition.endswith(" notnull"):
                col = condition.replace(" notnull", "").strip()
                df = df[df[col].notna()]
            else:
                # Standard column operator value: e.g. "price > 0"
                for op in ["!=", ">=", "<=", "==", ">", "<"]:
                    if op in condition:
                        col, val_str = condition.split(op, 1)
                        col = col.strip()
                        val_str = val_str.strip()
                        val = self._parse_value(val_str)

                        if op == ">":
                            df = df[df[col] > val]
                        elif op == "<":
                            df = df[df[col] < val]
                        elif op == ">=":
                            df = df[df[col] >= val]
                        elif op == "<=":
                            df = df[df[col] <= val]
                        elif op == "==":
                            df = df[df[col] == val]
                        elif op == "!=":
                            df = df[df[col] != val]
                        break
                else:
                    logger.warning(f"Could not parse condition: {condition}")

            after = len(df)
            logger.info(f"Filter '{condition}': {before} → {after} rows ({before - after} removed)")
            return df

        except Exception as e:
            logger.error(f"Failed to apply filter '{condition}': {e}")
            return df

    def _parse_value(self, val_str: str):
        """Parse a single value from string."""
        val_str = val_str.strip().strip("'").strip('"')
        # Try numeric
        try:
            if "." in val_str:
                return float(val_str)
            return int(val_str)
        except ValueError:
            pass
        # Try boolean
        if val_str.lower() == "true":
            return True
        if val_str.lower() == "false":
            return False
        if val_str.lower() in ("none", "null", "nan"):
            return None
        return val_str

    def _parse_values(self, values_str: str) -> list:
        """Parse a tuple/list of values from string like ('A', 'B', 'C')."""
        values_str = values_str.strip().strip("()").strip("[]").strip("{}")
        parts = []
        for part in values_str.split(","):
            part = part.strip().strip("'").strip('"')
            if part:
                parts.append(self._parse_value(part))
        return parts
