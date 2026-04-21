# SmartCompare — AI-Powered Grocery Price Comparison

**Course:** CSCE 5200 – Information Retrieval  
**Team:** Group 7  
**Semester:** Spring 2026

---

## What It Does

SmartCompare ingests grocery product data from Target, Walmart, and WholeFoods, normalises package sizes across units (oz → g, fl oz → ml, gallon → ml, etc.), computes fair **unit prices** ($/100g or $/L), and surfaces the cheapest option via a clean React web interface with AI-powered recommendations.

---

## Quick Start — Run Everything with One Command

> **Prerequisites:** Python 3.10+, Node.js 18+

### Step 1 — Install dependencies (once)

```bash
# From the project root: price_formation_system/

# Python backend
pip install -r requirements.txt

# React frontend
cd frontend && npm install && cd ..
```

### Step 2 — Start the full stack

Open **two terminals** from `price_formation_system/`:

**Terminal 1 — Backend API**
```bash
uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend && npm run dev
```

Then open **http://localhost:5173** in your browser. ✅

> The pipeline data (`data/processed/combined.csv`) is already generated.  
> To regenerate it (e.g. after changing source data):
> ```bash
> python run_pipeline.py
> ```

---

## Project Structure

```
price_formation_system/
├── api/
│   └── server.py              ← FastAPI backend (search, unit-price API)
├── data/
│   ├── raw/
│   │   ├── GroceryDB_foods.csv    ← 41,050 real products (Target/Walmart/WholeFoods)
│   │   └── Item_List.csv          ← Cross-store comparison list
│   └── processed/
│       └── combined.csv           ← Preprocessed output (auto-generated)
├── src/
│   ├── price_normalizer.py    ← Unit conversion & unit-price computation
│   ├── data_adapter.py        ← Adapts raw schemas → standard schema
│   ├── ir_retrieval.py        ← BM25 retrieval (Sprint 2)
│   ├── nlp_processor.py       ← Query parsing (Sprint 2)
│   └── recommender.py         ← Price ranking (Sprint 3)
├── frontend/
│   └── src/
│       ├── App.jsx            ← React UI (two-page flow, filters, comparison table)
│       └── index.css          ← Full design system
├── evaluation/
│   └── ground_truth.csv       ← Test queries with expected cheapest stores
├── run_pipeline.py            ← Master data pipeline runner
└── requirements.txt
```

---

## Key Features

| Feature | How It Works |
|---------|-------------|
| **Liquid vs Solid Units** | Milk/juice/oil → `$/L`; Rice/flour/meat → `$/100g` |
| **Smart Search** | Word-boundary matching — "rice" never returns "rice krispies" |
| **Best Value AI Card** | Highlights the cheapest unit-price product with savings % |
| **Filters** | Price range, organic/premium quality, per-store toggle |
| **Top 10 + Show More** | Shows 10 results by default, expandable on demand |
| **Comparison Table** | Side-by-side unit-price table for top 10 matches |

---

## Pipeline Results

| Metric | Value |
|--------|-------|
| Total rows processed | **41,050** |
| Liquid products (ml) | **10,546** |
| Solid products (g) | **30,504** |
| NaN unit prices | **0** (100% success) |
| Ground truth accuracy | **4/4 (100%)** |
| Stores covered | Target, Walmart, WholeFoods |
| Pipeline runtime | ~3–4 seconds |

---

## Data Sources

| File | Source | Size |
|------|--------|------|
| `GroceryDB_foods.csv` | Mozafari et al., 2022 – [GroceryDB](https://www.nature.com/articles/s41538-022-00164-0) | 41,050 products |
| `Item_List.csv` | Internal cross-store spreadsheet | 29 categories × 4 stores |

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/search?q=milk&limit=30` | Word-boundary product search |
| `GET` | `/api/products?page=1&limit=50` | Paginated product list |
| `GET` | `/api/stores` | Store aggregate stats |
| `POST` | `/api/reload` | Reload CSV data from disk |

Interactive docs: **http://127.0.0.1:8000/docs**

---

## References

1. Mozafari, M. et al. (2022). GroceryDB. *npj Science of Food*, 6(1). https://doi.org/10.1038/s41538-022-00164-0  
2. Robertson, S. & Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond.  
3. Reimers, N. & Gurevych, I. (2019). Sentence-BERT. *EMNLP 2019*.  
4. NIST SP 811 – Guide for the Use of the International System of Units.

---

*CSCE 5200 – University of North Texas, Spring 2026.*
