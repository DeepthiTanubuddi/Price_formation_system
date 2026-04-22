"""
price_normalizer.py
-------------------
Handles data cleaning and unit price normalization for our grocery dataset.
CSCE 5200 - Group 7

The main job here is to take raw product data from multiple stores and get
everything into a consistent format — especially unit prices — so we can
meaningfully compare "cheapest milk" across Walmart, Target, etc.

Unit conversions follow NIST SP 811 / FDA label standards:
  https://www.nist.gov/pml/special-publication-811

We deliberately keep this module light on dependencies (just pandas + regex)
so it's easy to test each function in isolation.

References:
  [1] NIST SP 811 – Guide for the Use of the International System of Units
  [2] GroceryDB dataset paper: https://www.nature.com/articles/s41538-022-00164-0
"""

from __future__ import annotations

import logging
import re
import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.catalog_enrichment import enrich_catalog_metadata

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)

# Every store CSV must have at least these six columns.
REQUIRED_COLUMNS: list[str] = [
    "product_name",
    "store",
    "price",
    "quantity",
    "unit",
    "category",
]

# Unit conversion tables.
# Source: NIST SP 811 (1 oz = 28.3495 g, 1 lb = 453.592 g, etc.)

_WEIGHT_CONVERSIONS: dict[str, tuple[float, str]] = {
    "oz":  (28.3495, "g"),
    "lb":  (453.592, "g"),
    "kg":  (1000.0,  "g"),
    "g":   (1.0,     "g"),  # already in grams — no conversion needed
}

_VOLUME_CONVERSIONS: dict[str, tuple[float, str]] = {
    "fl_oz": (29.5735,  "ml"),
    "floz":  (29.5735,  "ml"),  # both spellings appear in real data
    "l":     (1000.0,   "ml"),
    "L":     (1000.0,   "ml"),
    "pt":    (473.176,  "ml"),
    "qt":    (946.353,  "ml"),
    "gal":   (3785.41,  "ml"),
    "ml":    (1.0,      "ml"),  # already in ml — no conversion needed
}

# Units we pass through as-is without converting to grams or ml.
_PASSTHROUGH_UNITS: frozenset[str] = frozenset(
    {"pack", "unit", "count", "each", "ct"}
)

_DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "combined.csv"


def load_store_data(filepath: str) -> pd.DataFrame:
    """Load and validate a single store's CSV file.

    Parameters
    ----------
    filepath : str
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        DataFrame with at least the six required columns.

    Raises
    ------
    ValueError
        If required columns are missing.
    FileNotFoundError
        If the file doesn't exist (raised by pandas).

    Notes
    -----
    We load everything as strings first, then coerce numeric columns.
    This avoids pandas guessing wrong types on messy data.
    Individual bad rows are handled later by apply_unit_prices rather
    than being dropped here.
    """
    logger.info("Loading store data from: %s", filepath)
    df: pd.DataFrame = pd.read_csv(filepath, dtype=str)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"CSV '{filepath}' is missing required column(s): {missing}. "
            f"Expected columns: {REQUIRED_COLUMNS}"
        )

    df["price"]    = pd.to_numeric(df["price"],    errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    # Strip leading/trailing whitespace from all text columns.
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].str.strip()

    logger.info("Loaded %d rows from '%s'.", len(df), filepath)
    return df


