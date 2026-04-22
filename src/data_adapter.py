"""
data_adapter.py
---------------
Converts our real-world source files into the standard schema used by the
rest of the pipeline.
CSCE 5200 - Group 7

Source files:
  GroceryDB_foods.csv — scraped grocery product data from Walmart, Target, and Whole Foods.
    Relevant columns: name, store, price, package_weight (grams), harmonized category.
    The store is encoded in the original_ID prefix: tg_ = Target, wf_ = Whole Foods, wm_ = Walmart.

  Item_List.csv — wide-format product list with one column per store.
    Columns: Category, Aldi-Item, Aldi-Link, Aldi-Multiplier, Kroger-Item, ...
    No prices — this file is only used for category and product name enrichment.

Target schema for both sources:
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

# Maps GroceryDB original_ID prefixes to human-readable store names.
_ID_PREFIX_STORE: dict[str, str] = {
    "tg_": "Target",
    "wf_": "WholeFoods",
    "wm_": "Walmart",
}

# Maps GroceryDB category slugs to our simplified category labels.
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

# GroceryDB stores all package quantities in grams, even for liquids.
# For liquid products we treat the gram value as ml (density ≈ 1 g/mL
# for water-based products — close enough for price comparison).

# Categories that are definitely liquids.
_LIQUID_CATEGORIES: frozenset[str] = frozenset({
    "beverages", "drink-juice", "drink-juice-wf", "drink-water-wf",
    "drink-soft-energy-mixes", "drink-coffee", "drink-tea",
    "drink-shakes-other", "milk-milk-substitute", "dairy-yogurt-drink",
})

# Product name keywords that imply a liquid regardless of category.
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

# Categories that are always solid (force grams even if the name looks ambiguous).
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
    """Return True if the product is likely a liquid (should use ml instead of g)."""
    cat = (category or "").lower().strip()

    if cat in _SOLID_CATEGORIES:
        return False

    if cat in _LIQUID_CATEGORIES:
        return True

    # Fall back to name-based heuristic when category is ambiguous.
    name_lower = (" " + (product_name or "").lower() + " ")
    for kw in _LIQUID_NAME_KEYWORDS:
        if kw in name_lower:
            return True

    return False


# Regex for stripping HTML entities that occasionally appear in GroceryDB product names.
_HTML_ENTITY_RE = re.compile(r"&#?\w+;")

def _clean_html_entities(text: str) -> str:
    """Replace common HTML entities with their ASCII equivalents."""
    text = text.replace("&#39;", "'").replace("&#38;", "&").replace("&#8482;", "")
    text = text.replace("&#8211;", "-").replace("&#8212;", "-")
    return _HTML_ENTITY_RE.sub("", text).strip()


def adapt_grocerydb(filepath: str, max_rows: int | None = None) -> pd.DataFrame:
    """Convert GroceryDB_foods.csv to our standard schema.

    Strategy:
    - package_weight is in grams, so we use it as the quantity with unit = "g".
    - For liquids we use "ml" instead (1 g ≈ 1 ml for water-based products).
    - We derive the store name from the original_ID prefix (tg_, wf_, wm_).
    - We drop rows with a missing price or weight since we can't compute a unit price for them.
    - We apply the max_rows cap when provided (useful for fast test runs).

    Parameters
    ----------
    filepath : str
        Path to GroceryDB_foods.csv.
    max_rows : int, optional
        Only keep the first N valid rows. Useful for faster testing.

    Returns
    -------
    pd.DataFrame
        Standard-schema DataFrame.
    """
    logger.info("Adapting GroceryDB from: %s", filepath)
    raw = pd.read_csv(filepath, dtype=str, low_memory=False)

    raw = raw.rename(columns={
        "name":                       "product_name",
        "harmonized single category": "category",
        "package_weight":             "quantity",
    })

    def _store_from_id(orig_id: str) -> str:
        if isinstance(orig_id, str):
            for prefix, store in _ID_PREFIX_STORE.items():
                if orig_id.startswith(prefix):
                    return store
        return "Unknown"

    raw["store"] = raw["original_ID"].apply(_store_from_id)

    # Remove any rows where we couldn't identify the store.
    raw = raw[raw["store"] != "Unknown"].copy()

    raw["price"]    = pd.to_numeric(raw["price"],    errors="coerce")
    raw["quantity"] = pd.to_numeric(raw["quantity"], errors="coerce")

    # We need both price and quantity to compute a unit price.
    raw = raw.dropna(subset=["price", "quantity"])
    raw = raw[raw["price"] > 0]
    raw = raw[raw["quantity"] > 0]

    raw["unit"] = raw.apply(
        lambda row: "ml" if _is_liquid(
            str(row.get("category", "")),
            str(row.get("product_name", ""))
        ) else "g",
        axis=1,
    )

    raw["category"] = raw["category"].fillna("other").str.strip().str.lower()
    raw["category"] = raw["category"].map(_CATEGORY_MAP).fillna(raw["category"])

    raw["product_name"] = raw["product_name"].apply(
        lambda x: _clean_html_entities(str(x)) if isinstance(x, str) else x
    )

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


def adapt_item_list(filepath: str) -> pd.DataFrame:
    """Convert wide-format Item_List.csv to our standard schema.

    The Item_List file has no prices — it's used purely to enrich the
    product/category dimension. We pivot it to long format and set
    price/quantity to NaN as placeholders. These rows appear in the merged
    dataset but are excluded from unit price ranking since they have no prices.

    Parameters
    ----------
    filepath : str
        Path to Item_List.csv.

    Returns
    -------
    pd.DataFrame
        Standard-schema DataFrame (unit_price will be NaN for all these rows).
    """
    logger.info("Adapting Item_List from: %s", filepath)
    raw = pd.read_csv(filepath, dtype=str)

    stores = ["Aldi", "Kroger", "Walmart", "Ruler"]
    records = []

    for _, row in raw.iterrows():
        category_raw = str(row.get("Category", "")).strip()
        cat_name = re.sub(r"\s*\(.*?\)", "", category_raw).strip().lower()

        for store in stores:
            item_col  = f"{store}-Item"
            item_name = str(row.get(item_col, "")).strip()
            if not item_name or item_name.lower() in ("nan", ""):
                continue

            records.append(
                {
                    "product_name": item_name,
                    "store":        store,
                    "price":        float("nan"),   # no price in source
                    "quantity":     float("nan"),   # no quantity in source
                    "unit":         "unit",         # placeholder
                    "category":     cat_name,
                }
            )

    out = pd.DataFrame(records)
    logger.info("Item_List adapter: %d rows generated.", len(out))
    return out


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
        Path to Item_List.csv. If None or the file is missing, returns an empty DataFrame.
    max_grocerydb_rows : int, optional
        Cap the number of GroceryDB rows (default: all rows).

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (grocerydb_df, item_list_df)
    """
    gdb = adapt_grocerydb(grocerydb_path, max_rows=max_grocerydb_rows)
    if item_list_path and Path(item_list_path).exists():
        itl = adapt_item_list(item_list_path)
    else:
        logger.info("Item_List path not provided or not found — skipping.")
        itl = pd.DataFrame()
    return gdb, itl


# Run directly to inspect a quick sample of both adapted outputs.
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
