"""
FastAPI Backend Server for Price Formation System
CSCE 5200 - Group 7

Search strategy — 4-tier relevance ranking:
  Tier 1: query is the PRIMARY noun (product name ends with or starts with query)
  Tier 2: exact word-boundary match, same unit domain (liquid/solid consistency)
  Tier 3: word-boundary match, different domain (cross-domain penalty)
  Tier 4: substring fallback (only when no word-boundary results)

Unit display:
  $/g  → $/100g
  $/ml → $/L
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pathlib import Path
import math
import re

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
    global _df_cache
    if _df_cache is not None:
        return _df_cache
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(DATA_PATH)
    df = df.replace({math.nan: None})
    _df_cache = df
    return df


def invalidate_cache():
    global _df_cache
    _df_cache = None


# ---------------------------------------------------------------------------
# Unit display helpers
# ---------------------------------------------------------------------------

def display_unit_price(unit_price, canonical_unit):
    """$/g → $/100g,  $/ml → $/L"""
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
    up, cu = display_unit_price(row.get("unit_price"), row.get("canonical_unit"))
    row = dict(row)
    row["unit_price"] = up
    row["canonical_unit"] = cu
    if row.get("quantity") is not None:
        try:
            row["quantity"] = round(float(row["quantity"]), 2)
        except (TypeError, ValueError):
            pass
    return row


# ---------------------------------------------------------------------------
# Domain detection  (liquid vs solid)
# ---------------------------------------------------------------------------

# Query words that are inherently liquid products
_LIQUID_QUERY_WORDS = frozenset({
    "milk", "juice", "water", "soda", "oil", "vinegar", "broth", "stock",
    "cream", "kefir", "kombucha", "lemonade", "tea", "coffee", "beer",
    "wine", "yogurt", "smoothie", "shake", "drink", "beverage", "syrup",
    "sauce", "soup",
})

# Query words that are inherently solid/dry products
_SOLID_QUERY_WORDS = frozenset({
    "rice", "flour", "sugar", "salt", "cereal", "oats", "pasta", "bread",
    "cracker", "chip", "cookie", "cake", "muffin", "bagel", "nut", "seed",
    "bean", "lentil", "pepper", "spice", "herb", "protein powder",
    "eggs", "butter", "cheese", "meat", "chicken", "beef", "pork", "fish",
    "shrimp", "salmon", "tuna",
})

# Known modifier words that make a match irrelevant
# e.g. "milk thistle", "milk chocolate frosting", "condensed milk"
# — not "pure" milk products
_MODIFIER_WORDS_AFTER: dict[str, set[str]] = {
    "milk": {"thistle", "chocolate", "morsels", "frosting", "chocolate frosting",
             "powder", "based", "derived", "flavored", "flavoured"},
}

# Categories that indicate supplements / non-food
_SUPPLEMENT_CATEGORIES = frozenset({
    "health", "medicine", "supplements", "vitamins",
})


def _query_domain(query: str) -> str:
    """Return 'liquid', 'solid', or 'any' for the query."""
    q = query.lower().strip()
    if q in _LIQUID_QUERY_WORDS:
        return "liquid"
    if q in _SOLID_QUERY_WORDS:
        return "solid"
    return "any"


def _is_false_positive(name: str, query: str) -> bool:
    """Return True if this product name is a known false-positive for the query."""
    name_lower = name.lower()
    q = query.lower()
    mods = _MODIFIER_WORDS_AFTER.get(q, set())
    for mod in mods:
        if re.search(r"\b" + re.escape(q) + r"\s+" + re.escape(mod), name_lower):
            return True
    return False


# ---------------------------------------------------------------------------
# 4-tier relevance search
# ---------------------------------------------------------------------------

_re_cache: dict[str, re.Pattern] = {}


def _word_re(query: str) -> re.Pattern:
    if query not in _re_cache:
        _re_cache[query] = re.compile(r"\b" + re.escape(query.strip()) + r"\b", re.IGNORECASE)
    return _re_cache[query]


def _relevance_score(name: str, canonical_unit: str, query: str, domain: str) -> int:
    """
    Higher = more relevant.

    5 — primary noun: name ends or starts with query (e.g. "whole milk", "milk 1 gallon")
    4 — word-boundary match + unit domain matches expected (liquid query + ml unit)
    3 — word-boundary match, domain neutral or unknown
    2 — word-boundary match but domain mismatch (solid query → liquid product, or vice versa)
    1 — word-boundary match but likely false positive (modifier word follows query)
    0 — substring only (no word boundary)
    """
    name_lower = name.lower().strip()
    q = query.lower()

    # Word-boundary check
    has_wb = bool(_word_re(q).search(name_lower))
    if not has_wb:
        return 0

    # False positive check
    if _is_false_positive(name_lower, q):
        return 1

    # Domain match
    unit_is_liquid = canonical_unit in ("ml",)
    unit_is_solid  = canonical_unit in ("g", "kg")
    domain_match = (
        (domain == "liquid" and unit_is_liquid) or
        (domain == "solid"  and unit_is_solid)  or
        domain == "any"
    )
    domain_mismatch = not domain_match and domain != "any"

    # Primary noun check — query is the last significant word in the name
    # e.g. "vitamin d whole milk" → milk at end = primary
    words = re.findall(r"[a-z]+", name_lower)
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
    """
    4-tier relevance search.
    Results sorted by (relevance_score DESC, unit_price ASC).
    """
    query_clean = query.lower().strip()
    domain      = _query_domain(query_clean)
    names       = df["product_name"].fillna("").str.lower()

    # ── Word-boundary candidates ───────────────────────────────────────────
    word_re  = _word_re(query_clean)
    mask_wb  = names.str.contains(word_re, regex=True)
    tier_wb  = df[mask_wb].copy()

    # ── Substring fallback ────────────────────────────────────────────────
    if tier_wb.empty:
        mask_sub = names.str.contains(re.escape(query_clean), regex=True)
        combined = df[mask_sub].copy()
    else:
        combined = tier_wb

    # Filter valid unit prices only
    valid = combined[combined["unit_price"].notna()].copy()
    if valid.empty:
        return valid

    # Score each row
    valid["_relevance"] = valid.apply(
        lambda row: _relevance_score(
            str(row["product_name"]),
            str(row.get("canonical_unit", "")),
            query_clean,
            domain,
        ),
        axis=1,
    )

    # Drop score-1 (false positives) if we have higher-scoring results
    max_score = valid["_relevance"].max()
    if max_score >= 3:
        valid = valid[valid["_relevance"] >= 2]  # drop clear false positives

    # Sort: relevance DESC, then unit_price ASC (best value within each tier)
    valid = valid.sort_values(["_relevance", "unit_price"], ascending=[False, True])

    return valid.drop(columns=["_relevance"]).head(limit)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/products")
def get_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500)
):
    df = load_data()
    if df.empty:
        return {"data": [], "total": 0, "page": page, "limit": limit}

    valid = df[df["unit_price"].notna()].copy()
    valid = valid.sort_values("unit_price", ascending=True)

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
    """4-tier relevance search with domain awareness."""
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
    df = load_data()
    if df.empty:
        return {}
    valid = df[df["unit_price"].notna()]
    stats = (
        valid.groupby("store")
        .agg(products=("product_name", "count"),
             avg_price=("price", "mean"),
             avg_unit_p=("unit_price", "mean"))
        .reset_index()
    )
    return stats.to_dict(orient="records")


@app.post("/api/reload")
def reload_data():
    invalidate_cache()
    df = load_data()
    return {"status": "reloaded", "rows": len(df)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
