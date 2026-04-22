"""
run_pipeline.py
---------------
Main script that runs the entire data pipeline for the SmartCompare price comparison system.
CSCE 5200 - Group 7

What this script does, in order:
  1. Reads GroceryDB_foods.csv and Item_List.csv and converts them to our standard schema
  2. Saves those adapted files to data/processed/
  3. Cleans product names and computes unit prices
  4. Saves the final combined.csv to data/processed/
  5. Prints a summary with a store breakdown, top categories, and cheapest items
  6. Runs a quick accuracy check against our ground truth file

To run from the project root:
    python run_pipeline.py
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore", category=FutureWarning)

# Make sure our src/ package is importable from the project root
sys.path.insert(0, str(Path(__file__).parent))
from src.data_adapter    import build_adapted_datasets
from src.catalog_enrichment import enrich_catalog_metadata
from src.price_normalizer import (
    clean_product_names,
    apply_unit_prices,
    merge_store_datasets,
)

# Directory paths used throughout the pipeline
ROOT         = Path(__file__).parent
RAW_DIR      = ROOT / "data" / "raw"
PROCESSED    = ROOT / "data" / "processed"
EVAL_DIR     = ROOT / "evaluation"

GROCERYDB    = RAW_DIR / "GroceryDB_foods.csv"
ITEM_LIST    = RAW_DIR / "Item_List.csv"
SAMPLE_CSV   = RAW_DIR / "sample_grocery.csv"
GROUND_TRUTH = EVAL_DIR / "ground_truth.csv"

PROCESSED.mkdir(parents=True, exist_ok=True)

# Set this to a smaller number (e.g. 5000) if you want a quick test run
# without waiting for the full GroceryDB to process.
MAX_GROCERYDB_ROWS = None


# ── Console formatting helpers ────────────────────────────────────────────────

def _divider(char: str = "=", width: int = 68) -> None:
    print(char * width)


def _hdr(title: str) -> None:
    _divider()
    print(f"  {title}")
    _divider()


def _print_df_stats(df: pd.DataFrame, label: str) -> None:
    print(f"\n  {label}")
    print(f"    Rows            : {len(df):>8,}")
    print(f"    Stores          : {sorted(df['store'].unique())}")
    print(f"    Categories      : {df['category'].nunique()} unique")
    n_nan = df["unit_price"].isna().sum() if "unit_price" in df.columns else "N/A"
    print(f"    NaN unit_price  : {n_nan}")


# ── Step 1: Load and adapt the raw source files ───────────────────────────────

def step_adapt() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    _hdr("STEP 1/4 -- Adapting raw datasets to standard schema")

    # GroceryDB (main source — Walmart, Target, Whole Foods)
    if GROCERYDB.exists():
        print(f"\n  [GroceryDB]  {GROCERYDB.name}  ({GROCERYDB.stat().st_size/1e6:.1f} MB)")
        gdb_df, itl_df = build_adapted_datasets(
            str(GROCERYDB),
            str(ITEM_LIST) if ITEM_LIST.exists() else None,
            max_grocerydb_rows=MAX_GROCERYDB_ROWS,
        )
        gdb_df.to_csv(PROCESSED / "grocerydb_adapted.csv", index=False)
        print(f"  [OK] GroceryDB adapted: {len(gdb_df):,} rows")
        print(f"       Stores found     : {sorted(gdb_df['store'].unique())}")
    else:
        print("  [WARN] GroceryDB_foods.csv not found — skipping.")
        gdb_df = pd.DataFrame()
        itl_df = pd.DataFrame()

    # Item_List (category/product dimension data, no prices)
    if ITEM_LIST.exists() and not itl_df.empty:
        itl_df.to_csv(PROCESSED / "item_list_adapted.csv", index=False)
        print(f"\n  [Item_List]  {ITEM_LIST.name}")
        print(f"  [OK] Item_List adapted: {len(itl_df):,} rows (no prices — dimension data only)")

    # Sample CSV is always included if present
    sample_df = pd.DataFrame()
    if SAMPLE_CSV.exists():
        sample_df = pd.read_csv(SAMPLE_CSV)
        print(f"\n  [Sample]     {SAMPLE_CSV.name}  ({len(sample_df)} rows)")

    return gdb_df, itl_df, sample_df


# ── Step 2: Merge all source data into one DataFrame ─────────────────────────

def step_merge(gdb_df, sample_df) -> pd.DataFrame:
    _hdr("STEP 2/4 -- Merging datasets")

    frames = []
    if not gdb_df.empty:
        gdb_df["source_file"] = "GroceryDB_foods.csv"
        frames.append(gdb_df)
    if not sample_df.empty:
        sample_df["source_file"] = "sample_grocery.csv"
        frames.append(sample_df)

    if not frames:
        print("  [ERROR] No data to merge — nothing was loaded in Step 1.")
        sys.exit(1)

    merged = pd.concat(frames, ignore_index=True)
    print(f"  [OK] Merged {len(frames)} source file(s) → {len(merged):,} total rows")
    return merged


# ── Step 3: Clean product names and compute unit prices ───────────────────────

def step_preprocess(df: pd.DataFrame) -> pd.DataFrame:
    _hdr("STEP 3/4 -- Preprocessing (clean names + unit prices)")

    print("  Cleaning product names ...")
    df = clean_product_names(df)

    print("  Computing unit prices ...")
    df = apply_unit_prices(df)

    n_ok  = df["unit_price"].notna().sum()
    n_nan = df["unit_price"].isna().sum()
    pct   = 100 * n_ok / max(len(df), 1)
    print(f"  [OK] Unit price computed for {n_ok:,} rows ({pct:.1f}%)")
    print(f"       Rows where unit price could not be computed: {n_nan:,}")
    return df


# ── Step 4: Save combined.csv and print the summary report ───────────────────

def step_save_and_report(df: pd.DataFrame) -> None:
    _hdr("STEP 4/4 -- Saving and Summary Report")

    out_path = PROCESSED / "combined.csv"
    df = enrich_catalog_metadata(df)
    df.to_csv(out_path, index=False)
    print(f"  [OK] Combined CSV saved → {out_path}")
    print(f"       File size          : {out_path.stat().st_size / 1e6:.2f} MB")

    # Per-store breakdown
    print("\n  Store Breakdown:")
    store_stats = (
        df[df["unit_price"].notna()]
        .groupby("store")
        .agg(
            products   =("product_name", "count"),
            avg_price  =("price",      "mean"),
            avg_unit_p =("unit_price", "mean"),
            categories =("category",  "nunique"),
        )
        .sort_values("products", ascending=False)
    )
    print(store_stats.to_string())

    # Top categories by product count
    print("\n  Top 10 Categories by Product Count:")
    cat_counts = df["category"].value_counts().head(10)
    for cat, cnt in cat_counts.items():
        print(f"    {cat:<25}  {cnt:>6,}")

    # Cheapest items by unit price
    print("\n  Cheapest by Unit Price (top 10 products):")
    valid = df[df["unit_price"].notna()].copy()
    if not valid.empty:
        cheapest = (
            valid.sort_values("unit_price")
            .drop_duplicates(subset=["product_name", "store"])
            [["product_name", "store", "price", "unit_price", "canonical_unit"]]
            .head(10)
        )
        print(cheapest.to_string(index=False))


# ── Evaluation: compare our cheapest-store picks to ground truth ──────────────

def step_evaluate(df: pd.DataFrame) -> None:
    _hdr("EVALUATION -- Ground Truth Comparison")

    if not GROUND_TRUTH.exists():
        print("  [SKIP] evaluation/ground_truth.csv not found — skipping accuracy check.")
        return

    gt = pd.read_csv(GROUND_TRUTH)
    valid = df[df["unit_price"].notna()].copy()
    valid["product_name_clean"] = valid["product_name"].str.lower().str.strip()

    hits = 0
    for _, row in gt.iterrows():
        query          = str(row["product_name"]).lower().strip()
        expected_store = str(row["expected_cheapest_store"]).strip()

        matches = valid[valid["product_name_clean"].str.contains(query, na=False)]
        if matches.empty:
            print(f"  [MISS]  '{query}' — no matching products found in processed data")
            continue

        cheapest_row = matches.loc[matches["unit_price"].idxmin()]
        actual_store = cheapest_row["store"]
        symbol = "[OK] " if actual_store == expected_store else "[DIFF]"
        if actual_store == expected_store:
            hits += 1
        print(
            f"  {symbol} '{query}' | "
            f"Expected: {expected_store:10s} | "
            f"Got: {actual_store:10s} | "
            f"unit_price: {cheapest_row['unit_price']:.6f} /{cheapest_row['canonical_unit']}"
        )

    total    = len(gt)
    accuracy = hits / total if total else 0
    print(f"\n  Accuracy: {hits}/{total} ({accuracy:.0%})")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    start = time.time()

    print()
    _divider("=")
    print("  IR & NLP-Based Price Formation System")
    print("  CSCE 5200 -- Group 7  |  Full Pipeline Runner")
    _divider("=")
    print()

    gdb_df, itl_df, sample_df = step_adapt()
    merged    = step_merge(gdb_df, sample_df)
    processed = step_preprocess(merged)
    step_save_and_report(processed)
    step_evaluate(processed)

    elapsed = time.time() - start
    _divider()
    print(f"  Pipeline complete in {elapsed:.1f}s")
    _divider()


if __name__ == "__main__":
    main()
