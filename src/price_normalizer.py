"""
price_normalizer.py
===================
Data preprocessing module for the IR & NLP-Based Price Formation System.
CSCE 5200 – Group 7

This module implements the full data-cleaning and unit-normalisation pipeline
used to transform raw per-store grocery CSVs into a single, analysis-ready
DataFrame where every product carries a consistent unit-price expressed in a
canonical SI-adjacent unit (grams or millilitres for weight/volume items, or
the original discrete unit for packaged counts).

Design notes
------------
* Unit conversions follow NIST SP 811 / FDA label standards.
* Product-name cleaning uses a lightweight regex approach rather than a full
  NLP tokeniser so that the module has zero heavy dependencies beyond Pandas.
* The pipeline is designed so that each step can be unit-tested independently
  (pure functions with no global state).

References
----------
[1] NIST SP 811 – Guide for the Use of the International System of Units
    https://www.nist.gov/pml/special-publication-811
[2] GroceryDB: Informing Healthy Food Choices through an Empirical
    Examination of Grocery Store Food Items.
    https://www.nature.com/articles/s41538-022-00164-0
"""

from __future__ import annotations

import logging
import re
import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Columns that every store CSV **must** contain.
REQUIRED_COLUMNS: list[str] = [
    "product_name",
    "store",
    "price",
    "quantity",
    "unit",
    "category",
]

# ---------------------------------------------------------------------------
# Unit-conversion look-up tables
# Ref [1]: 1 oz_av = 28.3495 g; 1 lb = 453.592 g; 1 kg = 1000 g
#          1 fl oz = 29.5735 ml; 1 L = 1000 ml; 1 pt = 473.176 ml;
#          1 qt = 946.353 ml; 1 gal = 3785.41 ml
# ---------------------------------------------------------------------------

#: Weight units → (multiplier_to_grams, canonical_unit)
_WEIGHT_CONVERSIONS: dict[str, tuple[float, str]] = {
    "oz":  (28.3495, "g"),
    "lb":  (453.592, "g"),
    "kg":  (1000.0,  "g"),
    "g":   (1.0,     "g"),   # already canonical
}

#: Volume units → (multiplier_to_ml, canonical_unit)
_VOLUME_CONVERSIONS: dict[str, tuple[float, str]] = {
    "fl_oz": (29.5735,  "ml"),
    "floz":  (29.5735,  "ml"),  # alternative spelling tolerated
    "l":     (1000.0,   "ml"),
    "L":     (1000.0,   "ml"),
    "pt":    (473.176,  "ml"),
    "qt":    (946.353,  "ml"),
    "gal":   (3785.41,  "ml"),
    "ml":    (1.0,      "ml"),  # already canonical
}

#: Discrete / already-normalised units that are passed through unchanged.
_PASSTHROUGH_UNITS: frozenset[str] = frozenset(
    {"pack", "unit", "count", "each", "ct"}
)

# ---------------------------------------------------------------------------
# Default output path for the combined CSV
# ---------------------------------------------------------------------------
_DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "combined.csv"


# ===========================================================================
# 1. load_store_data
# ===========================================================================

def load_store_data(filepath: str) -> pd.DataFrame:
    """Load and lightly validate a single store's raw CSV.

    Parameters
    ----------
    filepath : str
        Absolute or relative path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame with at least the six required columns.

    Raises
    ------
    ValueError
        If any of the required columns are absent from the file.
    FileNotFoundError
        Propagated from ``pd.read_csv`` if the path does not exist.

    Notes
    -----
    * Only string columns are stripped of surrounding whitespace; numeric
      columns are left for downstream type coercion.
    * No rows are dropped here – validation is kept deliberately permissive so
      that individual bad rows can be handled gracefully by ``apply_unit_prices``.
    """
    logger.info("Loading store data from: %s", filepath)
    df: pd.DataFrame = pd.read_csv(filepath, dtype=str)  # load all as str first

    # ---- column validation ------------------------------------------------
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"CSV '{filepath}' is missing required column(s): {missing}. "
            f"Expected columns: {REQUIRED_COLUMNS}"
        )

    # ---- coerce numeric columns -------------------------------------------
    df["price"]    = pd.to_numeric(df["price"],    errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    # ---- strip whitespace from all string (object) columns ----------------
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].str.strip()

    logger.info("Loaded %d rows from '%s'.", len(df), filepath)
    return df


# ===========================================================================
# 2. normalize_unit
# ===========================================================================

