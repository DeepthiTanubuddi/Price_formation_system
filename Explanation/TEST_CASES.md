# SmartCompare — Test Cases Reference
**CSCE 5200 - Group 7**

This document describes all test cases for the SmartCompare Price Formation System.
Each section covers one module, listing the function under test, the input, the expected output or behavior, and what the test validates.

---

## Table of Contents

1. [price_normalizer.py](#1-price_normalizerpy)
2. [data_adapter.py](#2-data_adapterpy)
3. [catalog_enrichment.py](#3-catalog_enrichmentpy)
4. [api/server.py](#4-apiserverpy)
5. [run_pipeline.py — Integration Tests](#5-run_pipelinepy--integration-tests)
6. [evaluation/ground_truth.csv — Accuracy Tests](#6-evaluationground_truthcsv--accuracy-tests)

---

## 1. `price_normalizer.py`

### `normalize_unit(quantity, unit)`

| # | Input | Expected Output | What it validates |
|---|---|---|---|
| TC-NM-01 | `(16, "oz")` | `(453.592, "g")` | Ounces → grams conversion |
| TC-NM-02 | `(1, "lb")` | `(453.592, "g")` | Pounds → grams conversion |
| TC-NM-03 | `(2, "kg")` | `(2000.0, "g")` | Kilograms → grams conversion |
| TC-NM-04 | `(500, "g")` | `(500.0, "g")` | Grams passthrough (no-op) |
| TC-NM-05 | `(64, "fl_oz")` | `(1892.704, "ml")` | Fluid ounces → ml conversion |
| TC-NM-06 | `(1, "L")` | `(1000.0, "ml")` | Liters (uppercase) → ml |
| TC-NM-07 | `(1, "l")` | `(1000.0, "ml")` | Liters (lowercase) → ml |
| TC-NM-08 | `(1, "pt")` | `(473.176, "ml")` | Pints → ml |
| TC-NM-09 | `(1, "qt")` | `(946.353, "ml")` | Quarts → ml |
| TC-NM-10 | `(1, "gal")` | `(3785.41, "ml")` | Gallons → ml |
| TC-NM-11 | `(250, "ml")` | `(250.0, "ml")` | Milliliters passthrough |
| TC-NM-12 | `(6, "pack")` | `(6.0, "pack")` | Discrete unit passthrough |
| TC-NM-13 | `(12, "count")` | `(12.0, "count")` | Count passthrough |
| TC-NM-14 | `(1, "each")` | `(1.0, "each")` | Each passthrough |
| TC-NM-15 | `(1, "ct")` | `(1.0, "ct")` | Short count form passthrough |
| TC-NM-16 | `(1, "UNKNOWN")` | `(1.0, "UNKNOWN")` | Unknown unit — returns original, logs warning |
| TC-NM-17 | `(1, "floz")` | `(29.5735, "ml")` | Alternate fluid oz spelling |
| TC-NM-18 | `(0.5, "kg")` | `(500.0, "g")` | Fractional quantity |

---

### `compute_unit_price(price, quantity, unit)`

| # | Input | Expected Output | What it validates |
|---|---|---|---|
| TC-UP-01 | `(3.49, 16, "oz")` | `≈ 0.007694` | Normal case: price / normalized grams |
| TC-UP-02 | `(1.99, 1, "lb")` | `≈ 0.004389` | Pounds to grams then divide |
| TC-UP-03 | `(2.50, 64, "fl_oz")` | `≈ 0.001322` | Fluid ounces to ml then divide |
| TC-UP-04 | `(4.99, 6, "pack")` | `≈ 0.8317` | Discrete unit (no conversion) |
| TC-UP-05 | `(3.00, 0, "oz")` | `raises ValueError` | Zero quantity must fail |
| TC-UP-06 | `(3.00, -1, "oz")` | `raises ValueError` | Negative quantity must fail |
| TC-UP-07 | `(0.00, 16, "oz")` | `0.0` | Zero price is valid |

---

### `apply_unit_prices(df)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-AUP-01 | DataFrame with all valid rows | All rows get unit_price, normalized_qty, canonical_unit |
| TC-AUP-02 | Row with price = NaN | That row's unit_price = NaN; rest are processed normally |
| TC-AUP-03 | Row with quantity = 0 | That row's unit_price = NaN; exception is caught and logged |
| TC-AUP-04 | Row with unknown unit | unit_price computed using original quantity; warning logged |
| TC-AUP-05 | Empty DataFrame | Returns empty DataFrame with the three new columns added |
| TC-AUP-06 | 100% valid rows | n_ok = len(df), n_bad = 0 |
| TC-AUP-07 | Mix of valid and invalid rows | Only invalid rows become NaN; valid rows unaffected |
| TC-AUP-08 | Input DataFrame not mutated | Original df passed in is unchanged (returns a copy) |

---

### `clean_product_names(df)`

| # | Input `product_name` | Expected Output | What it validates |
|---|---|---|---|
| TC-CN-01 | `"  Whole  Milk!! (1 Gallon)  "` | `"whole milk 1 gallon"` | Lowercase, strip specials, collapse spaces |
| TC-CN-02 | `"EGGS"` | `"eggs"` | Uppercase → lowercase |
| TC-CN-03 | `"whole-grain bread"` | `"whole-grain bread"` | Hyphens are preserved |
| TC-CN-04 | `"café"` | `"caf"` | Non-ASCII characters are stripped |
| TC-CN-05 | `"  rice  "` | `"rice"` | Leading/trailing whitespace stripped |
| TC-CN-06 | `"rice   krispies"` | `"rice krispies"` | Multiple spaces → single space |
| TC-CN-07 | `"Product #5 (2 lb)"` | `"product 5 2 lb"` | Special characters removed |
| TC-CN-08 | Input DataFrame not mutated | Original df unchanged | Returns copy |

---

### `merge_store_datasets(filepaths)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-MSD-01 | Single valid file | Returns that file's rows with source_file column added |
| TC-MSD-02 | Two valid files | Concatenates both; total rows = sum; source_file tracks origin |
| TC-MSD-03 | Empty list `[]` | `raises ValueError` |
| TC-MSD-04 | File missing required column | `raises ValueError` from `load_store_data` |
| TC-MSD-05 | File does not exist | `raises FileNotFoundError` from pandas |
| TC-MSD-06 | Duplicate rows across files | Both rows kept (no dedup at this stage) |

---

### `load_store_data(filepath)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-LSD-01 | Valid CSV with all 6 required columns | Returns DataFrame; price and quantity are numeric |
| TC-LSD-02 | CSV missing one required column | `raises ValueError` listing missing columns |
| TC-LSD-03 | CSV with whitespace in strings | All string columns stripped |
| TC-LSD-04 | CSV with non-numeric price values | Those price cells become NaN (coerced) |
| TC-LSD-05 | File does not exist | `raises FileNotFoundError` |

---

### `build_pipeline(filepaths, output_path)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-BP-01 | One valid store CSV | Runs all 3 steps; writes combined.csv; returns DataFrame |
| TC-BP-02 | Custom `output_path` | CSV is written to the custom path instead of default |
| TC-BP-03 | Empty filepaths list | Fails with ValueError from merge step |
| TC-BP-04 | Output directory doesn't exist | Directory is created automatically |

---

## 2. `data_adapter.py`

### `_is_liquid(category, product_name)`

| # | category | product_name | Expected | What it validates |
|---|---|---|---|---|
| TC-IL-01 | `"beverages"` | `"orange juice"` | `True` | Liquid category |
| TC-IL-02 | `"baking"` | `"all purpose flour"` | `False` | Solid category |
| TC-IL-03 | `"other"` | `"whole milk 1 gallon"` | `True` | Name keyword fallback |
| TC-IL-04 | `"other"` | `"chicken breast"` | `False` | Neither category nor name matches |
| TC-IL-05 | `"snacks"` | `"oat milk"` | `False` | Solid category wins over name keyword |
| TC-IL-06 | `""` | `"olive oil"` | `True` | Name-based detection with no category |
| TC-IL-07 | `"meat"` | `"beef broth"` | `True` | Name keyword broth triggers liquid |

---

### `adapt_grocerydb(filepath, max_rows)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-GDB-01 | Valid GroceryDB CSV | Returns DataFrame with 6 standard columns |
| TC-GDB-02 | Row with `original_ID` prefix `"tg_"` | store = "Target" |
| TC-GDB-03 | Row with `original_ID` prefix `"wf_"` | store = "WholeFoods" |
| TC-GDB-04 | Row with `original_ID` prefix `"wm_"` | store = "Walmart" |
| TC-GDB-05 | Row with unknown prefix | Row is dropped |
| TC-GDB-06 | Row with missing price | Row is dropped |
| TC-GDB-07 | Row with price = 0 | Row is dropped |
| TC-GDB-08 | Row with missing quantity | Row is dropped |
| TC-GDB-09 | Row with quantity = 0 | Row is dropped |
| TC-GDB-10 | Liquid product | unit = "ml" |
| TC-GDB-11 | Solid product | unit = "g" |
| TC-GDB-12 | `max_rows=100` | Output has at most 100 rows |
| TC-GDB-13 | Product name with HTML entity `&#39;` | Replaced with apostrophe |
| TC-GDB-14 | Category in `_CATEGORY_MAP` | Mapped to simplified label |
| TC-GDB-15 | Category not in `_CATEGORY_MAP` | Original category preserved |

---

### `adapt_item_list(filepath)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-ITL-01 | Valid Item_List CSV | Returns rows for Aldi, Kroger, Walmart, Ruler |
| TC-ITL-02 | Row with empty item name for a store | That store's row is skipped |
| TC-ITL-03 | All rows | price = NaN, quantity = NaN, unit = "unit" for all rows |
| TC-ITL-04 | Category with parenthetical note `"Dairy (Fresh)"` | Category becomes `"dairy"` |

---

### `build_adapted_datasets(grocerydb_path, item_list_path, max_grocerydb_rows)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-BAD-01 | Both files present | Returns (gdb_df, itl_df) both non-empty |
| TC-BAD-02 | `item_list_path=None` | Returns (gdb_df, empty DataFrame) |
| TC-BAD-03 | Item_List path points to non-existent file | Returns (gdb_df, empty DataFrame) |
| TC-BAD-04 | `max_grocerydb_rows=500` | gdb_df has at most 500 rows |

---

## 3. `catalog_enrichment.py`

### `_pick_photo_id(product_name, category)`

| # | product_name | category | Expected key used | What it validates |
|---|---|---|---|---|
| TC-PH-01 | `"whole milk"` | `"dairy"` | `"milk"` | Exact keyword match |
| TC-PH-02 | `"strawberry yogurt"` | `"dairy"` | `"strawberry"` | Longer key wins (strawberry > yogurt > dairy) |
| TC-PH-03 | `"mystery item"` | `"other"` | `"default"` | Fallback when no keyword matches |
| TC-PH-04 | Same product name, called twice | Same photo ID | Deterministic (hash-based) |
| TC-PH-05 | `"ice cream bar"` | `"frozen"` | `"ice cream"` | Multi-word keyword match |

---

### `_product_search_url(product_name, store)`

| # | store | Expected URL pattern |
|---|---|---|
| TC-URL-01 | `"Walmart"` | Starts with `https://www.walmart.com/search?q=` |
| TC-URL-02 | `"Target"` | Starts with `https://www.target.com/s?searchTerm=` |
| TC-URL-03 | `"WholeFoods"` | Starts with `https://www.wholefoodsmarket.com` |
| TC-URL-04 | `"Aldi"` | Starts with `https://new.aldi.us/results?q=` |
| TC-URL-05 | `"Kroger"` | Starts with `https://www.kroger.com/search?query=` |
| TC-URL-06 | `"UnknownStore"` | Falls back to Google search URL |
| TC-URL-07 | `"whole milk"` (product with spaces) | Product name is URL-encoded |

---

### `enrich_catalog_metadata(df)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-EM-01 | DataFrame with no product_url | product_url column added and populated |
| TC-EM-02 | DataFrame with no image_url | image_url column added with Unsplash URLs |
| TC-EM-03 | DataFrame with old SVG data URL in image_url | image_url replaced with Unsplash URL |
| TC-EM-04 | DataFrame already has product_url | Existing URL is preserved |
| TC-EM-05 | Input DataFrame not mutated | Returns a copy |
| TC-EM-06 | All Unsplash URLs start with `https://images.unsplash.com` | Format correct |

---

## 4. `api/server.py`

### `display_unit_price(unit_price, canonical_unit)`

| # | unit_price | canonical_unit | Expected Output | What it validates |
|---|---|---|---|---|
| TC-DU-01 | `0.005` | `"g"` | `(0.5, "100g")` | $/g → $/100g scaling |
| TC-DU-02 | `0.001` | `"ml"` | `(1.0, "L")` | $/ml → $/L scaling |
| TC-DU-03 | `0.8333` | `"pack"` | `(0.8333, "pack")` | Passthrough for other units |
| TC-DU-04 | `None` | `"g"` | `(None, "g")` | None input returns unchanged |
| TC-DU-05 | `"bad"` | `"g"` | `("bad", "g")` | Non-numeric returns unchanged |

---

### `_query_domain(query)`

| # | query | Expected domain |
|---|---|---|
| TC-QD-01 | `"milk"` | `"liquid"` |
| TC-QD-02 | `"juice"` | `"liquid"` |
| TC-QD-03 | `"rice"` | `"solid"` |
| TC-QD-04 | `"eggs"` | `"solid"` |
| TC-QD-05 | `"granola"` | `"any"` (unknown) |
| TC-QD-06 | `"MILK"` | `"liquid"` (case insensitive) |

---

### `_is_false_positive(name, query)`

| # | name | query | Expected |
|---|---|---|---|
| TC-FP-01 | `"milk thistle supplement"` | `"milk"` | `True` |
| TC-FP-02 | `"milk chocolate bar"` | `"milk"` | `True` |
| TC-FP-03 | `"whole milk 1 gallon"` | `"milk"` | `False` |
| TC-FP-04 | `"2% milk"` | `"milk"` | `False` |
| TC-FP-05 | `"almond milk"` | `"milk"` | `False` |

---

### `_relevance_score(name, canonical_unit, query, domain)`

| # | name | canonical_unit | query | domain | Expected Score |
|---|---|---|---|---|---|
| TC-RS-01 | `"whole milk"` | `"ml"` | `"milk"` | `"liquid"` | `5` (primary noun + domain match) |
| TC-RS-02 | `"milk chocolate"` | `"g"` | `"milk"` | `"liquid"` | `1` (false positive modifier) |
| TC-RS-03 | `"2% milk reduced fat"` | `"ml"` | `"milk"` | `"liquid"` | `4` (word-boundary + domain match) |
| TC-RS-04 | `"rice flour"` | `"g"` | `"rice"` | `"solid"` | `4` (word-boundary + domain match) |
| TC-RS-05 | `"wild rice mix"` | `"ml"` | `"rice"` | `"solid"` | `2` (domain mismatch — liquid unit for solid query) |
| TC-RS-06 | `"granola bar"` | `"g"` | `"rice"` | `"any"` | `0` (no match at all) |
| TC-RS-07 | `"brown rice"` | `"g"` | `"rice"` | `"solid"` | `5` (primary noun + domain match) |

---

### `smart_search(df, query, limit)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-SS-01 | Query matches product names at word boundary | Returns word-boundary results; no substring-only results |
| TC-SS-02 | Query matches nothing at word boundary | Falls back to substring search |
| TC-SS-03 | Multiple stores carry the same product | Results sorted by relevance then unit_price ASC |
| TC-SS-04 | Products with NaN unit_price exist | NaN-price rows excluded from results |
| TC-SS-05 | `"milk"` query with "milk thistle" in data | "milk thistle" gets score ≤ 1 and filtered out when better results exist |
| TC-SS-06 | `limit=5` with 20 matches | Returns at most 5 results |
| TC-SS-07 | Empty DataFrame | Returns empty DataFrame |
| TC-SS-08 | `"milk"` query — only liquid unit_price rows scored 4-5 | Solid-unit milk rows (if any) get score 2 and are deprioritized |

---

### `_store_highlights(df, store, limit)`

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-SH-01 | Valid store with products | Returns up to `limit` staple-category products |
| TC-SH-02 | Store not in dataset | Returns empty DataFrame |
| TC-SH-03 | Products with no unit_price | Those rows excluded |
| TC-SH-04 | Multiple products with same name | Deduplicated by product_name |
| TC-SH-05 | `limit=3` | Returns at most 3 rows |
| TC-SH-06 | Store name with spaces `"Whole Foods"` | Matched correctly (spaces stripped) |

---

### API Endpoint Tests

| # | Endpoint | Input | Expected Response |
|---|---|---|---|
| TC-API-01 | `GET /api/search?q=milk` | — | `data` list non-empty, `query="milk"` |
| TC-API-02 | `GET /api/search?q=milk&limit=3` | — | `data` list has ≤ 3 items |
| TC-API-03 | `GET /api/search?q=` (empty) | — | HTTP 422 (FastAPI validation) |
| TC-API-04 | `GET /api/products?page=1&limit=10` | — | Returns 10 products sorted by unit price |
| TC-API-05 | `GET /api/products?page=99999` | — | Returns empty `data` list |
| TC-API-06 | `GET /api/stores` | — | List of store objects with `products`, `avg_price` |
| TC-API-07 | `GET /api/stores/Walmart/highlights` | — | Returns ≤ 5 products for Walmart |
| TC-API-08 | `GET /api/stores/UnknownStore/highlights` | — | Returns `data: []` |
| TC-API-09 | `POST /api/reload` | — | `{"status": "reloaded", "rows": N}` |
| TC-API-10 | Unit prices in response for g | canonical_unit = "100g" | Display conversion applied |
| TC-API-11 | Unit prices in response for ml | canonical_unit = "L" | Display conversion applied |

---

## 5. `run_pipeline.py` — Integration Tests

| # | Scenario | Expected Behavior |
|---|---|---|
| TC-INT-01 | GroceryDB present, Item_List present | All 4 steps run; combined.csv written |
| TC-INT-02 | GroceryDB missing | Step 1 prints `[WARN]`; pipeline continues with empty gdb_df |
| TC-INT-03 | Neither source file present | Merge step exits with error (no data to merge) |
| TC-INT-04 | Sample CSV present alongside GroceryDB | Both sources merged into combined.csv |
| TC-INT-05 | `MAX_GROCERYDB_ROWS = 1000` | Pipeline runs faster; output has ≤ 1000 GroceryDB rows |
| TC-INT-06 | `data/processed/` directory does not exist | Directory created automatically |
| TC-INT-07 | Run twice in a row | Second run overwrites combined.csv (no duplicate rows) |

---

## 6. `evaluation/ground_truth.csv` — Accuracy Tests

The ground truth file (`evaluation/ground_truth.csv`) lists expected cheapest stores and expected unit prices for known queries.

| # | product_name | expected_cheapest_store | What it validates |
|---|---|---|---|
| TC-GT-01 | `jasmine rice` | `Walmart` | Walmart is cheapest for jasmine rice by unit price |
| TC-GT-02 | `large eggs` | `Target` | Target is cheapest for large eggs by unit price |
| TC-GT-03 | `lunchables turkey` | `Walmart` | Walmart is cheapest for Lunchables |
| TC-GT-04 | `arizona diet green tea` | `Target` | Target is cheapest for AZ iced tea |

**Evaluation logic:**
- For each ground truth query, the pipeline finds all matching products in `combined.csv`
- It selects the product with the **lowest unit_price**
- It compares the actual store to the expected store
- `[OK]` = match, `[DIFF]` = mismatch, `[MISS]` = no matching products found
- Final accuracy = hits / total ground truth entries

---

*This document covers all testable units across the SmartCompare system as of Sprint 1.*
