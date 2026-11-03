"""Restore the generated CSV omitted from GitHub using the included Parquet."""
from pathlib import Path
import pandas as pd
root = Path(__file__).resolve().parents[1]
target = root / "data/exports/hourly.csv"
if not target.exists():
    pd.read_parquet(target.with_suffix(".parquet")).to_csv(target, index=False)
    print("Restored data/exports/hourly.csv")
else:
    print("data/exports/hourly.csv already exists")
