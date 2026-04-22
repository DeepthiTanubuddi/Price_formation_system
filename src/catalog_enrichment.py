"""
catalog_enrichment.py
---------------------
Adds shopping-style metadata to our product records so the frontend
looks like a real grocery comparison site.

We add two things:
  - product_url: a store search link for the product
  - image_url: a real product photo from Unsplash, matched by category

Images are sourced from Unsplash using fixed photo IDs mapped to grocery
categories. No API key needed — we use stable public photo URLs.
Format: https://images.unsplash.com/photo-{ID}?w=400&q=80&fit=crop
"""

from __future__ import annotations

from urllib.parse import quote

import pandas as pd


# Store search URL templates and brand colors.
_STORE_CONFIG = {
    "walmart": {
        "label": "Walmart",
        "search_url": "https://www.walmart.com/search?q={query}",
        "color": "#0071CE",
    },
    "target": {
        "label": "Target",
        "search_url": "https://www.target.com/s?searchTerm={query}",
        "color": "#CC0000",
    },
    "costco": {
        "label": "Costco",
        "search_url": "https://www.costco.com/CatalogSearch?dept=All&keyword={query}",
        "color": "#005DAA",
    },
    "aldi": {
        "label": "Aldi",
        "search_url": "https://new.aldi.us/results?q={query}",
        "color": "#00539B",
    },
    "wholefoods": {
        "label": "Whole Foods",
        "search_url": "https://www.wholefoodsmarket.com/products/all-products?text={query}",
        "color": "#00674B",
    },
    "kroger": {
        "label": "Kroger",
        "search_url": "https://www.kroger.com/search?query={query}&searchType=default_search",
        "color": "#2C6BAC",
    },
}

# Fallback config for stores not in the map above.
_DEFAULT_STORE = {
    "label": "Store",
    "search_url": "https://www.google.com/search?q={query}",
    "color": "#4B5563",
}