def normalize_unit(quantity: float, unit: str) -> tuple[float, str]:
    """Convert a raw quantity/unit pair to a canonical measurement.

    Weight units are converted to grams; volume units are converted to ml.
    Discrete units (pack, count, etc.) are passed through unchanged.

    Parameters
    ----------
    quantity : float
        The raw numeric quantity.
    unit : str
        The unit string (e.g. "oz", "lb", "fl_oz").

    Returns
    -------
    tuple[float, str]
        (normalized_quantity, canonical_unit)

    Examples
    --------
    >>> normalize_unit(16, "oz")
    (453.592, 'g')
    >>> normalize_unit(1, "lb")
    (453.592, 'g')
    >>> normalize_unit(64, "fl_oz")
    (1892.706, 'ml')
    >>> normalize_unit(6, "pack")
    (6.0, 'pack')
    """
    unit_clean = unit.strip().lower() if isinstance(unit, str) else ""

    if unit_clean in _WEIGHT_CONVERSIONS:
        multiplier, canonical = _WEIGHT_CONVERSIONS[unit_clean]
        return (quantity * multiplier, canonical)

    if unit_clean in _VOLUME_CONVERSIONS:
        multiplier, canonical = _VOLUME_CONVERSIONS[unit_clean]
        return (quantity * multiplier, canonical)

    # Try the original capitalization too (handles "L" vs "l").
    if unit in _VOLUME_CONVERSIONS:
        multiplier, canonical = _VOLUME_CONVERSIONS[unit]
        return (quantity * multiplier, canonical)

    if unit_clean in _PASSTHROUGH_UNITS:
        return (float(quantity), unit_clean)

    logger.warning(
        "Unknown unit '%s' encountered — returning original values. "
        "Consider adding it to the conversion table.",
        unit,
    )
    return (float(quantity), unit)


def compute_unit_price(price: float, quantity: float, unit: str) -> float:
    """Compute the unit price (price per canonical unit).

    Formula:  unit_price = price / normalized_quantity

    Parameters
    ----------
    price : float
        Total package price in USD.
    quantity : float
        Raw package quantity before normalization.
    unit : str
        Unit of the raw quantity.

    Returns
    -------
    float
        Price per canonical unit ($/g, $/ml, $/pack, etc.)

    Raises
    ------
    ValueError
        If quantity <= 0.

    Examples
    --------
    >>> compute_unit_price(3.49, 16, "oz")   # $3.49 for 16 oz → $/g
    0.007694...
    """
    if quantity <= 0:
        raise ValueError(
            f"quantity must be > 0, got {quantity!r}. "
            "Cannot compute a unit price for a non-positive quantity."
        )

    normalized_qty, _ = normalize_unit(quantity, unit)

    if normalized_qty == 0.0:
        raise ValueError(
            f"Normalized quantity is 0 for quantity={quantity}, unit={unit!r}."
        )

    return price / normalized_qty


def apply_unit_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Add unit_price, normalized_qty, and canonical_unit columns to a DataFrame.

    Processes every row individually. Errors on individual rows are caught
    and logged so one bad row doesn't stop the rest from being processed.

    Parameters
    ----------
    df : pd.DataFrame
        Must have price, quantity, and unit columns.

    Returns
    -------
    pd.DataFrame
        Input DataFrame with three new columns. Returns a copy — does not
        modify the original.

    Notes
    -----
    Rows where unit_price ends up as NaN are worth investigating after the run.
    """
    df = df.copy()

    unit_prices:      list[float] = []
    normalized_qtys:  list[float] = []
    canonical_units:  list[str]   = []

    for idx, row in df.iterrows():
        try:
            price    = float(row["price"])
            quantity = float(row["quantity"])
            unit     = str(row["unit"])

            unit_price           = compute_unit_price(price, quantity, unit)
            norm_qty, can_unit   = normalize_unit(quantity, unit)

            unit_prices.append(unit_price)
            normalized_qtys.append(norm_qty)
            canonical_units.append(can_unit)

        except Exception as exc:
            logger.warning(
                "Row %s: could not compute unit price — %s. Setting unit_price to NaN.",
                idx,
                exc,
            )
            unit_prices.append(float("nan"))
            normalized_qtys.append(float("nan"))
            canonical_units.append("")

    df["unit_price"]     = unit_prices
    df["normalized_qty"] = normalized_qtys
    df["canonical_unit"] = canonical_units

    n_ok  = sum(not math.isnan(up) for up in unit_prices)
    n_bad = len(unit_prices) - n_ok
    logger.info(
        "apply_unit_prices finished: %d rows computed successfully, %d rows set to NaN.",
        n_ok,
        n_bad,
    )
    return df


def merge_store_datasets(filepaths: list[str]) -> pd.DataFrame:
    """Load and combine multiple per-store CSVs into one DataFrame.

    Adds a source_file column to each frame before combining, so we
    can still trace where each row came from after the merge.

    Parameters
    ----------
    filepaths : list[str]
        Paths to the raw per-store CSV files. At least one is required.

    Returns
    -------
    pd.DataFrame
        Combined DataFrame with a reset integer index.

    Raises
    ------
    ValueError
        If filepaths is empty.
    """
    if not filepaths:
        raise ValueError("filepaths must contain at least one path.")

    frames: list[pd.DataFrame] = []
    for fp in filepaths:
        logger.info("Loading file for merge: %s", fp)
        frame = load_store_data(fp)
        frame["source_file"] = Path(fp).name  # keep the filename short in the output CSV
        frames.append(frame)

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        "merge_store_datasets: merged %d file(s) → %d total rows.",
        len(filepaths),
        len(combined),
    )
    return combined


def clean_product_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the product_name column for downstream search and comparison.

    Steps applied:
    1. Lowercase everything for consistent token matching.
    2. Strip special characters (keep letters, digits, spaces, and hyphens).
       Hyphens are kept because compound names like "whole-grain" are common.
    3. Strip leading/trailing whitespace.
    4. Collapse multiple spaces into one.

    Parameters
    ----------
    df : pd.DataFrame
        Must have a product_name column.

    Returns
    -------
    pd.DataFrame
        Copy with cleaned product_name. The original DataFrame is not modified.

    Examples
    --------
    >>> row = {"product_name": "  Whole  Milk!! (1 Gallon)  "}
    >>> clean_product_names(pd.DataFrame([row]))["product_name"].iloc[0]
    'whole milk 1 gallon'
    """
    df = df.copy()

    df["product_name"] = df["product_name"].str.lower()
    df["product_name"] = df["product_name"].str.replace(
        r"[^a-z0-9 \-]", "", regex=True
    )
    df["product_name"] = df["product_name"].str.strip()
    df["product_name"] = df["product_name"].str.replace(r"\s{2,}", " ", regex=True)

    logger.info("clean_product_names: cleaned product_name column (%d rows).", len(df))
    return df


