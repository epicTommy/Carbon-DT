"""CSV loading placeholders for the MVP."""

from pathlib import Path

import pandas as pd


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load a CSV file without applying business-specific validation yet."""
    return pd.read_csv(path)