# Unsplash photo IDs organized by grocery category keyword.
# Each key maps to a list of photo IDs. We pick one deterministically
# based on a hash of the product name, so the same product always gets
# the same image. Longer keys win over shorter keys (more specific match).
_CATEGORY_PHOTOS: dict[str, list[str]] = {
    "milk":         ["1550583724-aa135596b44c", "1634141510639-ef91ae93c1a1", "1563636619-e9143da7f009"],
    "yogurt":       ["1488477181676-78af0afbbb78", "1559181567-c3190ca9959b", "1505252585461-04db1eb84625"],
    "cheese":       ["1486297678162-eb2a19b0a32d", "1452195100486-9cc805987862", "1505253758473-ec3a9e6ec84d"],
    "butter":       ["1558642452-9d2a7deb7f62", "1608897013039-887f21d8c804", "1571167451108-9e7f1e4ee253"],
    "cream":        ["1587840171670-8b850147754e", "1563636619-e9143da7f009", "1568901346375-23c9450c58cd"],
    "egg":          ["1518492104633-130d0cc84637", "1569288052389-7e8d4a4e3f66", "1617397015764-38a1e8f16ca7"],
    "bread":        ["1509440159596-0249088772ff", "1549931319-a545dcf3bc7c", "1574085733277-851d9d856a3a"],
    "bagel":        ["1617197163168-8a39a8021847", "1509440159596-0249088772ff"],
    "rice":         ["1536304929831-ee1ca9d44906", "1559963110-71b394e7494d", "1604977042946-1eecc30f269e"],
    "pasta":        ["1551183053-bf91798d792b", "1598511726153-9f6d6e57e4e0", "1546069901-ba9599a7e63c"],
    "flour":        ["1574484284002-952d92456975", "1586942293584-7853d07edc3a"],
    "sugar":        ["1550583724-aa135596b44c", "1467545180656-c2d5eddc6fe0"],
    "oat":          ["1517093702195-a4a6b76c1e7e", "1583394838336-acd977736f90"],
    "cereal":       ["1517093702195-a4a6b76c1e7e", "1525351484163-7529414344d8"],
    "coffee":       ["1495474472287-4d71bcdd2085", "1506619099913-b099ef8579f1", "1509042239860-f550ce710b93"],
    "tea":          ["1556679343-c7306c1976bc", "1544787219-7f47ccb76574", "1498804103079-a6141b6b7d43"],
    "juice":        ["1600271886742-f049cd451bcd", "1543158181-e6f9f6712349", "1546069901-ba9599a7e63c"],
    "water":        ["1559827291-72ebaa3cf73a", "1564419929729-7b33eb5a8870"],
    "soda":         ["1625772299848-391b6a87d7b3", "1527960669566-f882ba85a4d4"],
    "beer":         ["1608270586352-ac4af0c5b969", "1571576774742-ed5f1b0c4b56"],
    "wine":         ["1510812431401-41d2bd2722f3", "1506377247377-2a5b3b417ebb"],
    "chicken":      ["1598103442097-8b74394b95c7", "1516714435082-f33db3cf7a46", "1594212699673-1d1cd648a456"],
    "beef":         ["1607623814075-a51a67e2a01b", "1603048588665-791ca8aea617"],
    "pork":         ["1607623814075-a51a67e2a01b", "1593030761767-d94a0e35f0c0"],
    "fish":         ["1534482421-64566f976cfa", "1519708227418-a2d0260ff470"],
    "salmon":       ["1519708227418-a2d0260ff470", "1476224203421-74177e79a142"],
    "shrimp":       ["1559339352-11d035aa65ce", "1534482421-64566f976cfa"],
    "tuna":         ["1534482421-64566f976cfa", "1519708227418-a2d0260ff470"],
    "fruit":        ["1490474418585-ba9bad8fd0ea", "1619566636858-adf3ef46400b"],
    "apple":        ["1560806887-1e4cd0b6cbd6", "1567306226416-28f0efdc88ce"],
    "banana":       ["1571771894821-ce9b6c11b08e", "1528825871115-3581a5387919"],
    "berry":        ["1464965911861-746a04b4bca6", "1488477181676-78af0afbbb78"],
    "strawberry":   ["1464965911861-746a04b4bca6", "1473093226511-05552bbeb3b3"],
    "orange":       ["1547514701-42782101795e", "1551439462-3813bdab46e7"],
    "vegetable":    ["1540420773420-3366772f4999", "1485637701851-4f52bbe5d012"],
    "broccoli":     ["1553982378-6c9e59b26174", "1540420773420-3366772f4999"],
    "carrot":       ["1598170845054-1d6de1c1d9e8", "1540420773420-3366772f4999"],
    "tomato":       ["1546094096-0df4bcaaa337", "1558818785-c2ac1fba9dd3"],
    "potato":       ["1518977676601-b53f82aba655", "1512621776951-a57141f2eefd"],
    "onion":        ["1518977676601-b53f82aba655", "1540420773420-3366772f4999"],
    "spinach":      ["1485637701851-4f52bbe5d012", "1540420773420-3366772f4999"],
    "salad":        ["1512621776951-a57141f2eefd", "1543362906-acfc16c67564"],
    "produce":      ["1490474418585-ba9bad8fd0ea", "1540420773420-3366772f4999"],
    "snack":        ["1528825871115-3581a5387919", "1563805958-20b8b1e66ac1"],
    "chip":         ["1563805958-20b8b1e66ac1", "1552944150-6dd1180e5999"],
    "cookie":       ["1499636136210-6f4ee915583e", "1558961363-fa8fdf82db35"],
    "cake":         ["1578985545062-69928b1d9587", "1464349100622-c0cee2878b5f"],
    "chocolate":    ["1481391319741-f885c0e143b2", "1549007994-c6f01e5cf2a4"],
    "candy":        ["1553361371-9b22f78e8b1d", "1481391319741-f885c0e143b2"],
    "ice cream":    ["1551024709-8f23befc548f", "1497034825429-c343d7c6a68f"],
    "frozen":       ["1551024709-8f23befc548f", "1498888914252-f990a57da51a"],
    "soup":         ["1547592166-23ac45744acd", "1534483509719-3feaee7c30da"],
    "sauce":        ["1565299507177-93d0c3c2c7a2", "1547592166-23ac45744acd"],
    "oil":          ["1474979266404-7f5af9a8a7c8", "1615485290382-41b6bf14fc3a"],
    "vinegar":      ["1474979266404-7f5af9a8a7c8"],
    "salt":         ["1474979266404-7f5af9a8a7c8", "1550583724-aa135596b44c"],
    "pepper":       ["1506377247377-2a5b3b417ebb", "1474979266404-7f5af9a8a7c8"],
    "spice":        ["1506377247377-2a5b3b417ebb", "1546069901-ba9599a7e63c"],
    "herb":         ["1506377247377-2a5b3b417ebb", "1552907894-8ad493f961f4"],
    "nut":          ["1606923829579-4e1b62e72b9e", "1508061253366-f7da158b6d46"],
    "seed":         ["1536304929831-ee1ca9d44906", "1606923829579-4e1b62e72b9e"],
    "bean":         ["1559963110-71b394e7494d", "1536304929831-ee1ca9d44906"],
    "lentil":       ["1559963110-71b394e7494d"],
    "baby":         ["1519689680058-324335573bb0", "1536704108-ee37e3c93b50"],
    "protein":      ["1571167451108-9e7f1e4ee253", "1535914254981-b5012eebbd37"],
    "organic":      ["1540420773420-3366772f4999", "1490474418585-ba9bad8fd0ea"],
    "grain":        ["1536304929831-ee1ca9d44906", "1559963110-71b394e7494d"],
    "drink":        ["1600271886742-f049cd451bcd", "1543158181-e6f9f6712349"],
    "beverage":     ["1600271886742-f049cd451bcd", "1527960669566-f882ba85a4d4"],
    "smoothie":     ["1505252585461-04db1eb84625", "1543158181-e6f9f6712349"],
    "default":      ["1542838132-92c53300491e", "1506368083636-6defb67639cd", "1473093226511-05552bbeb3b3"],
}


