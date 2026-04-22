"""
inspect_csv.py
--------------
Prints the column names and a sample row from combined.csv for quick debugging.
CSCE 5200 - Group 7

Useful when you want to check the output schema without running the full verify.py.

Usage:
    python inspect_csv.py
"""

import pandas as pd

df = pd.read_csv('data/processed/combined.csv', nrows=5)
print("COLUMNS:", df.columns.tolist())
print()
print("SAMPLE ROW:")
for col in df.columns:
    print(f"  {col}: {df[col].iloc[0]}")