def build_pipeline(
    filepaths: list[str],
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    """Run the full preprocessing pipeline: load → clean → unit prices → save.

    Steps
    -----
    1. merge_store_datasets — load and concatenate per-store CSVs
    2. clean_product_names  — normalize product name strings
    3. apply_unit_prices    — compute normalized unit prices
    4. Save to data/processed/combined.csv

    Parameters
    ----------
    filepaths : list[str]
        Paths to the raw per-store CSV files.
    output_path : str, optional
        Custom output path. Defaults to data/processed/combined.csv.

    Returns
    -------
    pd.DataFrame
        Fully preprocessed DataFrame ready for search and analysis.
    """
    print("=" * 60)
    print("  Price Formation System – Preprocessing Pipeline")
    print("  CSCE 5200 – Group 7")
    print("=" * 60)

    print(f"\n[1/3] Loading and merging {len(filepaths)} store dataset(s)…")
    df = merge_store_datasets(filepaths)
    print(f"      [OK] {len(df)} total rows loaded.")

    print("\n[2/3] Cleaning product names…")
    df = clean_product_names(df)
    print("      [OK] Product names cleaned.")

    print("\n[3/3] Computing normalized unit prices…")
    df = apply_unit_prices(df)
    n_nan = df["unit_price"].isna().sum()
    print(f"      [OK] Unit prices computed. "
          f"({n_nan} row(s) with NaN — check logs for details.)")

    save_path = Path(output_path) if output_path else _DEFAULT_OUTPUT_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    df = enrich_catalog_metadata(df)
    df.to_csv(save_path, index=False)
    print(f"[DONE] Pipeline complete! Combined CSV saved to:\n  {save_path.resolve()}")
    print("=" * 60)

    return df


# Run a quick self-test if you execute this file directly.
if __name__ == "__main__":
    import sys

    _sample = Path(__file__).parent.parent / "data" / "raw" / "sample_grocery.csv"

    if not _sample.exists():
        print(
            f"Sample data not found at {_sample}. "
            "Please make sure data/raw/sample_grocery.csv exists.",
            file=sys.stderr
        )
        sys.exit(1)

    result_df = build_pipeline([str(_sample)])
    print("\nFirst 5 rows of the processed output:")
    print(result_df[["product_name", "store", "price", "unit_price", "canonical_unit"]].head())
