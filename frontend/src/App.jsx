import { useState, useEffect, useCallback } from 'react'
import './index.css'

// ─── Constants ───────────────────────────────────────────────────────────────
const API_BASE = 'http://127.0.0.1:8000'

const UNITS = ['kg', 'lb', 'oz', 'g', 'L', 'mL', 'unit', 'pack', 'dozen']

const STORES = ['Aldi', 'Walmart', 'Target', 'Costco', 'Whole Foods', 'Kroger']

const QUALITY_OPTIONS = ['Any', 'Standard', 'Premium', 'Organic']

const STORE_DOT_CLASS = {
  walmart:       'dot-walmart',
  target:        'dot-target',
  costco:        'dot-costco',
  aldi:          'dot-aldi',
  'whole foods': 'dot-wholefoods',
  wholefoods:    'dot-wholefoods',
  kroger:        'dot-kroger',
}

const STORE_ICONS = {
  walmart:       '🔵',
  target:        '🎯',
  costco:        '🏪',
  aldi:          '🟦',
  'whole foods': '🌿',
  wholefoods:    '🌿',
  kroger:        '🛒',
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n) =>
  n != null
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
    : 'N/A'

/**
 * Format unit price with human-readable denominator.
 * Server already converts: $/g → $/100g, $/ml → $/L
 */
const fmtUnit = (price, unit) => {
  if (price == null || unit == null) return 'N/A'
  const p = parseFloat(price)
  if (isNaN(p)) return 'N/A'
  return `${fmt(p)}/${unit}`
}

/**
 * Format raw quantity+unit into a human-readable string.
 * Converts large gram values → kg, large ml values → L.
 * e.g. 4535.92 g → "4.54 kg", 3840 ml → "3.84 L", 340 g → "340 g"
 */
const fmtQty = (qty, unit) => {
  if (qty == null) return ''
  const q = parseFloat(qty)
  if (isNaN(q)) return `${qty} ${unit}`

  if (unit === 'g') {
    if (q >= 1000) return `${(q / 1000).toFixed(2)} kg`
    return `${Math.round(q)} g`
  }
  if (unit === 'ml') {
    if (q >= 1000) return `${(q / 1000).toFixed(2)} L`
    return `${Math.round(q)} ml`
  }
  // Already sensible units (kg, L, oz, lb, pack, etc.)
  return `${q % 1 === 0 ? q : q.toFixed(2)} ${unit}`
}

function getStoreKey(store = '') {
  return store.toLowerCase().replace(/\s+/g, '')
}

function getStoreDotClass(store = '') {
  const key = store.toLowerCase()
  return STORE_DOT_CLASS[key] || STORE_DOT_CLASS[getStoreKey(store)] || 'dot-default'
}

function getStoreIcon(store = '') {
  const key = store.toLowerCase()
  return STORE_ICONS[key] || STORE_ICONS[getStoreKey(store)] || '🏬'
}

function getProductEmoji(name = '', category = '') {
  const lower = name.toLowerCase()
  const cat   = (category || '').toLowerCase()

  // Category-based
  if (cat.includes('milk')) return '🥛'
  if (cat.includes('juice') || cat.includes('drink')) return '🧃'
  if (cat.includes('egg')) return '🥚'
  if (cat.includes('meat') || cat.includes('poultry')) return '🥩'
  if (cat.includes('seafood')) return '🐟'
  if (cat.includes('produce')) return '🥦'
  if (cat.includes('bread') || cat.includes('bagel') || cat.includes('muffin')) return '🍞'
  if (cat.includes('rice') || cat.includes('grain') || cat.includes('pasta')) return '🌾'
  if (cat.includes('snack') || cat.includes('chip')) return '🍿'
  if (cat.includes('coffee')) return '☕'
  if (cat.includes('tea')) return '🍵'
  if (cat.includes('cheese')) return '🧀'
  if (cat.includes('ice-cream') || cat.includes('frozen')) return '🍦'
  if (cat.includes('baby')) return '👶'
  if (cat.includes('sauce') || cat.includes('condiment')) return '🍅'
  if (cat.includes('soup') || cat.includes('stew')) return '🍲'
  if (cat.includes('spice') || cat.includes('season')) return '🧂'
  if (cat.includes('baking')) return '🧁'
  if (cat.includes('chocolate') || cat.includes('candy')) return '🍫'
  if (cat.includes('spread')) return '🧈'

  // Name-based fallback
  const nameMap = {
    rice: '🌾', milk: '🥛', eggs: '🥚', bread: '🍞', meat: '🥩',
    chicken: '🍗', fish: '🐟', vegetable: '🥦', fruit: '🍎',
    cheese: '🧀', butter: '🧈', oil: '🫙', sugar: '🍬', salt: '🧂',
    flour: '🌾', pasta: '🍝', cereal: '🥣', coffee: '☕', tea: '🍵',
    juice: '🧃', water: '💧', soda: '🥤', beef: '🥩', pork: '🥓',
    salmon: '🐟', shrimp: '🦐', yogurt: '🥛', cream: '🥛',
    chocolate: '🍫', cookie: '🍪', cake: '🎂', pizza: '🍕',
    soup: '🍲', sauce: '🍅', vinegar: '🫙', mustard: '🟡',
  }
  for (const [key, emoji] of Object.entries(nameMap)) {
    if (lower.includes(key)) return emoji
  }
  return '🛒'
}

