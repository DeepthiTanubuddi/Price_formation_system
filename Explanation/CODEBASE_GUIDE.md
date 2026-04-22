# SmartCompare — Codebase Guide
**CSCE 5200 - Group 7**

A complete reference for the SmartCompare Price Formation System — covering architecture, every module, data schema, API, frontend, and how to run everything.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Flow](#2-data-flow)
3. [Project Structure](#3-project-structure)
4. [Backend Modules — `src/`](#4-backend-modules--src)
   - [price_normalizer.py](#41-price_normalizerpy)
   - [data_adapter.py](#42-data_adapterpy)
   - [catalog_enrichment.py](#43-catalog_enrichmentpy)
   - [ir_retrieval.py](#44-ir_retrievalpy)
   - [nlp_processor.py](#45-nlp_processorpy)
   - [recommender.py](#46-recommenderpy)
5. [Pipeline Runner — `run_pipeline.py`](#5-pipeline-runner--run_pipelinepy)
6. [CLI Entry Point — `src/main.py`](#6-cli-entry-point--srcmainpy)
7. [API Server — `api/server.py`](#7-api-server--apiserverpy)
8. [Frontend — `frontend/`](#8-frontend--frontend)
9. [Data Schema](#9-data-schema)
10. [API Reference](#10-api-reference)
11. [Configuration Options](#11-configuration-options)
12. [Utility Scripts](#12-utility-scripts)
13. [How to Run](#13-how-to-run)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. System Overview

SmartCompare is a full-stack grocery price comparison tool. A user types a product name (e.g. "milk"), and the app fetches results from a pre-built CSV dataset, ranks them by relevance and unit price, and displays them across multiple store tabs with a comparison table.

The system has three layers:

| Layer | Technology | Purpose |
|---|---|---|
| **Data pipeline** | Python (pandas) | Ingests raw CSVs, normalizes prices, writes `combined.csv` |
| **API backend** | FastAPI (Python) | Serves search, product list, store stats over HTTP |
| **Frontend** | React + Vite | Renders the UI — search, results, cart, store spotlight |

---

## 2. Data Flow

```
Raw source files
  ├── data/raw/GroceryDB_foods.csv    (Walmart, Target, Whole Foods products)
  ├── data/raw/Item_List.csv          (Aldi, Kroger product names, no prices)
  └── data/raw/sample_grocery.csv    (optional additional products)
         │
         ▼
  src/data_adapter.py
  ├── adapt_grocerydb()   → standard schema (6 columns)
  └── adapt_item_list()   → standard schema (no prices)
         │
         ▼
  src/price_normalizer.py
  ├── clean_product_names()   → lowercase, strip specials
  └── apply_unit_prices()     → compute $/g or $/ml per row
         │
         ▼
  src/catalog_enrichment.py
  └── enrich_catalog_metadata()  → add product_url + image_url
         │
         ▼
  data/processed/combined.csv    ← the final dataset
         │
         ▼
  api/server.py (FastAPI)
  ├── /api/search           → smart_search()
  ├── /api/products         → paginated list
  ├── /api/stores           → store stats
  └── /api/stores/{n}/highlights → top 5 per store
         │
         ▼
  frontend/src/App.jsx (React)
  └── renders search results, comparison table, cart, store spotlight
```

---

## 3. Project Structure

```
price_formation_system/
│
├── api/
│   └── server.py              FastAPI backend — all HTTP endpoints
│
├── data/
│   ├── raw/                   Place source CSVs here before running the pipeline
│   │   ├── GroceryDB_foods.csv
│   │   ├── Item_List.csv
│   │   └── sample_grocery.csv (optional)
│   └── processed/
│       └── combined.csv       Output of the pipeline — what the API reads
│
├── evaluation/
│   └── ground_truth.csv       Known correct answers for accuracy testing
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx            Entire React app (search, results, cart, spotlight)
│   │   ├── index.css          All CSS styles
│   │   └── main.jsx           React entry point
│   ├── package.json
│   └── vite.config.js
│
├── src/
│   ├── __init__.py
│   ├── catalog_enrichment.py  Adds product URLs and Unsplash image URLs
│   ├── data_adapter.py        Converts raw CSVs to standard schema
│   ├── ir_retrieval.py        IR module stub (Sprint 2)
│   ├── main.py                CLI entry point
│   ├── nlp_processor.py       NLP module stub (Sprint 2)
│   ├── price_normalizer.py    Unit conversion and unit price computation
│   └── recommender.py         Recommendation module stub (Sprint 3)
│
├── inspect_csv.py             Quick column + sample row printout
├── run_pipeline.py            Main pipeline runner (adapt → merge → normalize → save)
├── verify.py                  Dataset health check after pipeline run
├── requirements.txt           Python dependencies
├── .gitignore
└── README.md
```

---

## 4. Backend Modules — `src/`

---

### 4.1 `price_normalizer.py`

**Purpose:** The core data cleaning module. Takes raw store CSVs and produces a clean, normalized DataFrame.

**Key constants:**

| Name | Type | Description |
|---|---|---|
| `REQUIRED_COLUMNS` | `list[str]` | The 6 columns every store CSV must have |
| `_WEIGHT_CONVERSIONS` | `dict` | oz, lb, kg, g → grams |
| `_VOLUME_CONVERSIONS` | `dict` | fl_oz, L, pt, qt, gal, ml → milliliters |
| `_PASSTHROUGH_UNITS` | `frozenset` | pack, count, each, ct — no conversion |

**Public functions:**

#### `load_store_data(filepath) → pd.DataFrame`
Loads a single store CSV. Validates that all 6 required columns are present. Coerces `price` and `quantity` to numeric; everything else stays as string. Strips whitespace from all text columns.

#### `normalize_unit(quantity, unit) → (float, str)`
Converts a raw quantity/unit pair to a canonical measurement:
- Weight (oz, lb, kg, g) → grams
- Volume (fl_oz, L, pt, qt, gal, ml) → ml
- Discrete (pack, count, each, ct) → pass through

Returns `(normalized_quantity, canonical_unit)`.

#### `compute_unit_price(price, quantity, unit) → float`
Computes `price / normalize_unit(quantity, unit)[0]`.
Raises `ValueError` if quantity ≤ 0.

#### `apply_unit_prices(df) → pd.DataFrame`
Iterates over all rows, calls `compute_unit_price`, and appends three new columns:
- `unit_price` — price per gram or per ml
- `normalized_qty` — quantity in the canonical unit
- `canonical_unit` — "g", "ml", "pack", etc.

Bad rows get `NaN` and a warning is logged; the rest continue processing normally.

#### `merge_store_datasets(filepaths) → pd.DataFrame`
Loads multiple store CSVs and concatenates them. Adds a `source_file` column so you can trace each row back to its original file.

#### `clean_product_names(df) → pd.DataFrame`
Normalizes the `product_name` column: lowercase → strip special chars (keep hyphens) → strip whitespace → collapse spaces.

#### `build_pipeline(filepaths, output_path) → pd.DataFrame`
Runs the full pipeline in one call:
1. `merge_store_datasets`
2. `clean_product_names`
3. `apply_unit_prices`
4. `enrich_catalog_metadata`
5. Save to `data/processed/combined.csv`

---

### 4.2 `data_adapter.py`

**Purpose:** Converts the two real-world source files (GroceryDB and Item_List) into our standard 6-column schema so `price_normalizer.py` can process them uniformly.

**Key constants:**

| Name | Type | Description |
|---|---|---|
| `_ID_PREFIX_STORE` | `dict` | Maps tg_, wf_, wm_ to Target, WholeFoods, Walmart |
| `_CATEGORY_MAP` | `dict` | GroceryDB categories → simplified labels |
| `_LIQUID_CATEGORIES` | `frozenset` | Category slugs that are definitely liquids |
| `_LIQUID_NAME_KEYWORDS` | `tuple` | Name substrings that imply a liquid |
| `_SOLID_CATEGORIES` | `frozenset` | Category slugs that are definitely solids |

**Why liquid/solid detection matters:**
GroceryDB stores all package weights in grams — even for liquids like milk and juice. For water-based liquids, 1 g ≈ 1 ml, so we relabel the unit as "ml" when the product is a liquid. This makes unit price comparisons between liquids ($/ml) and solids ($/g) meaningful.

**Public functions:**

#### `_is_liquid(category, product_name) → bool`
Decision order: solid category → solid; liquid category → liquid; name keyword → liquid; else → solid.

#### `adapt_grocerydb(filepath, max_rows) → pd.DataFrame`
Reads GroceryDB_foods.csv, maps store prefixes, drops rows with missing/zero prices or quantities, assigns g or ml unit, maps categories, and strips HTML entities from names.

#### `adapt_item_list(filepath) → pd.DataFrame`
Reads Item_List.csv (wide format), pivots to one row per store per product, and sets price/quantity to NaN (no prices in this source).

#### `build_adapted_datasets(grocerydb_path, item_list_path, max_grocerydb_rows) → (pd.DataFrame, pd.DataFrame)`
Calls both adapters and returns them as a tuple. Safe to call with `item_list_path=None`.

---

### 4.3 `catalog_enrichment.py`

**Purpose:** Adds two metadata columns to the dataset so the frontend can show product links and images without any additional API calls.

**What it adds:**

| Column | Example value | How it's generated |
|---|---|---|
| `product_url` | `https://www.walmart.com/search?q=jasmine+rice` | Store search URL template + URL-encoded product name |
| `image_url` | `https://images.unsplash.com/photo-...` | Deterministic Unsplash photo matched by product keyword |

**Image matching logic:**
1. Build a text string from `product_name + category`
2. Find the longest keyword in `_CATEGORY_PHOTOS` that appears in that text
3. Pick a photo from the list using `hash(product_name) % len(photos)` — same product always gets the same photo
4. Fallback to a generic "grocery" photo if no keyword matches

**Public functions:**

#### `enrich_catalog_metadata(df) → pd.DataFrame`
Adds `product_url` and `image_url` if missing. Always regenerates `image_url` to replace old SVG placeholders from earlier pipeline runs. Returns a copy — does not mutate the input.

---

### 4.4 `ir_retrieval.py`

**Status: Stub — Sprint 2**

Planned functionality:
- `build_bm25_index(df)` — BM25 sparse retrieval index using `rank-bm25`
- `dense_retrieve(query, df, top_k)` — dense semantic retrieval using sentence-transformers

Currently both functions raise `NotImplementedError`. The actual search is handled by `smart_search()` in `api/server.py` using regex-based tier scoring.

---

### 4.5 `nlp_processor.py`

**Status: Stub — Sprint 2**

Planned functionality:
- `parse_query(raw_query)` — extract structured fields (product, store, budget, preference) from a natural-language query using spaCy
- `expand_query(tokens)` — add synonyms and related terms using WordNet

---

### 4.6 `recommender.py`

**Status: Stub — Sprint 3**

Planned functionality:
- `rank_by_unit_price(df, product_query, top_k)` — return cheapest matches
- `optimise_basket(shopping_list, df, budget)` — find the optimal multi-store shopping basket

---

## 5. Pipeline Runner — `run_pipeline.py`

**How to run:**
```powershell
python run_pipeline.py
```

**What it does step by step:**

| Step | Function | Description |
|---|---|---|
| 1/4 | `step_adapt()` | Loads GroceryDB + Item_List + sample CSV; saves adapted CSVs |
| 2/4 | `step_merge()` | Concatenates all sources into one DataFrame |
| 3/4 | `step_preprocess()` | Cleans names + computes unit prices |
| 4/4 | `step_save_and_report()` | Saves combined.csv; prints store breakdown, top categories, cheapest items |
| Eval | `step_evaluate()` | Compares results against `evaluation/ground_truth.csv` |

**Configuration:**

```python
# At the top of run_pipeline.py — set to None for full run
MAX_GROCERYDB_ROWS = None    # set to 5000 for a fast test run
```

**Console output example:**
```
====================================================================
  IR & NLP-Based Price Formation System
  CSCE 5200 -- Group 7  |  Full Pipeline Runner
====================================================================

  STEP 1/4 -- Adapting raw datasets to standard schema
  [GroceryDB]  GroceryDB_foods.csv  (24.3 MB)
  [OK] GroceryDB adapted: 351,705 rows
       Stores found     : ['Target', 'WholeFoods', 'Walmart']
  ...
  Pipeline complete in 42.3s
```

---

## 6. CLI Entry Point — `src/main.py`

**How to run:**
```powershell
python -m src.main --preprocess-only
python -m src.main --query "cheapest jasmine rice" --budget 5.00
```

**Arguments:**

| Flag | Type | Description |
|---|---|---|
| `--preprocess-only` | flag | Run the pipeline and exit |
| `--query` | str | Natural-language shopping query |
| `--budget` | float | Max spend in USD |
| `--top-k` | int | Number of results (default: 5) |

**Note:** Full query handling (NLP + IR + recommender) is planned for Sprint 2. Currently, `--query` prints a placeholder message.

---

## 7. API Server — `api/server.py`

**How to start:**
```powershell
python -m uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
```

**Architecture:**

The server loads `combined.csv` once on startup (lazy load on first request) and caches it in memory. All endpoints read from this cache — no database needed.

**Search algorithm — 4-tier relevance scoring:**

Every product in the dataset gets a relevance score for a given query:

| Score | Condition |
|---|---|
| 5 | Query word is the primary noun (first or last word) + domain matches |
| 4 | Word-boundary match + domain matches (or primary noun alone) |
| 3 | Word-boundary match, neutral domain |
| 2 | Word-boundary match but domain mismatch (solid query → liquid product) |
| 1 | Word-boundary match but followed by a modifier that makes it a false positive |
| 0 | Substring-only match (no word boundary) |

Results are sorted by `(score DESC, unit_price ASC)`.

**Domain detection:**
The server detects whether a query is for a liquid or solid product. Liquid queries ("milk", "juice", "oil") score higher against products with `canonical_unit = "ml"`; solid queries ("rice", "flour", "eggs") score higher against `canonical_unit = "g"` products. This prevents milk from returning soup stock and rice from returning rice milk.

**Unit display conversion:**
Before sending data to the frontend, unit prices are scaled for human readability:
- `$/g` → `$/100g` (avoids tiny numbers like `$0.0005`)
- `$/ml` → `$/L`

---

## 8. Frontend — `frontend/`

**How to start:**
```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

**App URL:** `http://127.0.0.1:5173`

**Key components in `App.jsx`:**

| Component | Purpose |
|---|---|
| `LandingPage` | Search bar, feature grid, store spotlight section, testimonials |
| `FiltersSidebar` | Price range + store checkbox filters for search results |
| `ProductCard` | Individual result card with rank badge, store chip, metrics, add-to-cart |
| `BestValueCard` | Highlighted banner for the #1 ranked result |
| `PriceComparisonTable` | Table showing the best price per store for the current query |
| `CartPage` | Full cart review: items grouped by store, quantity controls, order summary |
| `ProductThumb` | Product image (Unsplash) with emoji fallback and store badge |
| `TopCartBar` | Persistent cart button in the top bar |
| `StoreChip` | Colored store label/button used throughout the app |

**State management:**

The app uses React `useState` and `useMemo` — no Redux or external state library:

| State | Description |
|---|---|
| `searchResults` | Products returned from the last search |
| `cartItems` | Products saved to the cart (array, persisted in memory) |
| `filters` | Active price range and store filters |
| `page` | Which page the user is on: "landing", "results", "cart" |
| `selectedStore` | Which store's spotlight is showing on the landing page |

**Search flow:**
1. User types in search bar and presses Enter or clicks "Search now"
2. `fetchSearch(query)` calls `GET /api/search?q=...`
3. Results are stored in `searchResults`
4. Filters (`minPrice`, `maxPrice`, `stores`) are applied client-side using `useMemo`
5. Filtered results are displayed as `ProductCard` components

**Cart flow:**
1. User clicks "Add to cart" on any product card
2. Product is added to `cartItems` array with `cartQty: 1`
3. Clicking again increments quantity; clicking "Remove" removes the item
4. Cart is accessible from `TopCartBar` at the top of every page
5. `CartPage` groups items by store and shows an order summary

**Store spotlight:**
On the landing page, clicking a store chip calls `GET /api/stores/{store}/highlights` and displays the top 5 staple products for that store.

**Image handling:**
1. Check if the product's `image_url` from the API is a real HTTP URL → use it directly
2. If not, fall back to picking a photo from the local `UNSPLASH_PHOTOS` map using the product name/category
3. If the image fails to load, fall back to a category emoji

---

## 9. Data Schema

### `combined.csv` — the processed dataset

| Column | Type | Description |
|---|---|---|
| `product_name` | str | Cleaned, lowercase product name |
| `store` | str | Store name (Walmart, Target, WholeFoods, Aldi, Kroger) |
| `price` | float | Total package price in USD |
| `quantity` | float | Original package quantity (in grams or ml from GroceryDB) |
| `unit` | str | Original unit (g or ml for GroceryDB; unit for Item_List) |
| `category` | str | Simplified category label (dairy, produce, snacks, etc.) |
| `source_file` | str | Which raw CSV this row came from |
| `unit_price` | float | Price per gram ($/g) or per ml ($/ml) or per pack |
| `normalized_qty` | float | Quantity in canonical units (grams or ml) |
| `canonical_unit` | str | The unit of normalized_qty (g, ml, pack, etc.) |
| `product_url` | str | Store search URL for this product |
| `image_url` | str | Unsplash photo URL for the product |

### `evaluation/ground_truth.csv`

| Column | Description |
|---|---|
| `product_name` | Fuzzy-match query string |
| `store` | Store where the product was checked |
| `expected_cheapest_store` | Which store should have the lowest unit price |
| `expected_unit_price_per_g` | Expected unit price ($/g) |

---

## 10. API Reference

Base URL: `http://127.0.0.1:8000`
Interactive docs: `http://127.0.0.1:8000/docs`

---

### `GET /api/search`

Search products with 4-tier relevance ranking.

**Query parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `q` | string | Yes | — | Search query |
| `limit` | int | No | 50 | Max results (1–100) |

**Response:**
```json
{
  "data": [
    {
      "product_name": "whole milk",
      "store": "Walmart",
      "price": 3.48,
      "quantity": 3785.41,
      "unit": "ml",
      "category": "dairy",
      "unit_price": 0.9195,
      "canonical_unit": "L",
      "product_url": "https://www.walmart.com/search?q=whole+milk",
      "image_url": "https://images.unsplash.com/photo-..."
    }
  ],
  "total": 24,
  "query": "milk"
}
```

---

### `GET /api/products`

Paginated list of all products, sorted by unit price ascending.

**Query parameters:**

| Parameter | Type | Default | Range |
|---|---|---|---|
| `page` | int | 1 | ≥ 1 |
| `limit` | int | 50 | 1–500 |

**Response:**
```json
{
  "data": [...],
  "total": 351705,
  "page": 1,
  "limit": 50
}
```

---

### `GET /api/stores`

Aggregate statistics per store.

**Response:**
```json
[
  {
    "store": "Walmart",
    "products": 125432,
    "avg_price": 4.21,
    "avg_unit_p": 0.0047
  },
  ...
]
```

---

### `GET /api/stores/{store_name}/highlights`

Top staple-category products for a specific store.

**Path parameter:** `store_name` — store name string (e.g. "Walmart", "Whole Foods")
**Query parameter:** `limit` (int, default 5, max 10)

**Response:**
```json
{
  "store": "Walmart",
  "data": [...],
  "total": 5,
  "note": "Best-seller picks are inferred from staple-category relevance..."
}
```

---

### `POST /api/reload`

Clears the in-memory data cache and reloads `combined.csv` from disk.
Useful after re-running the pipeline without restarting the server.

**Response:**
```json
{"status": "reloaded", "rows": 351705}
```

---

## 11. Configuration Options

### Pipeline configuration (`run_pipeline.py`)

```python
MAX_GROCERYDB_ROWS = None   # Set to e.g. 5000 for faster test runs
```

### Server configuration

The server reads from a fixed path by default:

```python
DATA_PATH = Path(__file__).parent.parent / "data" / "processed" / "combined.csv"
```

To change the port or host:
```powershell
python -m uvicorn api.server:app --host 0.0.0.0 --port 9000
```

### Frontend API base

In `frontend/src/App.jsx`:
```js
const API_BASE = ''   // empty string = same host as the frontend (proxy)
```

If you need to point to a different backend host, change this to e.g. `"http://127.0.0.1:8000"`.

---

## 12. Utility Scripts

### `verify.py`
Quick health-check after running the pipeline. Prints row counts, store list, category count, NaN unit prices, and a per-store unit price comparison.

```powershell
python verify.py
```

### `inspect_csv.py`
Prints the column list and one sample row from `combined.csv`. Useful for quickly checking the output schema.

```powershell
python inspect_csv.py
```

---

## 13. How to Run

### One-time setup

```powershell
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Run the pipeline (generates combined.csv)

```powershell
python run_pipeline.py
```

Place `GroceryDB_foods.csv` and `Item_List.csv` in `data/raw/` before running.

### Start the backend

```powershell
python -m uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
```

### Start the frontend (second terminal)

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

### Open the app

Navigate to: `http://127.0.0.1:5173`

---

## 14. Troubleshooting

### `combined.csv` not found when starting the server
Run `python run_pipeline.py` first to generate the processed data.

### Frontend shows no results
Check that the backend is running and reachable:
```powershell
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/search?q=milk&limit=3'
```

### Product names look garbled (HTML entities like `&#39;`)
This is cleaned by `_clean_html_entities()` in `data_adapter.py`. If you see it in the output, re-run the pipeline.

### Product images not loading
Images come from Unsplash. If they're blocked, the app falls back to category emojis. No action needed.

### NaN unit_price rows in combined.csv
This is expected for Item_List rows (no prices in source). It's also expected for any GroceryDB row where price or quantity was missing or zero. Check the `verify.py` output for counts.

### Python not found
Use the full path to your Python executable:
```powershell
& 'C:\path\to\python.exe' run_pipeline.py
```

---

*Last updated: Sprint 1 — CSCE 5200 Group 7*
