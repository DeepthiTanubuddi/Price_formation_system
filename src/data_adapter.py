"""
data_adapter.py
===============
Adapts the two real-world datasets (GroceryDB_foods.csv and Item_List.csv)
into the standard price_formation_system schema before pipeline processing.

CSCE 5200 – Group 7

Source schemas
--------------
GroceryDB_foods.csv columns (relevant):
    name, store, price, package_weight (grams), harmonized single category
    IDs prefixed: tg_ = Target, wf_ = WholeFoods, wm_ = Walmart

Item_List.csv columns (wide format, one row per product):
    Category,
    Aldi-Item, Aldi-Link, Aldi-Multiplier,
    Kroger-Item, Kroger-Link, Kroger-Multiplier,
    Walmart-Item, Walmart-Link, Walmart-Multiplier,
    Ruler-Item, Ruler-Link, Ruler-Multiplier
    (no price – used for category/product name enrichment only)

Target output schema:
    product_name (str), store (str), price (float),
    quantity (float), unit (str), category (str)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Store-prefix → canonical store name map (from GroceryDB original_ID)
# ---------------------------------------------------------------------------
_ID_PREFIX_STORE: dict[str, str] = {
    "tg_": "Target",
    "wf_": "WholeFoods",
    "wm_": "Walmart",
}

# ---------------------------------------------------------------------------
# GroceryDB category → our simplified category map
# ---------------------------------------------------------------------------
_CATEGORY_MAP: dict[str, str] = {
    "baby-food":       "baby-food",
    "baking":          "baking",
    "beverages":       "beverages",
    "bread":           "bread",
    "breakfast":       "breakfast",
    "candy":           "snacks",
    "canned-goods":    "pantry",
    "cereal":          "breakfast",
    "chips-pretzels":  "snacks",
    "coffee":          "beverages",
    "condiments":      "condiments",
    "cookies-sweets":  "snacks",
    "dairy":           "dairy",
    "deli":            "deli",
    "eggs":            "eggs",
    "fish":            "seafood",
    "frozen":          "frozen",
    "fruit":           "produce",
    "grains-pasta":    "grains",
    "ice-cream":       "frozen",
    "juice":           "beverages",
    "medicine":        "health",
    "meat":            "meat",
    "nuts":            "snacks",
    "oils-vinegars":   "pantry",
    "poultry":         "meat",
    "prepared":        "prepared",
    "produce":         "produce",
    "seafood":         "seafood",
    "snacks":          "snacks",
    "soup":            "pantry",
    "spices":          "pantry",
    "tea-coffee":      "beverages",
    "vegetables":      "produce",
    "water":           "beverages",
    "yogurt":          "dairy",
}

# ---------------------------------------------------------------------------
# Liquid category / keyword detection
# GroceryDB stores ALL package quantities in grams (even for liquids).
# For liquids, 1 fl oz ≈ 29.57 ml was used, so the "gram" value is actually
# the weight equivalent. We treat liquid quantities as ml (density ≈ 1 g/mL
# for water-based products — close enough for price comparison).
# ---------------------------------------------------------------------------

# Categories that are always liquid (use ml)
_LIQUID_CATEGORIES: frozenset[str] = frozenset({
    "beverages", "drink-juice", "drink-juice-wf", "drink-water-wf",
    "drink-soft-energy-mixes", "drink-coffee", "drink-tea",
    "drink-shakes-other", "milk-milk-substitute", "dairy-yogurt-drink",
})

# Name substrings that indicate liquid regardless of category
_LIQUID_NAME_KEYWORDS: tuple[str, ...] = (
    " milk ", " milk,", " milk-", "whole milk", "skim milk", "2% milk",
    "1% milk", "fat free milk", "almond milk", "oat milk", "soy milk",
    "coconut milk", "lactaid", "kefir",
    "juice", " water ", " water,", "sparkling water", "club soda",
    "lemonade", "kombucha", "gatorade", "powerade",
    "vinegar", "olive oil", "vegetable oil", "canola oil", "coconut oil",
    "cooking oil", "soy sauce", "hot sauce", "worcestershire",
    "coffee creamer", "liquid creamer",
    "fl oz", "fluid ounce", "gallon", "half gal", "half-gal",
    "32 oz liquid", "16 oz liquid",
    "soup", "broth", "stock", "beef broth", "chicken broth",
    "mouthwash", "hand soap", "dish soap", "laundry detergent",
)

# Categories that are ALWAYS solid (force g even if name has ambiguous keywords)
_SOLID_CATEGORIES: frozenset[str] = frozenset({
    "baking", "bread", "breakfast", "snacks-chips", "snacks-bars",
    "snacks-mixes-crackers", "snacks-nuts-seeds", "snacks-popcorn",
    "cookies-biscuit", "pastry-chocolate-candy", "cakes", "muffins-bagels",
    "pasta-noodles", "rice-grains-packaged", "rice-grains-wf",
    "spices-seasoning", "cheese", "eggs-wf", "eggs", "meat-packaged",
    "meat-poultry-wf", "seafood", "seafood-wf", "produce-packaged",
    "produce-beans-wf", "nuts-seeds-wf", "snacks-dips-salsa",
    "coffee-beans-wf",
})


def _is_liquid(category: str, product_name: str) -> bool:
    """Return True if the product is likely a liquid (should use ml not g)."""
    cat = (category or "").lower().strip()

    # Fast path: explicitly solid category
    if cat in _SOLID_CATEGORIES:
        return False

    # Fast path: explicitly liquid category
    if cat in _LIQUID_CATEGORIES:
        return True

    # Name-based heuristic (case-insensitive)
    name_lower = (" " + (product_name or "").lower() + " ")
    for kw in _LIQUID_NAME_KEYWORDS:
        if kw in name_lower:
            return True

    return False

# ---------------------------------------------------------------------------
# Helper: strip HTML entities from GroceryDB product names
# ---------------------------------------------------------------------------
_HTML_ENTITY_RE = re.compile(r"&#?\w+;")

def _clean_html_entities(text: str) -> str:
    """Replace common HTML entities with ASCII equivalents."""
    text = text.replace("&#39;", "'").replace("&#38;", "&").replace("&#8482;", "")
    text = text.replace("&#8211;", "-").replace("&#8212;", "-")
    return _HTML_ENTITY_RE.sub("", text).strip()


# ===========================================================================
# 1. Adapt GroceryDB_foods.csv
# ===========================================================================

def adapt_grocerydb(filepath: str, max_rows: int | None = None) -> pd.DataFrame:
    """Convert GroceryDB_foods.csv → standard schema.

    Strategy
    --------
    * ``package_weight`` is already in **grams** – use it as ``quantity`` with
      ``unit = "g"``.
    * Derive ``store`` from the ``original_ID`` prefix (tg_, wf_, wm_).
    * Filter out rows where ``price`` is missing (cannot compute unit price).
    * Limit to ``max_rows`` if provided (useful for faster testing).

    Parameters
    ----------
    filepath : str
        Path to GroceryDB_foods.csv.
    max_rows : int, optional
        If set, only the first ``max_rows`` valid rows are returned.

    Returns
    -------
    pd.DataFrame
        Standard-schema DataFrame.
    """
    logger.info("Adapting GroceryDB from: %s", filepath)
    raw = pd.read_csv(filepath, dtype=str, low_memory=False)

    # Rename to working names
    raw = raw.rename(columns={
        "name":                       "product_name",
        "harmonized single category": "category",
        "package_weight":             "quantity",
    })

    # Derive store from original_ID prefix
    def _store_from_id(orig_id: str) -> str:
        if isinstance(orig_id, str):
            for prefix, store in _ID_PREFIX_STORE.items():
                if orig_id.startswith(prefix):
                    return store
        return "Unknown"

    raw["store"] = raw["original_ID"].apply(_store_from_id)

    # Keep only rows whose store is known
    raw = raw[raw["store"] != "Unknown"].copy()

    # Coerce numerics
    raw["price"]    = pd.to_numeric(raw["price"],    errors="coerce")
    raw["quantity"] = pd.to_numeric(raw["quantity"], errors="coerce")

    # Drop rows with no price or no weight (can't compute unit price)
    raw = raw.dropna(subset=["price", "quantity"])
    raw = raw[raw["price"] > 0]
    raw = raw[raw["quantity"] > 0]

    # Set unit: use ml for liquids, g for solids.
    # GroceryDB stores all weights as grams, but for liquids the value is
    # effectively the volume in ml (water density ≈ 1 g/mL).
    raw["unit"] = raw.apply(
        lambda row: "ml" if _is_liquid(
            str(row.get("category", "")),
            str(row.get("product_name", ""))
        ) else "g",
        axis=1,
    )

    # Map category
    raw["category"] = raw["category"].fillna("other").str.strip().str.lower()
    raw["category"] = raw["category"].map(_CATEGORY_MAP).fillna(raw["category"])

    # Clean HTML entities from product names
    raw["product_name"] = raw["product_name"].apply(
        lambda x: _clean_html_entities(str(x)) if isinstance(x, str) else x
    )

    # Select & standardise columns
    out = raw[["product_name", "store", "price", "quantity", "unit", "category"]].copy()
    out = out.reset_index(drop=True)

    if max_rows is not None:
        out = out.iloc[:max_rows]

    logger.info(
        "GroceryDB adapter: %d rows after filtering (%.1f%% of original).",
        len(out),
        100 * len(out) / max(len(raw), 1),
    )
    return out


# ===========================================================================
# 2. Adapt Item_List.csv
# ===========================================================================

def adapt_item_list(filepath: str) -> pd.DataFrame:
    """Convert wide-format Item_List.csv → standard schema.

    The Item_List has no price column; it is used only to enrich the
    product/category dimension.  We pivot it to long format and assign
    placeholder prices of NaN so that rows appear in the merged dataset
    but are excluded from unit-price ranking until prices are scraped.

    Parameters
    ----------
    filepath : str
        Path to Item_List.csv.

    Returns
    -------
    pd.DataFrame
        Standard-schema DataFrame (unit_price will be NaN for these rows).
    """
    logger.info("Adapting Item_List from: %s", filepath)
    raw = pd.read_csv(filepath, dtype=str)

    stores = ["Aldi", "Kroger", "Walmart", "Ruler"]
    records = []

    for _, row in raw.iterrows():
        category_raw = str(row.get("Category", "")).strip()
        # Parse category name (strip size hint in parentheses for the name)
        cat_name = re.sub(r"\s*\(.*?\)", "", category_raw).strip().lower()

        for store in stores:
            item_col = f"{store}-Item"
            item_name = str(row.get(item_col, "")).strip()
            if not item_name or item_name.lower() in ("nan", ""):
                continue

            records.append(
                {
                    "product_name": item_name,
                    "store":        store,
                    "price":        float("nan"),   # no price in source
                    "quantity":     float("nan"),   # no quantity in source
                    "unit":         "unit",         # discrete unit placeholder
                    "category":     cat_name,
                }
            )

    out = pd.DataFrame(records)
    logger.info("Item_List adapter: %d rows generated.", len(out))
    return out


# ===========================================================================
# 3. Build adapted combined CSV
# ===========================================================================

def build_adapted_datasets(
    grocerydb_path: str,
    item_list_path: str | None = None,
    max_grocerydb_rows: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return two adapted DataFrames ready for the preprocessing pipeline.

    Parameters
    ----------
    grocerydb_path : str
        Path to GroceryDB_foods.csv.
    item_list_path : str, optional
        Path to Item_List.csv.  If None or file absent, returns empty DataFrame.
    max_grocerydb_rows : int, optional
        Cap GroceryDB rows (default: all).

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (grocerydb_df, item_list_df)
    """
    gdb = adapt_grocerydb(grocerydb_path, max_rows=max_grocerydb_rows)
    if item_list_path and Path(item_list_path).exists():
        itl = adapt_item_list(item_list_path)
    else:
        logger.info("Item_List path not provided or not found – skipping.")
        itl = pd.DataFrame()
    return gdb, itl


# ---------------------------------------------------------------------------
# CLI: python -m src.data_adapter
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    _base = Path(__file__).parent.parent / "data" / "raw"
    _gdb  = _base / "GroceryDB_foods.csv"
    _itl  = _base / "Item_List.csv"

    if not _gdb.exists():
        print(f"ERROR: {_gdb} not found.", file=sys.stderr)
        sys.exit(1)

    gdb_df, itl_df = build_adapted_datasets(str(_gdb), str(_itl))

    print(f"\nGroceryDB adapted: {len(gdb_df):,} rows")
    print(gdb_df[["product_name", "store", "price", "quantity", "unit", "category"]].head(5))

    print(f"\nItem_List adapted: {len(itl_df):,} rows")
    print(itl_df.head(5))