def normalize_unit(quantity: float, unit: str) -> tuple[float, str]:
    """Convert a raw quantity/unit pair to a canonical measurement.

    Weight units are converted to **grams (g)**; volume units to
    **millilitres (ml)**; discrete units are passed through unchanged.

    Algorithm
    ---------
    1. Normalise the ``unit`` string (lower-case, strip).
    2. Look up weight conversions (Ref [1] NIST SP 811).
    3. Look up volume conversions.
    4. If the unit is a known pass-through (pack, count, …), return as-is.
    5. Otherwise log a warning and return the original values.

    Parameters
    ----------
    quantity : float
        The raw numeric quantity from the source data.
    unit : str
        The raw unit string (e.g. ``"oz"``, ``"lb"``, ``"fl_oz"``).

    Returns
    -------
    tuple[float, str]
        ``(normalized_quantity, canonical_unit)`` where ``canonical_unit``
        is one of ``"g"``, ``"ml"``, or the original discrete unit.

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

    # ---- weight -----------------------------------------------------------
    if unit_clean in _WEIGHT_CONVERSIONS:
        multiplier, canonical = _WEIGHT_CONVERSIONS[unit_clean]
        return (quantity * multiplier, canonical)

    # ---- volume -----------------------------------------------------------
    if unit_clean in _VOLUME_CONVERSIONS:
        multiplier, canonical = _VOLUME_CONVERSIONS[unit_clean]
        return (quantity * multiplier, canonical)

    # ---- also try the original capitalisation for L / fl_oz ---------------
    if unit in _VOLUME_CONVERSIONS:
        multiplier, canonical = _VOLUME_CONVERSIONS[unit]
        return (quantity * multiplier, canonical)

    # ---- discrete / pass-through ------------------------------------------
    if unit_clean in _PASSTHROUGH_UNITS:
        return (float(quantity), unit_clean)

    # ---- unknown unit – warn and pass through unchanged -------------------
    logger.warning(
        "Unknown unit '%s' encountered – returning original values. "
        "Consider adding it to the conversion table.",
        unit,
    )
    return (float(quantity), unit)


# ===========================================================================
# 3. compute_unit_price
# ===========================================================================

def compute_unit_price(price: float, quantity: float, unit: str) -> float:
    """Compute the normalised unit price (price per canonical unit).

    The function calls :func:`normalize_unit` internally so that the
    denominator is always in a consistent SI-adjacent unit.

    Formula::

        unit_price = price / normalized_quantity

    Parameters
    ----------
    price : float
        Total package price in USD.
    quantity : float
        Raw package quantity (before unit normalisation).
    unit : str
        Unit of the raw quantity (e.g. ``"oz"``, ``"ml"``, ``"lb"``).

    Returns
    -------
    float
        Price per canonical unit (e.g. $/g, $/ml, $/pack).

    Raises
    ------
    ValueError
        If ``quantity`` is ≤ 0 (prevents division by zero and catches bad data).

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

    # Guard against a zero result after conversion (should not normally occur
    # given valid conversions, but be defensive).
    if normalized_qty == 0.0:
        raise ValueError(
            f"Normalized quantity is 0 for quantity={quantity}, unit={unit!r}."
        )

    return price / normalized_qty


# ===========================================================================
# 4. apply_unit_prices
# ===========================================================================

def apply_unit_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Add unit-price columns to a DataFrame, handling per-row errors.

    Applies :func:`compute_unit_price` row-wise and attaches three new
    columns:

    * ``unit_price``      – price per canonical unit (NaN on error)
    * ``normalized_qty``  – quantity after unit conversion
    * ``canonical_unit``  – the post-conversion unit string

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``price``, ``quantity``, and ``unit`` columns.

    Returns
    -------
    pd.DataFrame
        Input DataFrame with three additional columns appended in-place.
        The original DataFrame is **not** mutated; a copy is returned.

    Notes
    -----
    * Per-row exceptions are caught and logged so that a single bad row does
      not abort the entire pipeline.
    * Rows where ``unit_price`` is NaN should be investigated post-run.
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

            # compute_unit_price raises ValueError for quantity <= 0
            unit_price = compute_unit_price(price, quantity, unit)
            norm_qty, can_unit = normalize_unit(quantity, unit)

            unit_prices.append(unit_price)
            normalized_qtys.append(norm_qty)
            canonical_units.append(can_unit)

        except Exception as exc:
            logger.warning(
                "Row %s: could not compute unit price – %s. Setting unit_price=NaN.",
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
        "apply_unit_prices: %d rows OK, %d rows with NaN unit_price.",
        n_ok,
        n_bad,
    )
    return df


# ===========================================================================
# 5. merge_store_datasets
# ===========================================================================

def merge_store_datasets(filepaths: list[str]) -> pd.DataFrame:
    """Load and merge multiple per-store CSVs into one DataFrame.

    Each file is loaded via :func:`load_store_data`.  A ``source_file``
    column is added to every frame before concatenation so that the origin
    of each row remains traceable after merging.

    Parameters
    ----------
    filepaths : list[str]
        Paths to the raw per-store CSV files.  At least one path must be
        provided.

    Returns
    -------
    pd.DataFrame
        Combined DataFrame with a reset integer index (0, 1, 2, …).

    Raises
    ------
    ValueError
        If ``filepaths`` is empty.

    Notes
    -----
    * ``pd.concat`` is used with ``ignore_index=True`` (equivalent to
      resetting the index), matching the behaviour documented in the pandas
      user guide on combining DataFrames.
    """
    if not filepaths:
        raise ValueError("filepaths must contain at least one path.")

    frames: list[pd.DataFrame] = []
    for fp in filepaths:
        logger.info("Merging file: %s", fp)
        frame = load_store_data(fp)
        # Track provenance – basename keeps paths short in the output CSV.
        frame["source_file"] = Path(fp).name
        frames.append(frame)

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        "merge_store_datasets: merged %d files → %d total rows.",
        len(filepaths),
        len(combined),
    )
    return combined


