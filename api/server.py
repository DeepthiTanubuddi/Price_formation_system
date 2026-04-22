"""
server.py
---------
FastAPI backend for the SmartCompare Price Formation System.
CSCE 5200 - Group 7

Search uses a 4-tier relevance system:
  Tier 5: query is the primary noun (name ends or starts with the query word)
  Tier 4: exact word-boundary match + unit domain matches (e.g. milk query → ml unit)
  Tier 3: word-boundary match, domain neutral or unknown
  Tier 2: word-boundary match but domain mismatch (e.g. solid query → liquid product)
  Tier 1: word-boundary match but likely a false positive (modifier word follows query)
  Tier 0: substring only (no word boundary found)

Unit display conversions applied before sending to the frontend:
  $/g  → $/100g  (easier for humans to compare)
  $/ml → $/L
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pathlib import Path
import math
import re

from src.catalog_enrichment import enrich_catalog_metadata

app = FastAPI(title="Price Formation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = Path(__file__).parent.parent / "data" / "processed" / "combined.csv"

_df_cache = None


def load_data() -> pd.DataFrame:
    """Load the combined CSV into memory, caching it after the first call."""
    global _df_cache
    if _df_cache is not None:
        return _df_cache
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(DATA_PATH)
    df = enrich_catalog_metadata(df)
    df = df.replace({math.nan: None})
    _df_cache = df
    return df


def invalidate_cache():
    """Clear the in-memory data cache so the next request reloads from disk."""
    global _df_cache
    _df_cache = None


# ── Unit display helpers ──────────────────────────────────────────────────────

def display_unit_price(unit_price, canonical_unit):
    """Convert raw unit prices to human-friendly display units.

    $/g  → $/100g  (avoids tiny numbers like $0.0005)
    $/ml → $/L
    """
    if unit_price is None or canonical_unit is None:
        return unit_price, canonical_unit
    try:
        up = float(unit_price)
    except (TypeError, ValueError):
        return unit_price, canonical_unit
    if canonical_unit == "g":
        return round(up * 100, 4), "100g"
    if canonical_unit == "ml":
        return round(up * 1000, 4), "L"
    return round(up, 6), canonical_unit


def format_row(row: dict) -> dict:
    """Apply display unit conversion to a single product row."""
    up, cu = display_unit_price(row.get("unit_price"), row.get("canonical_unit"))
    row = dict(row)
    row["unit_price"]     = up
    row["canonical_unit"] = cu
    if row.get("quantity") is not None:
        try:
            row["quantity"] = round(float(row["quantity"]), 2)
        except (TypeError, ValueError):
            pass
    return row


def _store_highlights(df: pd.DataFrame, store: str, limit: int = 5) -> pd.DataFrame:
    """Return the top 'best-selling style' items for a given store.

    The dataset doesn't have sales volume data, so we use a proxy:
    items from common staple categories with valid unit prices,
    sorted toward broadly useful low-cost/value products,
    deduplicated by product name.
    """
    valid = df[df["unit_price"].notna()].copy()
    if valid.empty:
        return valid

    store_key = store.lower().replace(" ", "")
    scoped    = valid[valid["store"].fillna("").str.lower().str.replace(" ", "", regex=False) == store_key].copy()
    if scoped.empty:
        return scoped

    staple_keywords = (
        "milk", "rice", "egg", "bread", "pasta", "cereal", "coffee", "tea",
        "juice", "water", "chicken", "beef", "cheese", "butter", "fruit",
        "vegetable", "produce", "snack", "yogurt", "oat", "flour", "sugar",
    )

    scoped["category_text"] = scoped["category"].fillna("").str.lower()
    scoped["name_text"]     = scoped["product_name"].fillna("").str.lower()
    scoped["staple_score"]  = scoped.apply(
        lambda row: sum(
            1 for term in staple_keywords if term in row["category_text"] or term in row["name_text"]
        ),
        axis=1,
    )

    scoped = scoped.sort_values(
        ["staple_score", "unit_price", "price"],
        ascending=[False, True, True],
    )
    scoped = scoped.drop_duplicates(subset=["product_name"])
    return scoped.head(limit)


# ── Domain detection: liquid vs. solid ───────────────────────────────────────
# Used to boost relevance for results that match the expected product type.

# Words that clearly imply a liquid product.
_LIQUID_QUERY_WORDS = frozenset({
    "milk", "juice", "water", "soda", "oil", "vinegar", "broth", "stock",
    "cream", "kefir", "kombucha", "lemonade", "tea", "coffee", "beer",
    "wine", "yogurt", "smoothie", "shake", "drink", "beverage", "syrup",
    "sauce", "soup",
})

# Words that clearly imply a solid or dry product.
_SOLID_QUERY_WORDS = frozenset({
    "rice", "flour", "sugar", "salt", "cereal", "oats", "pasta", "bread",
    "cracker", "chip", "cookie", "cake", "muffin", "bagel", "nut", "seed",
    "bean", "lentil", "pepper", "spice", "herb", "protein powder",
    "eggs", "butter", "cheese", "meat", "chicken", "beef", "pork", "fish",
    "shrimp", "salmon", "tuna",
})

# Modifier words that, when they follow the query word, indicate a false positive.
# Example: "milk thistle" or "milk chocolate frosting" — not actually a milk product.
_MODIFIER_WORDS_AFTER: dict[str, set[str]] = {
    "milk": {"thistle", "chocolate", "morsels", "frosting", "chocolate frosting",
             "powder", "based", "derived", "flavored", "flavoured"},
}

# Categories that suggest a supplement or non-food item.
_SUPPLEMENT_CATEGORIES = frozenset({
    "health", "medicine", "supplements", "vitamins",
})


def _query_domain(query: str) -> str:
    """Return 'liquid', 'solid', or 'any' for the given query string."""
    q = query.lower().strip()
    if q in _LIQUID_QUERY_WORDS:
        return "liquid"
    if q in _SOLID_QUERY_WORDS:
        return "solid"
    return "any"


def _is_false_positive(name: str, query: str) -> bool:
    """Return True if this product is a known false positive for the query.

    For example, "milk thistle" when searching for "milk".
    """
    name_lower = name.lower()
    q    = query.lower()
    mods = _MODIFIER_WORDS_AFTER.get(q, set())
    for mod in mods:
        if re.search(r"\b" + re.escape(q) + r"\s+" + re.escape(mod), name_lower):
            return True
    return False


# ── 4-tier relevance scoring ──────────────────────────────────────────────────

_re_cache: dict[str, re.Pattern] = {}


def _word_re(query: str) -> re.Pattern:
    """Return (and cache) a compiled word-boundary regex for the query."""
    if query not in _re_cache:
        _re_cache[query] = re.compile(r"\b" + re.escape(query.strip()) + r"\b", re.IGNORECASE)
    return _re_cache[query]


def _relevance_score(name: str, canonical_unit: str, query: str, domain: str) -> int:
    """Score a product's relevance to the query. Higher = more relevant.

    5 - primary noun: name ends or starts with the query word (e.g. "whole milk", "milk 1 gallon")
    4 - word-boundary match + unit domain matches what we expect
    3 - word-boundary match, domain is neutral or unknown
    2 - word-boundary match but domain doesn't match (e.g. solid query → liquid product)
    1 - word-boundary match but likely a false positive (modifier word follows query)
    0 - substring only (no word boundary found)
    """
    name_lower = name.lower().strip()
    q          = query.lower()

    has_wb = bool(_word_re(q).search(name_lower))
    if not has_wb:
        return 0

    if _is_false_positive(name_lower, q):
        return 1

    unit_is_liquid = canonical_unit in ("ml",)
    unit_is_solid  = canonical_unit in ("g", "kg")
    domain_match   = (
        (domain == "liquid" and unit_is_liquid) or
        (domain == "solid"  and unit_is_solid)  or
        domain == "any"
    )
    domain_mismatch = not domain_match and domain != "any"

    # Primary noun check: query is the last or first significant word in the name.
    words      = re.findall(r"[a-z]+", name_lower)
    is_primary = (
        words and (words[-1] == q or words[0] == q)
        or bool(re.search(r"\b" + re.escape(q) + r"\b\s*([-–]|\d|$)", name_lower))
    )

    if is_primary and domain_match:
        return 5
    if is_primary:
        return 4
    if domain_match:
        return 4
    if domain_mismatch:
        return 2
    return 3


def smart_search(df: pd.DataFrame, query: str, limit: int = 50) -> pd.DataFrame:
    """Run a 4-tier relevance search and return the top results.

    Results are sorted by (relevance_score DESC, unit_price ASC).
    Falls back to substring matching when no word-boundary results are found.
    """
    query_clean = query.lower().strip()
    domain      = _query_domain(query_clean)
    names       = df["product_name"].fillna("").str.lower()

    # Try word-boundary matches first.
    word_re = _word_re(query_clean)
    mask_wb = names.str.contains(word_re, regex=True)
    tier_wb = df[mask_wb].copy()

    # Fall back to substring matching if word-boundary returns nothing.
    if tier_wb.empty:
        mask_sub = names.str.contains(re.escape(query_clean), regex=True)
        combined = df[mask_sub].copy()
    else:
        combined = tier_wb

    # Only include products that have a valid unit price.
    valid = combined[combined["unit_price"].notna()].copy()
    if valid.empty:
        return valid

    valid["_relevance"] = valid.apply(
        lambda row: _relevance_score(
            str(row["product_name"]),
            str(row.get("canonical_unit", "")),
            query_clean,
            domain,
        ),
        axis=1,
    )

    # Drop clear false positives if we have better results available.
    max_score = valid["_relevance"].max()
    if max_score >= 3:
        valid = valid[valid["_relevance"] >= 2]

    valid = valid.sort_values(["_relevance", "unit_price"], ascending=[False, True])

    return valid.drop(columns=["_relevance"]).head(limit)


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    """Health check endpoint for Render.com"""
    return {"status": "ok", "message": "Price Formation API is running"}

@app.get("/api/products")
def get_products(
    page:  int = Query(1,  ge=1),
    limit: int = Query(50, ge=1, le=500)
):
    """Return a paginated list of all products, sorted by unit price."""
    df = load_data()
    if df.empty:
        return {"data": [], "total": 0, "page": page, "limit": limit}

    valid     = df[df["unit_price"].notna()].copy()
    valid     = valid.sort_values("unit_price", ascending=True)

    total     = len(valid)
    start_idx = (page - 1) * limit
    rows      = valid.iloc[start_idx:start_idx + limit].to_dict(orient="records")
    return {
        "data":  [format_row(r) for r in rows],
        "total": total,
        "page":  page,
        "limit": limit,
    }


@app.get("/api/search")
def search_products(
    q:     str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
):
    """Search products using 4-tier relevance scoring with domain awareness."""
    df = load_data()
    if df.empty:
        return {"data": [], "total": 0}

    matched = smart_search(df, q.strip(), limit=limit)
    return {
        "data":  [format_row(r) for r in matched.to_dict(orient="records")],
        "total": len(matched),
        "query": q.strip(),
    }


@app.get("/api/stores")
def get_store_stats():
    """Return aggregate statistics (product count, average prices) per store."""
    df = load_data()
    if df.empty:
        return {}
    valid = df[df["unit_price"].notna()]
    stats = (
        valid.groupby("store")
        .agg(products=(  "product_name", "count"),
             avg_price=(  "price",       "mean"),
             avg_unit_p=( "unit_price",  "mean"))
        .reset_index()
    )
    return stats.to_dict(orient="records")


@app.get("/api/stores/{store_name}/highlights")
def get_store_highlights(
    store_name: str,
    limit: int = Query(5, ge=1, le=10),
):
    """Return the top staple-category products for a given store.

    Since the dataset has no sales volume data, 'best sellers' are inferred
    from staple-category relevance and value (unit price).
    """
    df = load_data()
    if df.empty:
        return {"store": store_name, "data": [], "total": 0}

    highlights = _store_highlights(df, store_name, limit=limit)
    return {
        "store": store_name,
        "data":  [format_row(r) for r in highlights.to_dict(orient="records")],
        "total": len(highlights),
        "note":  "Best-seller picks are inferred from staple-category relevance and value because sales volume is not in the dataset.",
    }


@app.post("/api/reload")
def reload_data():
    """Clear the data cache and reload the processed CSV from disk."""
    invalidate_cache()
    df = load_data()
    return {"status": "reloaded", "rows": len(df)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