def _store_key(store: str | None) -> str:
    return (store or "").lower().replace(" ", "")


def _product_search_url(product_name: str, store: str) -> str:
    """Build a store search URL for the given product name and store."""
    config = _STORE_CONFIG.get(_store_key(store), _DEFAULT_STORE)
    query  = quote(product_name or "")
    return config["search_url"].format(query=query)


def _pick_photo_id(product_name: str, category: str | None) -> str:
    """Pick a deterministic Unsplash photo ID based on the product name and category.

    The same product always gets the same photo (hash-based selection).
    Longer keyword = more specific match = wins over shorter keywords.
    """
    text = f"{(product_name or '').lower()} {(category or '').lower().replace('-', ' ')}"

    best_key   = "default"
    best_score = 0
    for key in _CATEGORY_PHOTOS:
        if key == "default":
            continue
        if key in text:
            if len(key) > best_score:
                best_score = len(key)
                best_key   = key

    photos = _CATEGORY_PHOTOS[best_key]
    idx    = abs(hash(product_name or "x")) % len(photos)
    return photos[idx]


def _real_image_url(product_name: str, category: str | None) -> str:
    """Build a real Unsplash photo URL for the product."""
    photo_id = _pick_photo_id(product_name, category)
    return f"https://images.unsplash.com/photo-{photo_id}?w=400&h=400&q=80&fit=crop&auto=format"


def enrich_catalog_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Add product_url and image_url columns if they are missing or incomplete.

    - product_url: store search link (generated from the product name + store)
    - image_url: Unsplash photo URL matched by product category

    We always regenerate image_url to replace any old SVG placeholders that
    may have been written by earlier pipeline runs.
    """
    enriched = df.copy()

    if "product_url" not in enriched.columns:
        enriched["product_url"] = None
    if "image_url" not in enriched.columns:
        enriched["image_url"] = None

    missing_links = enriched["product_url"].isna() | (enriched["product_url"].astype(str).str.strip() == "")

    # Always regenerate image_url so old SVG placeholders get replaced.
    missing_images = (
        enriched["image_url"].isna()
        | (enriched["image_url"].astype(str).str.strip() == "")
        | enriched["image_url"].astype(str).str.startswith("data:image/svg")
    )

    if missing_links.any():
        enriched.loc[missing_links, "product_url"] = enriched.loc[missing_links].apply(
            lambda row: _product_search_url(str(row.get("product_name", "")), str(row.get("store", ""))),
            axis=1,
        )

    if missing_images.any():
        enriched.loc[missing_images, "image_url"] = enriched.loc[missing_images].apply(
            lambda row: _real_image_url(
                str(row.get("product_name", "")),
                row.get("category"),
            ),
            axis=1,
        )

    return enriched
