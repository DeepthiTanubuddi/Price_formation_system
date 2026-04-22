# SmartCompare

Grocery price comparison app — search across major stores, compare unit prices, and build a cart. Built for CSCE 5200 Group 7.

## What it does

- Search grocery products across Walmart, Target, Aldi, Kroger, Whole Foods, and Costco
- Compare total price and unit price side by side
- Save products to a cart and review them anytime from the top bar
- See how each store compares for a specific product at the bottom of search results
- Click through to the actual store listing for any product

## Stack

- **Frontend**: React + Vite
- **Backend**: FastAPI (Python)
- **Data**: CSV-based processed grocery dataset from GroceryDB

## Project layout

```text
price_formation_system/
|-- api/
|   `-- server.py
|-- data/
|   |-- raw/
|   `-- processed/
|       `-- combined.csv
|-- evaluation/
|   `-- ground_truth.csv
|-- frontend/
|   |-- src/
|   |   |-- App.jsx
|   |   `-- index.css
|   `-- package.json
|-- src/
|   |-- catalog_enrichment.py
|   |-- data_adapter.py
|   |-- ir_retrieval.py
|   |-- nlp_processor.py
|   |-- price_normalizer.py
|   `-- recommender.py
|-- run_pipeline.py
|-- requirements.txt
`-- README.md
```

## Requirements

- Python 3.10+
- Node.js 18+
- PowerShell or any terminal

## How to run it

### 1. Open the project folder

```powershell
cd path\to\price_formation_system
```

### 2. Check Node.js

```powershell
node --version
```

### 3. Check Python

```powershell
python --version
```

### 4. Install backend dependencies

```powershell
pip install -r requirements.txt
```

### 5. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

### 6. (Optional) Rebuild the processed dataset

Only needed if you changed the raw CSVs or want to regenerate `combined.csv` from scratch.

```powershell
python run_pipeline.py
```

### 7. Start the backend

Open a terminal in the project root and run:

```powershell
python -m uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
```

Backend URLs:
- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

### 8. Start the frontend

Open a second terminal and run:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

Frontend:
- App: `http://127.0.0.1:5173`

### 9. Use the app

1. Open `http://127.0.0.1:5173`
2. Search for something like `milk`, `rice`, or `eggs`
3. Compare the results across stores
4. Click `Add to cart` on anything you want to save
5. Open the cart from the top bar to review your selections
6. Scroll down on the results page to see the full store comparison table

### 10. Shut everything down

Press `Ctrl + C` in both terminals.

If you started them as background processes, stop them by PID:

```powershell
Stop-Process -Id <backend_pid>,<frontend_pid>
```

## Troubleshooting

### Python not found

Make sure Python is on your PATH, or use the full path to your Python installation:

```powershell
& 'C:\path\to\python.exe' -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

### Frontend loads but shows no data

Check that the backend is actually running:

```powershell
Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/search?q=milk&limit=3'
```

### Product links go to search pages instead of exact listings

That's expected for now. Links are generated from the product name and store name because
we don't have exact product page URLs. This would need store APIs or web scraping to improve.

## API endpoints

| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/api/search?q=milk&limit=30` | Search products with relevance ranking |
| `GET` | `/api/products?page=1&limit=50` | Paginated list of all products |
| `GET` | `/api/stores` | Summary stats per store |
| `GET` | `/api/stores/{store}/highlights` | Top 5 staple products for a store |
| `POST` | `/api/reload` | Reload the processed CSV from disk |

## Notes

- The frontend includes a cart review section accessible from the top bar.
- The results page has a store comparison table at the bottom showing the cheapest option per store.
- Product images come from Unsplash and are matched deterministically by product category.