# ===========================================================================
# 6. clean_product_names
# ===========================================================================

def clean_product_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise the ``product_name`` column for downstream IR and NLP tasks.

    Transformations applied (in order):

    1. **Lowercase** – uniform casing for token matching.
    2. **Remove special characters** – keep only alphanumerics, spaces, and
       hyphens (hyphens preserved because they appear in compound names such
       as "whole-grain" or "low-fat").
    3. **Strip** leading/trailing whitespace.
    4. **Collapse** multiple consecutive spaces to a single space.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a ``product_name`` column.

    Returns
    -------
    pd.DataFrame
        DataFrame with cleaned ``product_name`` values.  Other columns are
        unchanged.  The input is not mutated.

    Examples
    --------
    >>> row = {"product_name": "  Whole  Milk!! (1 Gallon)  "}
    >>> clean_product_names(pd.DataFrame([row]))["product_name"].iloc[0]
    'whole milk 1 gallon'
    """
    df = df.copy()

    # step 1: lowercase
    df["product_name"] = df["product_name"].str.lower()

    # step 2: remove everything except alphanumeric, space, hyphen
    # Regex character class: [^a-z0-9 \-] matches disallowed chars and removes them
    df["product_name"] = df["product_name"].str.replace(
        r"[^a-z0-9 \-]", "", regex=True
    )

    # step 3: strip leading/trailing whitespace
    df["product_name"] = df["product_name"].str.strip()

    # step 4: collapse multiple spaces (produced by step 2 removing punctuation)
    df["product_name"] = df["product_name"].str.replace(r"\s{2,}", " ", regex=True)

    logger.info("clean_product_names: product_name column cleaned (%d rows).", len(df))
    return df


# ===========================================================================
# 7. build_pipeline
# ===========================================================================

def build_pipeline(
    filepaths: list[str],
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    """Orchestrate the full preprocessing pipeline.

    Steps
    -----
    1. :func:`merge_store_datasets` – load & concatenate per-store CSVs.
    2. :func:`clean_product_names`  – normalise product name strings.
    3. :func:`apply_unit_prices`    – compute normalised unit prices.
    4. Save result to ``data/processed/combined.csv``.

    Parameters
    ----------
    filepaths : list[str]
        Paths to the raw per-store CSV files.
    output_path : str, optional
        Custom output path for the combined CSV.  Defaults to
        ``<project_root>/data/processed/combined.csv``.

    Returns
    -------
    pd.DataFrame
        Fully preprocessed DataFrame ready for the IR and NLP modules.

    Notes
    -----
    * Progress messages are printed to stdout (not just the log) so that
      interactive notebook / script use gives clear feedback.
    * The output directory is created if it does not already exist.
    """
    print("=" * 60)
    print("  Price Formation System – Preprocessing Pipeline")
    print("  CSCE 5200 – Group 7")
    print("=" * 60)

    # ── Step 1: Load & merge ────────────────────────────────────────────────
    print(f"\n[1/3] Loading and merging {len(filepaths)} store dataset(s)…")
    df = merge_store_datasets(filepaths)
    print(f"      [OK] {len(df)} total rows loaded.")

    # ── Step 2: Clean product names ─────────────────────────────────────────
    print("\n[2/3] Cleaning product names…")
    df = clean_product_names(df)
    print("      [OK] Product names normalised.")

    # ── Step 3: Compute unit prices ─────────────────────────────────────────
    print("\n[3/3] Computing normalised unit prices…")
    df = apply_unit_prices(df)
    n_nan = df["unit_price"].isna().sum()
    print(f"      [OK] unit_price computed. "
          f"({n_nan} row(s) with NaN - check logs for details.)")

    # ── Step 4: Persist combined CSV ─────────────────────────────────────────
    save_path = Path(output_path) if output_path else _DEFAULT_OUTPUT_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(save_path, index=False)
    print(f"[DONE] Pipeline complete! Combined CSV saved to:\n  {save_path.resolve()}")
    print("=" * 60)

    return df


# ===========================================================================
# Quick self-test (run this file directly: python price_normalizer.py)
# ===========================================================================

if __name__ == "__main__":
    import sys

    # Resolve the sample data path relative to this script
    _sample = Path(__file__).parent.parent / "data" / "raw" / "sample_grocery.csv"

    if not _sample.exists():
        print(f"Sample data not found at {_sample}. "
              "Please ensure data/raw/sample_grocery.csv exists.", file=sys.stderr)
        sys.exit(1)

    result_df = build_pipeline([str(_sample)])
    print("\nFirst 5 rows of processed output:")
    print(result_df[["product_name", "store", "price", "unit_price", "canonical_unit"]].head())