function calcSavings(results) {
  if (!results || results.length < 2) return null
  const best = results[0].unit_price
  const avg = results.reduce((s, r) => s + (r.unit_price || 0), 0) / results.length
  if (!best || !avg) return null
  const pct = ((avg - best) / avg * 100).toFixed(1)
  const amt = (avg - best).toFixed(2)
  return { pct, amt }
}

function pctVsBest(unitPrice, bestUnitPrice) {
  if (!unitPrice || !bestUnitPrice) return null
  return ((unitPrice - bestUnitPrice) / bestUnitPrice * 100).toFixed(1)
}

// ─── API ─────────────────────────────────────────────────────────────────────
async function fetchSearch(query, limit = 30) {
  const res = await fetch(
    `${API_BASE}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`
  )
  if (!res.ok) throw new Error('Search failed')
  return res.json()
}

async function fetchProducts(limit = 30) {
  const res = await fetch(`${API_BASE}/api/products?limit=${limit}`)
  if (!res.ok) throw new Error('Fetch failed')
  return res.json()
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function StarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
    </svg>
  )
}

function SearchSVG() {
  return (
    <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
    </svg>
  )
}

function BoltIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
    </svg>
  )
}

// ─── Landing Page ─────────────────────────────────────────────────────────────
function LandingPage({ onSearch }) {
  const [product, setProduct] = useState('')
  const [qty, setQty] = useState('')
  const [unit, setUnit] = useState('kg')

  const handleSearch = () => {
    if (!product.trim()) return
    onSearch(product.trim(), qty, unit)
  }

  const handleKey = (e) => { if (e.key === 'Enter') handleSearch() }

  return (
    <div className="hero">
      <div className="hero-badge">
        <BoltIcon />
        AI-Powered Price Comparison
      </div>

      <h1 className="hero-title">
        Find the Best Deals with Smart Price Comparison
      </h1>

      <p className="hero-subtitle">
        Compare prices across multiple stores instantly. Our AI analyzes product
        similarity, quantity, and unit prices to help you save money on every purchase.
      </p>

      <div className="hero-search" role="search">
        <div className="hero-search-wrap">
          <SearchSVG />
          <input
            id="hero-product-input"
            className="hero-search-input"
            type="text"
            placeholder="Search for a product (e.g., rice, milk, eggs)"
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            onKeyDown={handleKey}
            autoFocus
          />
        </div>

        <div className="hero-divider" />

        <input
          id="hero-qty-input"
          className="hero-qty-input"
          type="number"
          placeholder="Qty"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          onKeyDown={handleKey}
          min="0"
          step="any"
        />

        <select
          id="hero-unit-select"
          className="hero-unit-select"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
        >
          {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
        </select>

        <button id="hero-search-btn" className="hero-search-btn" onClick={handleSearch}>
          Search
        </button>
      </div>

      <div className="feature-grid">
        <div className="feature-card">
          <div className="feature-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
          </div>
          <div className="feature-title">Smart Unit Pricing</div>
          <div className="feature-desc">
            Automatically calculates and compares unit prices across different
            package sizes and formats.
          </div>
        </div>

        <div className="feature-card">
          <div className="feature-icon">
            <StarIcon />
          </div>
          <div className="feature-title">AI Product Matching</div>
          <div className="feature-desc">
            Uses NLP to find similar products across stores, ensuring you compare
            apples to apples.
          </div>
        </div>

        <div className="feature-card">
          <div className="feature-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
              <line x1="3" y1="6" x2="21" y2="6"/>
              <path d="M16 10a4 4 0 0 1-8 0"/>
            </svg>
          </div>
          <div className="feature-title">Multi-Store Coverage</div>
          <div className="feature-desc">
            Compare prices from Walmart, Target, Costco, Aldi, Whole Foods, and
            more in one place.
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Filters Sidebar ──────────────────────────────────────────────────────────
function FiltersSidebar({ filters, onChange, onReset }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-title">Filters</div>

      {/* Price Range */}
      <div className="filter-section">
        <label className="filter-label">Price Range</label>
        <div className="range-inputs">
          <input
            id="filter-min-price"
            type="number"
            className="range-input"
            placeholder="Min"
            value={filters.minPrice}
            onChange={(e) => onChange('minPrice', e.target.value)}
            min="0"
          />
          <input
            id="filter-max-price"
            type="number"
            className="range-input"
            placeholder="Max"
            value={filters.maxPrice}
            onChange={(e) => onChange('maxPrice', e.target.value)}
            min="0"
          />
        </div>
      </div>

      <div className="divider" />

      {/* Quality Preference */}
      <div className="filter-section">
        <label className="filter-label">Quality Preference</label>
        <div className="radio-group">
          {QUALITY_OPTIONS.map((q) => (
            <label key={q} className="radio-label">
              <input
                type="radio"
                name="quality"
                value={q}
                checked={filters.quality === q}
                onChange={() => onChange('quality', q)}
              />
              {q}
            </label>
          ))}
        </div>
      </div>

      <div className="divider" />

      {/* Stores */}
      <div className="filter-section">
        <label className="filter-label">Stores</label>
        <div className="checkbox-group">
          {STORES.map((store) => (
            <label key={store} className="checkbox-label">
              <input
                type="checkbox"
                checked={filters.stores.includes(store)}
                onChange={() => {
                  const next = filters.stores.includes(store)
                    ? filters.stores.filter((s) => s !== store)
                    : [...filters.stores, store]
                  onChange('stores', next)
                }}
              />
              {store}
            </label>
          ))}
        </div>
      </div>

      <div className="divider" />

      <button id="btn-reset-filters" className="btn-reset" onClick={onReset}>
        Reset Filters
      </button>
    </aside>
  )
}

// ─── Best Value Card ──────────────────────────────────────────────────────────
function BestValueCard({ product, searchQuery, savings }) {
  if (!product) return null
  const emoji = getProductEmoji(product.product_name, product.category)
  return (
    <div className="best-value-card">
      <div className="best-value-header">
        <span className="best-value-badge">
          <StarIcon /> Best Value
        </span>
        <span className="best-value-title">AI Recommendation</span>
      </div>

      <div className="best-value-body">
        <div className="best-value-img" aria-label="product image">
          {emoji}
        </div>

        <div className="best-value-info">
          <div className="best-value-store">
            <span className={`store-dot ${getStoreDotClass(product.store)}`} />
            {product.store}
          </div>
          <div className="best-value-product">{product.product_name}</div>
          <div className="best-value-total">
            {fmt(product.price)} &mdash; {fmtQty(product.quantity, product.unit)}
          </div>
          <div className="best-value-unit">
            {fmtUnit(product.unit_price, product.canonical_unit)}
          </div>
        </div>

        {savings && (
          <div className="best-value-savings">
            <div className="savings-label">YOU SAVE VS. AVG</div>
            <div className="savings-amount">
              {savings.pct}%
            </div>
          </div>
        )}
      </div>

      <div className="why-card">
        <span className="why-icon">💡</span>
        <div className="why-text">
          <strong>Why this recommendation?</strong> This product offers the lowest
          unit price for <em>{searchQuery}</em> across all available stores,
          giving you the best value per {product.canonical_unit || 'unit'}.
        </div>
      </div>
    </div>
  )
}

// ─── Product Card ─────────────────────────────────────────────────────────────
function ProductCard({ product, rank }) {
  const emoji = getProductEmoji(product.product_name, product.category)
  return (
    <div className="product-card" tabIndex={0}>
      <div className="product-rank">#{rank}</div>

      <div className="product-img" aria-label="product">
        {emoji}
      </div>

      <div className="product-info">
        <div className="product-store">
          <span className={`store-dot ${getStoreDotClass(product.store)}`} />
          {product.store}
        </div>
        <div className="product-name" title={product.product_name}>
          {product.product_name}
        </div>
        <div className="product-price">
          {fmt(product.price)} for {fmtQty(product.quantity, product.unit)}
        </div>
      </div>

      <div className="product-unit">
        {fmtUnit(product.unit_price, product.canonical_unit)}
      </div>
    </div>
  )
}

// ─── Comparison Table ─────────────────────────────────────────────────────────
function ComparisonTable({ results }) {
  if (!results || results.length === 0) return null
  const best = results[0]

  return (
    <div className="comparison-card">
      <div className="comparison-title">Price Comparison Table</div>
      <div style={{ overflowX: 'auto' }}>
        <table className="comparison-table">
          <thead>
            <tr>
              <th>Store</th>
              <th>Quantity</th>
              <th>Total Price</th>
              <th>Unit Price</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, idx) => {
              const isBest = idx === 0
              const pct = pctVsBest(r.unit_price, best.unit_price)
              return (
                <tr key={`${r.store}-${r.product_name}-${idx}`} className={isBest ? 'best-row' : ''}>
                  <td>
                    <div className="table-store-cell">
                      <span className={`store-dot ${getStoreDotClass(r.store)}`} />
                      {r.store}
                      {isBest && <span className="badge-best">Best</span>}
                    </div>
                  </td>
                  <td>{fmtQty(r.quantity, r.unit)}</td>
                  <td>{fmt(r.price)}</td>
                  <td className="table-unit-price">
                    {fmtUnit(r.unit_price, r.canonical_unit)}
                  </td>
                  <td>
                    {isBest ? (
                      <span className="value-lowest">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
                          strokeLinejoin="round">
                          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                        </svg>
                        Lowest
                      </span>
                    ) : (
                      <span className="value-higher">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
                          strokeLinejoin="round">
                          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
                          <polyline points="17 6 23 6 23 12"/>
                        </svg>
                        +{pct}%
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Results Page ─────────────────────────────────────────────────────────────
const PAGE_SIZE = 10  // initial visible product count

function ResultsPage({ searchQuery, searchUnit, allResults, loading, onSearch }) {
  const [headerProduct, setHeaderProduct] = useState(searchQuery)
  const [headerQty, setHeaderQty] = useState('')
  const [headerUnit, setHeaderUnit] = useState(searchUnit || 'kg')
  const [showAll, setShowAll] = useState(false)

  const defaultFilters = { minPrice: '', maxPrice: '', quality: 'Any', stores: [...STORES] }
  const [filters, setFilters] = useState(defaultFilters)

  // Apply filters
  const filteredResults = allResults.filter((r) => {
    if (filters.minPrice !== '' && r.price < parseFloat(filters.minPrice)) return false
    if (filters.maxPrice !== '' && r.price > parseFloat(filters.maxPrice)) return false
    if (filters.quality !== 'Any') {
      const lower = (r.product_name || '').toLowerCase()
      if (filters.quality === 'Organic' && !lower.includes('organic')) return false
      if (filters.quality === 'Premium' && !lower.includes('premium') && !lower.includes('select') && !lower.includes('choice')) return false
    }
    // Store filter — normalize both sides to remove spaces before comparing
    // Handles 'WholeFoods' (data) vs 'Whole Foods' (filter label)
    const normalizeStore = (s) => (s || '').toLowerCase().replace(/\s+/g, '')
    const dataStore = normalizeStore(r.store)
    const storeMatch = filters.stores.some((s) => normalizeStore(s) === dataStore)
    if (!storeMatch) return false
    return true
  })

  const sortedResults = [...filteredResults].sort(
    (a, b) => (a.unit_price || 9999) - (b.unit_price || 9999)
  )

  const best        = sortedResults[0] || null
  const savings     = calcSavings(sortedResults)
  const visibleResults = showAll ? sortedResults : sortedResults.slice(0, PAGE_SIZE)
  const hasMore     = sortedResults.length > PAGE_SIZE

  const handleFilterChange = useCallback((key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val }))
  }, [])

  const handleReset = useCallback(() => setFilters(defaultFilters), [])

  const handleHeaderSearch = () => {
    if (!headerProduct.trim()) return
    onSearch(headerProduct.trim(), headerQty, headerUnit)
  }

  const handleKey = (e) => { if (e.key === 'Enter') handleHeaderSearch() }

  return (
    <>
      {/* Results page header — search in header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo" onClick={() => onSearch(null)} tabIndex={0} role="button" aria-label="Go to home">
            <div className="logo-icon"><StarIcon /></div>
            <span className="logo-text">SmartCompare</span>
          </div>

          <div className="header-search">
            <div className="header-search-wrap">
              <SearchSVG />
              <input
                id="results-search-input"
                className="header-search-input"
                type="text"
                placeholder="Search for a product (e.g., rice, milk, eggs)"
                value={headerProduct}
                onChange={(e) => setHeaderProduct(e.target.value)}
                onKeyDown={handleKey}
              />
            </div>
            <input
              id="results-qty-input"
              className="header-qty-input"
              type="number"
              placeholder="Qty"
              value={headerQty}
              onChange={(e) => setHeaderQty(e.target.value)}
              onKeyDown={handleKey}
              min="0"
            />
            <select
              id="results-unit-select"
              className="header-unit-select"
              value={headerUnit}
              onChange={(e) => setHeaderUnit(e.target.value)}
            >
              {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
            <button id="results-search-btn" className="btn-search" onClick={handleHeaderSearch}>
              Search
            </button>
          </div>

          <button id="header-signin-btn" className="btn-signin">Sign In</button>
        </div>
      </header>

      {/* Main layout */}
      <div className="results-page">
        {/* Sidebar */}
        <FiltersSidebar
          filters={filters}
          onChange={handleFilterChange}
          onReset={handleReset}
        />

        {/* Results */}
        <main className="results-main">
          <div className="results-header">
            <div>
              <div className="results-title">
                Results for "<span>{searchQuery}</span>"
              </div>
              <div className="results-count">
                {loading
                  ? 'Searching...'
                  : `${sortedResults.length} products found${!showAll && hasMore ? ` — showing top ${PAGE_SIZE}` : ''}`
                }
              </div>
            </div>
          </div>

          {loading ? (
            <div className="loading-state">
              <div className="spinner" />
              <div>Searching for the best deals...</div>
            </div>
          ) : sortedResults.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <div className="empty-state-text">
                No products found matching your filters.<br />
                Try adjusting your filters or searching for something else.
              </div>
            </div>
          ) : (
            <>
              {/* Best Value */}
              <BestValueCard
                product={best}
                searchQuery={searchQuery}
                savings={savings}
              />

              {/* Product list */}
              <div className="products-list">
                {visibleResults.map((r, idx) => (
                  <ProductCard
                    key={`product-${r.store}-${r.product_name}-${idx}`}
                    product={r}
                    rank={idx + 1}
                  />
                ))}
              </div>

              {/* Show More / Show Less */}
              {hasMore && (
                <div className="show-more-wrap">
                  <button
                    className="btn-show-more"
                    onClick={() => setShowAll((v) => !v)}
                  >
                    {showAll
                      ? '▲ Show Less'
                      : `▼ Show More (${sortedResults.length - PAGE_SIZE} more results)`
                    }
                  </button>
                </div>
              )}

              {/* Comparison Table — always top 10 */}
              <ComparisonTable results={sortedResults.slice(0, 10)} />
            </>
          )}
        </main>
      </div>
    </>
  )
}

// ─── App Root ────────────────────────────────────────────────────────────────
export default function App() {
  const [view, setView] = useState('landing') // 'landing' | 'results'
  const [searchQuery, setSearchQuery]   = useState('')
  const [searchUnit, setSearchUnit]     = useState('kg')
  const [results, setResults]           = useState([])
  const [loading, setLoading]           = useState(false)
  const [apiError, setApiError]         = useState(false)

  const doSearch = useCallback(async (query, qty, unit) => {
    // Navigate back home if no query
    if (!query) {
      setView('landing')
      return
    }

    setSearchQuery(query)
    setSearchUnit(unit || 'kg')
    setView('results')
    setLoading(true)
    setResults([])
    setApiError(false)

    try {
      const data = await fetchSearch(query, 50)
      setResults(data.data || [])
    } catch {
      // Try fetching all products as fallback demo data
      try {
        const data = await fetchProducts(50)
        setResults(data.data || [])
        setApiError(true)
      } catch {
        setApiError(true)
        setResults(DEMO_DATA)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <div>
      {view === 'landing' ? (
        <>
          {/* Landing header */}
          <header className="header">
            <div className="header-inner">
              <div className="logo">
                <div className="logo-icon"><StarIcon /></div>
                <span className="logo-text">SmartCompare</span>
              </div>
              <button id="landing-signin-btn" className="btn-signin">Sign In</button>
            </div>
          </header>
          <LandingPage onSearch={doSearch} />
        </>
      ) : (
        <ResultsPage
          searchQuery={searchQuery}
          searchUnit={searchUnit}
          allResults={results}
          loading={loading}
          onSearch={doSearch}
        />
      )}

      {apiError && (
        <div style={{
          position: 'fixed', bottom: '1rem', right: '1rem',
          background: '#FEF3C7', border: '1px solid #FCD34D',
          borderRadius: '0.5rem', padding: '0.75rem 1rem',
          fontSize: '0.8rem', color: '#92400E', maxWidth: '300px',
          boxShadow: '0 4px 6px rgba(0,0,0,.1)', zIndex: 999
        }}>
          ⚠️ <strong>Demo mode:</strong> Backend not found at {API_BASE}. Showing demo data.
          Start the API server with <code>uvicorn server:app --reload</code>.
        </div>
      )}
    </div>
  )
}

// ─── Demo Data (fallback when API is unavailable) ────────────────────────────
const DEMO_DATA = [
  // RICE (solid → g → unit_price in $/100g from server)
  { product_name: 'Kirkland Signature Long Grain White Rice', store: 'Costco', price: 19.99, quantity: 9072, unit: 'g', unit_price: 0.22, canonical_unit: '100g', category: 'rice-grains-packaged' },
  { product_name: 'Great Value Long Grain Enriched Rice 32oz', store: 'Walmart', price: 2.47, quantity: 907, unit: 'g', unit_price: 0.27, canonical_unit: '100g', category: 'rice-grains-packaged' },
  { product_name: 'Market Pantry Jasmine Rice 5lb', store: 'Target', price: 4.49, quantity: 2268, unit: 'g', unit_price: 0.20, canonical_unit: '100g', category: 'rice-grains-packaged' },
  { product_name: '365 Organic Brown Rice 32oz', store: 'Whole Foods', price: 4.99, quantity: 907, unit: 'g', unit_price: 0.55, canonical_unit: '100g', category: 'rice-grains-packaged' },
  { product_name: 'Aldi liveGfree Jasmine Rice 2lb', store: 'Aldi', price: 2.79, quantity: 907, unit: 'g', unit_price: 0.31, canonical_unit: '100g', category: 'rice-grains-packaged' },
  { product_name: 'Private Selection Basmati Rice 2lb', store: 'Kroger', price: 3.99, quantity: 907, unit: 'g', unit_price: 0.44, canonical_unit: '100g', category: 'rice-grains-packaged' },
  // MILK (liquid → ml → unit_price in $/L from server)
  { product_name: 'Great Value Whole Milk 1 Gallon', store: 'Walmart', price: 2.59, quantity: 3785, unit: 'ml', unit_price: 0.68, canonical_unit: 'L', category: 'milk-milk-substitute' },
  { product_name: 'Good Gather Whole Milk 1 Gallon', store: 'Target', price: 3.19, quantity: 3785, unit: 'ml', unit_price: 0.84, canonical_unit: 'L', category: 'milk-milk-substitute' },
  { product_name: 'Organic Valley Whole Milk 64 fl oz', store: 'Whole Foods', price: 5.99, quantity: 1892, unit: 'ml', unit_price: 3.17, canonical_unit: 'L', category: 'milk-milk-substitute' },
]
