"""
verify.py
---------
Quick dataset health-check script for the SmartCompare pipeline.
CSCE 5200 - Group 7

Run this from the project root after the pipeline has produced combined.csv
to get a fast summary of row counts, stores, categories, and unit prices.

Usage:
    python verify.py
"""

import pandas as pd

df = pd.read_csv("data/processed/combined.csv")
print("=== PROCESSED DATASET SUMMARY ===")
print(f"Total rows      : {len(df):,}")
print(f"Columns         : {list(df.columns)}")
print(f"Stores          : {sorted(df['store'].unique())}")
print(f"Categories      : {df['category'].nunique()} unique")
print(f"NaN unit_price  : {df['unit_price'].isna().sum()}")
print()
print("=== STORE COMPARISON (avg unit price $/g) ===")
s = df[df["unit_price"].notna()].groupby("store")["unit_price"].agg(["mean", "min", "count"])
s.columns = ["avg_$/g", "min_$/g", "products"]
print(s.to_string())
print()
print("=== SAMPLE ROWS ===")
print(df[["product_name", "store", "price", "unit_price", "canonical_unit", "category"]].head(8).to_string(index=False))
