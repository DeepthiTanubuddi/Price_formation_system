import { useEffect, useMemo, useState, useCallback } from 'react'
import './index.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const UNITS = ['kg', 'lb', 'oz', 'g', 'L', 'mL', 'unit', 'pack', 'dozen']
const STORES = ['Aldi', 'Walmart', 'Target', 'Costco', 'Whole Foods', 'Kroger']
const PAGE_SIZE = 6  // how many results to show before the "show more" button

const STORE_META = {
  walmart: { color: '#0071CE', label: 'Walmart' },
  target: { color: '#CC0000', label: 'Target' },
  costco: { color: '#005DAA', label: 'Costco' },
  aldi: { color: '#00539B', label: 'Aldi' },
  wholefoods: { color: '#00674B', label: 'Whole Foods' },
  'whole foods': { color: '#00674B', label: 'Whole Foods' },
  kroger: { color: '#2C6BAC', label: 'Kroger' },
}

const TESTIMONIALS = [
  {
    quote: 'This feels much closer to a real shopping platform because the flow is clear and the store comparison is easy to read.',
    name: 'Priya S.',
    role: 'Graduate Student',
  },
  {
    quote: 'The top cart review panel is exactly where I expect it, and the product cards are much easier to scan now.',
    name: 'Daniel M.',
    role: 'Budget Shopper',
  },
]

const fmt = (n) =>
  n != null
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
    : 'N/A'

const fmtUnit = (price, unit) => {
  if (price == null || unit == null) return 'N/A'
  const p = parseFloat(price)
  if (Number.isNaN(p)) return 'N/A'
  return `${fmt(p)}/${unit}`
}

const fmtQty = (qty, unit) => {
  if (qty == null) return ''
  const q = parseFloat(qty)
  if (Number.isNaN(q)) return `${qty} ${unit || ''}`.trim()
  if (unit === 'g') return q >= 1000 ? `${(q / 1000).toFixed(2)} kg` : `${Math.round(q)} g`
  if (unit === 'ml') return q >= 1000 ? `${(q / 1000).toFixed(2)} L` : `${Math.round(q)} ml`
  return `${q % 1 === 0 ? q : q.toFixed(2)} ${unit || ''}`.trim()
}

function getStoreKey(store = '') {
  return store.toLowerCase().replace(/\s+/g, '')
}

function getStoreMeta(store = '') {
  return STORE_META[store.toLowerCase()] || STORE_META[getStoreKey(store)] || { color: '#4B5563', label: store || 'Store' }
}

function productKey(product) {
  return `${product.store}::${product.product_name}`
}

// Product image helpers
// We try to use real Unsplash photos matched to the product category.
// If that fails, we fall back to an emoji.

const UNSPLASH_PHOTOS = {
  milk:       ['1550583724-aa135596b44c', '1634141510639-ef91ae93c1a1', '1563636619-e9143da7f009'],
  yogurt:     ['1488477181676-78af0afbbb78', '1505252585461-04db1eb84625'],
  cheese:     ['1486297678162-eb2a19b0a32d', '1452195100486-9cc805987862'],
  butter:     ['1558642452-9d2a7deb7f62', '1608897013039-887f21d8c804'],
  egg:        ['1518492104633-130d0cc84637', '1569288052389-7e8d4a4e3f66'],
  bread:      ['1509440159596-0249088772ff', '1549931319-a545dcf3bc7c'],
  bagel:      ['1617197163168-8a39a8021847'],
  rice:       ['1536304929831-ee1ca9d44906', '1559963110-71b394e7494d'],
  pasta:      ['1551183053-bf91798d792b', '1598511726153-9f6d6e57e4e0'],
  flour:      ['1574484284002-952d92456975'],
  sugar:      ['1550583724-aa135596b44c'],
  oat:        ['1517093702195-a4a6b76c1e7e'],
  cereal:     ['1517093702195-a4a6b76c1e7e', '1525351484163-7529414344d8'],
  coffee:     ['1495474472287-4d71bcdd2085', '1506619099913-b099ef8579f1'],
  tea:        ['1556679343-c7306c1976bc', '1544787219-7f47ccb76574'],
  juice:      ['1600271886742-f049cd451bcd', '1543158181-e6f9f6712349'],
  water:      ['1559827291-72ebaa3cf73a'],
  soda:       ['1625772299848-391b6a87d7b3'],
  chicken:    ['1598103442097-8b74394b95c7', '1516714435082-f33db3cf7a46'],
  beef:       ['1607623814075-a51a67e2a01b'],
  fish:       ['1534482421-64566f976cfa', '1519708227418-a2d0260ff470'],
  salmon:     ['1519708227418-a2d0260ff470'],
  shrimp:     ['1559339352-11d035aa65ce'],
  fruit:      ['1490474418585-ba9bad8fd0ea', '1619566636858-adf3ef46400b'],
  apple:      ['1560806887-1e4cd0b6cbd6'],
  banana:     ['1571771894821-ce9b6c11b08e'],
  berry:      ['1464965911861-746a04b4bca6'],
  strawberry: ['1464965911861-746a04b4bca6'],
  orange:     ['1547514701-42782101795e'],
  vegetable:  ['1540420773420-3366772f4999', '1485637701851-4f52bbe5d012'],
  broccoli:   ['1553982378-6c9e59b26174'],
  carrot:     ['1598170845054-1d6de1c1d9e8'],
  tomato:     ['1546094096-0df4bcaaa337'],
  potato:     ['1518977676601-b53f82aba655'],
  spinach:    ['1485637701851-4f52bbe5d012'],
  salad:      ['1512621776951-a57141f2eefd'],
  produce:    ['1490474418585-ba9bad8fd0ea'],
  snack:      ['1563805958-20b8b1e66ac1'],
  chip:       ['1563805958-20b8b1e66ac1'],
  cookie:     ['1499636136210-6f4ee915583e'],
  cake:       ['1578985545062-69928b1d9587'],
  chocolate:  ['1481391319741-f885c0e143b2'],
  candy:      ['1553361371-9b22f78e8b1d'],
  'ice cream':['1551024709-8f23befc548f'],
  frozen:     ['1551024709-8f23befc548f'],
  soup:       ['1547592166-23ac45744acd'],
  sauce:      ['1565299507177-93d0c3c2c7a2'],
  oil:        ['1474979266404-7f5af9a8a7c8'],
  nut:        ['1606923829579-4e1b62e72b9e'],
  seed:       ['1536304929831-ee1ca9d44906'],
  bean:       ['1559963110-71b394e7494d'],
  baby:       ['1519689680058-324335573bb0'],
  protein:    ['1571167451108-9e7f1e4ee253'],
  grain:      ['1536304929831-ee1ca9d44906'],
  drink:      ['1600271886742-f049cd451bcd'],
  smoothie:   ['1505252585461-04db1eb84625'],
  default:    ['1542838132-92c53300491e', '1506368083636-6defb67639cd', '1473093226511-05552bbeb3b3'],
}

function getProductImageUrl(product = {}) {
  // if the server already sent us a real image URL, just use it directly
  if (
    product.image_url &&
    product.image_url.startsWith('http') &&
    !product.image_url.startsWith('data:')
  ) {
    return product.image_url
  }

  const text = `${product.product_name || ''} ${product.category || ''}`.toLowerCase()

  // pick the most specific keyword that matches (longer = more specific)
  let bestKey = 'default'
  let bestLen = 0
  for (const key of Object.keys(UNSPLASH_PHOTOS)) {
    if (key === 'default') continue
    if (text.includes(key) && key.length > bestLen) {
      bestKey = key
      bestLen = key.length
    }
  }

  const photos = UNSPLASH_PHOTOS[bestKey]
  // hash the product name so the same product always gets the same photo
  const name = product.product_name || 'x'
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  const photoId = photos[hash % photos.length]
  return `https://images.unsplash.com/photo-${photoId}?w=400&h=400&q=80&fit=crop&auto=format`
}

function getProductEmoji(product = {}) {
  const text = `${product.product_name || ''} ${product.category || ''}`.toLowerCase()
  if (text.includes('milk') || text.includes('yogurt')) return '🥛'
  if (text.includes('rice') || text.includes('grain') || text.includes('pasta')) return '🌾'
  if (text.includes('egg')) return '🥚'
  if (text.includes('bread') || text.includes('bagel')) return '🍞'
  if (text.includes('coffee')) return '☕'
  if (text.includes('tea')) return '🍵'
  if (text.includes('juice') || text.includes('drink')) return '🧃'
  if (text.includes('cheese')) return '🧀'
  if (text.includes('chicken') || text.includes('meat') || text.includes('beef')) return '🥩'
  if (text.includes('fruit') || text.includes('produce') || text.includes('apple')) return '🍎'
  if (text.includes('vegetable') || text.includes('broccoli')) return '🥦'
  if (text.includes('cookie') || text.includes('snack') || text.includes('chip')) return '🍪'
  if (text.includes('fish') || text.includes('salmon') || text.includes('shrimp')) return '🐟'
  if (text.includes('chocolate') || text.includes('candy')) return '🍫'
  if (text.includes('soup')) return '🍲'
  if (text.includes('salad')) return '🥗'
  if (text.includes('pizza')) return '🍕'
  if (text.includes('butter')) return '🧈'
  return '🛒'
}

// how much more expensive is this product vs the cheapest option?
function pctVsBest(unitPrice, bestUnitPrice) {
  if (!unitPrice || !bestUnitPrice || bestUnitPrice === 0) return null
  const pct = ((unitPrice - bestUnitPrice) / bestUnitPrice) * 100
  return pct > 0 ? Math.round(pct) : null
}

// calculate potential savings between best and worst unit price in the results
function calcSavings(sortedResults) {
  if (sortedResults.length < 2) return null
  const best = sortedResults[0]
  const worst = sortedResults[sortedResults.length - 1]
  if (!best?.unit_price || !worst?.unit_price) return null
  const pct = Math.round(((worst.unit_price - best.unit_price) / worst.unit_price) * 100)
  return pct > 0 ? { pct } : null
}

async function fetchSearch(query, limit = 50) {
  const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  if (!res.ok) throw new Error('Search failed')
  return res.json()
}

async function fetchStoreHighlights(store, limit = 5) {
  const res = await fetch(`${API_BASE}/api/stores/${encodeURIComponent(store)}/highlights?limit=${limit}`)
  if (!res.ok) throw new Error('Store highlights failed')
  return res.json()
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2l1.9 5.6L20 9.5l-4.7 3.4 1.8 5.6-5.1-3.6-5.1 3.6 1.8-5.6L4 9.5l6.1-1.9L12 2Z" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  )
}

function LinkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.1 0l2.8-2.8a5 5 0 0 0-7.1-7.1L11 4" />
      <path d="M14 11a5 5 0 0 0-7.1 0l-2.8 2.8a5 5 0 1 0 7.1 7.1L13 20" />
    </svg>
  )
}

function CartIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="9" cy="20" r="1.5" />
      <circle cx="18" cy="20" r="1.5" />
      <path d="M3 4h2l2.2 10.2a1 1 0 0 0 1 .8h9.8a1 1 0 0 0 1-.8L21 7H7" />
    </svg>
  )
}

function StoreChip({ store, active = false, onClick }) {
  const meta = getStoreMeta(store)
  const content = (
    <>
      <span className="store-chip-dot" style={{ backgroundColor: meta.color }} />
      {meta.label}
    </>
  )

  if (typeof onClick === 'function') {
    return (
      <button type="button" className={`store-chip ${active ? 'active' : ''}`} onClick={() => onClick(store)}>
        {content}
      </button>
    )
  }

  return <span className={`store-chip ${active ? 'active' : ''}`}>{content}</span>
}

function ProductThumb({ product }) {
  const meta = getStoreMeta(product.store)
  const [imgError, setImgError] = useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)
  const imageUrl = getProductImageUrl(product)

  return (
    <div className="product-thumb">
      {/* render the image immediately so it starts loading; only show once ready */}
      <img
        src={imageUrl}
        alt={product.product_name}
        loading="eager"
        crossOrigin="anonymous"
        referrerPolicy="no-referrer-when-downgrade"
        onLoad={() => setImgLoaded(true)}
        onError={() => setImgError(true)}
        className={`product-thumb-img ${imgLoaded && !imgError ? 'visible' : ''}`}
      />

      {/* overlay shows emoji until the real image loads, plus the store badge */}
      <div
        className="product-thumb-overlay"
        style={{
          background: (!imgLoaded || imgError)
            ? `linear-gradient(135deg, ${meta.color}22, #f5f0e8)`
            : `linear-gradient(to top, rgba(0,0,0,0.55) 0%, transparent 55%)`,
        }}
      >
        {(!imgLoaded || imgError) && (
          <span className="product-thumb-emoji">{getProductEmoji(product)}</span>
        )}
        <span className="product-thumb-store" style={{ backgroundColor: meta.color, color: '#fff' }}>
          {meta.label}
        </span>
      </div>
    </div>
  )
}

function TopCartBar({ cartItems, onGoToCart }) {
  return (
    <div className="top-cart-wrap">
      <button className={`cart-chip ${cartItems.length ? 'pulse' : ''}`} onClick={onGoToCart}>
        <CartIcon />
        <span>{cartItems.length} saved</span>
        {cartItems.length > 0 && (
          <span className="cart-chip-badge">{cartItems.length}</span>
        )}
      </button>
    </div>
  )
}

function CartPage({ cartItems, onIncrease, onDecrease, onRemove, onClear, onBack }) {
  const total = cartItems.reduce((sum, item) => sum + item.price * item.cartQty, 0)

  // Group by store
  const byStore = useMemo(() => {
    const map = new Map()
    cartItems.forEach((item) => {
      const key = getStoreKey(item.store)
      if (!map.has(key)) map.set(key, { label: item.store, items: [] })
      map.get(key).items.push(item)
    })
    return Array.from(map.values())
  }, [cartItems])

  const storeTotal = (items) => items.reduce((s, i) => s + i.price * i.cartQty, 0)

  return (
    <div className="cart-page-shell">
      {/* Back nav */}
      <div className="cart-page-nav">
        <button className="secondary-action cart-back-btn" onClick={onBack}>
          ← Back to shopping
        </button>
        {cartItems.length > 0 && (
          <button className="text-action" onClick={onClear}>Clear all</button>
        )}
      </div>

      <div className="cart-page-header">
        <div className="section-eyebrow">Cart Review</div>
        <h2>Your saved products</h2>
        <p style={{ color: 'var(--muted)', marginTop: '0.4rem' }}>
          {cartItems.length === 0
            ? 'Your cart is empty. Go back and add some products!'
            : `${cartItems.length} item${cartItems.length > 1 ? 's' : ''} selected across ${byStore.length} store${byStore.length > 1 ? 's' : ''}.`}
        </p>
      </div>

      {cartItems.length === 0 ? (
        <div className="card-shell empty-inline" style={{ marginTop: '1.5rem' }}>
          No products in your cart yet. Go search for something!
        </div>
      ) : (
        <div className="cart-page-body">
          {/* Per-store sections */}
          <div className="cart-page-items">
            {byStore.map(({ label, items }) => (
              <section key={label} className="card-shell cart-store-section">
                <div className="section-top" style={{ marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
                    <StoreChip store={label} active />
                    <span style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>{items.length} item{items.length > 1 ? 's' : ''}</span>
                  </div>
                  <span style={{ fontWeight: 800 }}>{fmt(storeTotal(items))}</span>
                </div>
                <div className="cart-stack">
                  {items.map((item) => (
                    <article key={productKey(item)} className="cart-row">
                      <ProductThumb product={item} />
                      <div className="cart-copy">
                        <h4>{item.product_name}</h4>
                        <p>{fmt(item.price)} · {fmtUnit(item.unit_price, item.canonical_unit)}</p>
                        <p style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>{fmtQty(item.quantity, item.unit)}</p>
                      </div>
                      <div className="cart-controls">
                        <button className="qty-btn" onClick={() => onDecrease(item)}>-</button>
                        <span>{item.cartQty}</span>
                        <button className="qty-btn" onClick={() => onIncrease(item)}>+</button>
                      </div>
                      <div className="cart-price">{fmt(item.price * item.cartQty)}</div>
                      <button className="text-action" onClick={() => onRemove(item)}>Remove</button>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>

          {/* Summary sidebar */}
          <aside className="cart-page-summary card-shell">
            <div className="section-eyebrow" style={{ marginBottom: '1rem' }}>Order Summary</div>
            <div className="cart-summary-rows">
              {byStore.map(({ label, items }) => (
                <div key={label} className="cart-summary-row">
                  <span>{label} ({items.reduce((s, i) => s + i.cartQty, 0)} items)</span>
                  <strong>{fmt(storeTotal(items))}</strong>
                </div>
              ))}
            </div>
            <div className="cart-total" style={{ marginTop: '1rem' }}>
              <span>Estimated Total</span>
              <strong>{fmt(total)}</strong>
            </div>
            <p style={{ color: 'var(--muted)', fontSize: '0.82rem', marginTop: '0.75rem', lineHeight: 1.6 }}>
              Prices shown are from the last search. Final prices may vary at checkout.
            </p>
            <button className="primary-action" style={{ width: '100%', marginTop: '1rem', justifyContent: 'center' }} onClick={onBack}>
              Continue Shopping
            </button>
          </aside>
        </div>
      )}
    </div>
  )
}

function LandingPage({ onSearch, selectedStore, onSelectStore, spotlightItems, spotlightLoading, spotlightNote }) {
  const [product, setProduct] = useState('')
  const [qty, setQty] = useState('')
  const [unit, setUnit] = useState('kg')

  const handleSearch = () => {
    if (!product.trim()) return
    onSearch(product.trim(), qty, unit)
  }

  return (
    <main className="landing-shell">
      <section className="hero-shell">
        <div className="hero-copy">
          <span className="eyebrow">Production-Ready Grocery Search</span>
          <h1>Shop by value, then explore the stores shoppers care about most.</h1>
          <p>
            Search groceries across major stores, compare the lowest price by store, save products to a cart,
            and click a store on the home page to reveal its top 5 best-selling products.
          </p>

          <div className="hero-search" role="search">
            <div className="search-input-wrap">
              <SearchIcon />
              <input
                type="text"
                placeholder="Search milk, rice, eggs, coffee..."
                value={product}
                onChange={(event) => setProduct(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleSearch()}
                autoFocus
              />
            </div>
            <input
              className="search-qty"
              type="number"
              placeholder="Qty"
              value={qty}
              onChange={(event) => setQty(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && handleSearch()}
              min="0"
              step="any"
            />
            <select className="search-unit" value={unit} onChange={(event) => setUnit(event.target.value)}>
              {UNITS.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <button className="search-btn" onClick={handleSearch}>Search now</button>
          </div>

          <div className="feature-grid">
            <article className="feature-card">
              <h4>Cleaner result ranking</h4>
              <p>See the strongest offers first, with only a few visible initially and a cleaner show-more flow.</p>
            </article>
            <article className="feature-card">
              <h4>Top cart review</h4>
              <p>Your cart lives in the top bar, so it stays available without taking space away from product discovery.</p>
            </article>
            <article className="feature-card">
              <h4>Home-page spotlight</h4>
              <p>Click a store here to explore its top 5 best-selling style products before you even search.</p>
            </article>
          </div>
        </div>

        <aside className="hero-visual">
          <div className="mock-browser">
            <div className="browser-dots">
              <span />
              <span />
              <span />
            </div>
            <div className="mock-card emphasis">
              <div className="mock-badge">
                <SparkIcon />
                Best product flow
              </div>
              <div className="mock-headline">Find the lowest price by store</div>
              <div className="mock-sub">Then open the cart from the top bar whenever you need it.</div>
            </div>
            <div className="mock-card">
              <div className="mock-section-title">Trusted stores</div>
              <div className="mock-list">
                {STORES.slice(0, 4).map((store) => (
                  <div key={store}><span>{store}</span><strong>Active</strong></div>
                ))}
              </div>
            </div>
          </div>
        </aside>
      </section>

      <section className="brand-testimonial-grid">
        <div className="card-shell">
          <div className="section-top">
            <div>
              <div className="section-eyebrow">Store spotlight</div>
              <h3>Click a store to see its top 5 selling products</h3>
            </div>
          </div>

          <div className="store-selector-grid">
            {STORES.map((store) => (
              <StoreChip
                key={store}
                store={store}
                active={selectedStore === store}
                onClick={onSelectStore}
              />
            ))}
          </div>

          {selectedStore ? (
            spotlightLoading ? (
              <div className="empty-inline">Loading top 5 items for {selectedStore}...</div>
            ) : (
              <>
                <p className="spotlight-note">{spotlightNote}</p>
                <div className="spotlight-grid">
                  {spotlightItems.map((product, index) => (
                    <article key={`${product.store}-${product.product_name}-${index}`} className="spotlight-card">
                      <ProductThumb product={product} />
                      <div className="spotlight-copy">
                        <StoreChip store={product.store} active />
                        <h4>{product.product_name}</h4>
                        <div className="spotlight-metrics">
                          <span>{fmt(product.price)}</span>
                          <span>{fmtUnit(product.unit_price, product.canonical_unit)}</span>
                        </div>
                      </div>
                      <a className="secondary-action" href={product.product_url} target="_blank" rel="noreferrer">
                        Open listing
                      </a>
                    </article>
                  ))}
                </div>
              </>
            )
          ) : null}
        </div>

        <div className="card-shell">
          <div className="section-eyebrow">Testimonials</div>
          <h3>Built for shopper confidence</h3>
          <div className="testimonial-stack">
            {TESTIMONIALS.map((item) => (
              <article key={item.name} className="testimonial-card">
                <p>"{item.quote}"</p>
                <strong>{item.name}</strong>
                <span>{item.role}</span>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}

function FiltersSidebar({ filters, onChange, onReset }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div className="sidebar-heading">Filters</div>
        <label className="field-label">Price range</label>
        <div className="range-grid">
          <input
            type="number"
            placeholder="Min"
            value={filters.minPrice}
            onChange={(event) => onChange('minPrice', event.target.value)}
            min="0"
          />
          <input
            type="number"
            placeholder="Max"
            value={filters.maxPrice}
            onChange={(event) => onChange('maxPrice', event.target.value)}
            min="0"
          />
        </div>
      </div>

      <div className="sidebar-section">
        <label className="field-label">Stores</label>
        <div className="choice-stack">
          {STORES.map((store) => (
            <label key={store} className="choice-item">
              <input
                type="checkbox"
                checked={filters.stores.includes(store)}
                onChange={() => {
                  const next = filters.stores.includes(store)
                    ? filters.stores.filter((item) => item !== store)
                    : [...filters.stores, store]
                  onChange('stores', next)
                }}
              />
              <span>{store}</span>
            </label>
          ))}
        </div>
      </div>

      <button className="secondary-action" onClick={onReset}>Reset filters</button>
    </aside>
  )
}

function BestValueCard({ product, searchQuery, savings, onAddToCart }) {
  if (!product) return null

  return (
    <section className="best-offer-card">
      <div className="best-offer-content">
        <ProductThumb product={product} />
        <div className="best-offer-copy">
          <div className="best-offer-badge">
            <SparkIcon />
            Best value for "{searchQuery}"
          </div>
          <h2>{product.product_name}</h2>
          <div className="best-offer-meta">
            <StoreChip store={product.store} />
            <span>{fmt(product.price)}</span>
            <span>{fmtQty(product.quantity, product.unit)}</span>
            <span>{fmtUnit(product.unit_price, product.canonical_unit)}</span>
          </div>
          <p>
            This result currently gives the strongest unit-value outcome in the visible comparison set.
          </p>
        </div>
        <div className="best-offer-actions">
          {savings ? (
            <div className="savings-chip">
              <strong>{savings.pct}%</strong>
              <span>better than average</span>
            </div>
          ) : null}
          <button className="primary-action add-success" onClick={() => onAddToCart(product)}>
            <CartIcon />
            Added to cart
          </button>
          <a className="secondary-action" href={product.product_url} target="_blank" rel="noreferrer">
            Open product
          </a>
        </div>
      </div>
    </section>
  )
}

function ProductCard({ product, rank, bestUnitPrice, onAddToCart }) {
  const delta = rank === 1 ? null : pctVsBest(product.unit_price, bestUnitPrice)
  const [addedPulse, setAddedPulse] = useState(false)

  const handleAdd = () => {
    onAddToCart(product)
    setAddedPulse(true)
    // reset the pulse animation after it finishes
    window.setTimeout(() => setAddedPulse(false), 650)
  }

  return (
    <article className={`shopping-card ${addedPulse ? 'added-pulse' : ''}`}>
      <div className="shopping-card-rank">#{rank}</div>
      <ProductThumb product={product} />

      <div className="shopping-card-copy">
        <div className="shopping-card-topline">
          <StoreChip store={product.store} />
          {rank === 1 ? <span className="value-pill best">Best value</span> : null}
          {delta ? <span className="value-pill">+{delta}% vs best</span> : null}
        </div>

        <h3>{product.product_name}</h3>

        <div className="shopping-card-metrics">
          <div>
            <span>Total price</span>
            <strong>{fmt(product.price)}</strong>
          </div>
          <div>
            <span>Package size</span>
            <strong>{fmtQty(product.quantity, product.unit)}</strong>
          </div>
          <div>
            <span>Unit price</span>
            <strong>{fmtUnit(product.unit_price, product.canonical_unit)}</strong>
          </div>
        </div>
      </div>

      <div className="shopping-card-actions">
        <button className={`primary-action ${addedPulse ? 'add-success' : ''}`} onClick={handleAdd}>
          <CartIcon />
          {addedPulse ? 'Added' : 'Add to cart'}
        </button>
        <a className="secondary-action" href={product.product_url} target="_blank" rel="noreferrer">
          <LinkIcon />
          Visit store
        </a>
      </div>
    </article>
  )
}

function PriceComparisonTable({ results }) {
  // Find the best (lowest) unit price across all results
  const lowestByStore = useMemo(() => {
    const map = new Map()
    results.forEach((item) => {
      const key = getStoreKey(item.store)
      const existing = map.get(key)
      if (!existing || (item.unit_price ?? Infinity) < (existing.unit_price ?? Infinity)) {
        map.set(key, item)
      }
    })
    return Array.from(map.values()).sort((a, b) => (a.unit_price || Infinity) - (b.unit_price || Infinity))
  }, [results])

  if (!lowestByStore.length) return null

  const bestUnitPrice = lowestByStore[0]?.unit_price

  return (
    <section className="card-shell">
      <div className="section-top">
        <div>
          <div className="section-eyebrow">Price Comparison</div>
          <h3>Price Comparison Table</h3>
        </div>
      </div>

      <div className="price-table-wrap">
        <table className="price-table">
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
            {lowestByStore.map((product, index) => {
              const isLowest = index === 0
              const pct = isLowest
                ? null
                : bestUnitPrice && product.unit_price
                ? Math.round(((product.unit_price - bestUnitPrice) / bestUnitPrice) * 100)
                : null
              return (
                <tr key={`${product.store}-${product.product_name}`} className={isLowest ? 'pt-row-best' : ''}>
                  <td>
                    <div className="pt-store-cell">
                      <span>{product.store}</span>
                      {isLowest && <span className="pt-best-badge">Best</span>}
                    </div>
                  </td>
                  <td className="pt-muted">{fmtQty(product.quantity, product.unit) || '—'}</td>
                  <td>{fmt(product.price)}</td>
                  <td className="pt-unit-price">{fmtUnit(product.unit_price, product.canonical_unit)}</td>
                  <td>
                    {isLowest ? (
                      <span className="pt-value-best">↘ Lowest</span>
                    ) : pct != null ? (
                      <span className="pt-value-higher">↗ +{pct}%</span>
                    ) : (
                      <span className="pt-muted">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ResultsPage({
  searchQuery,
  searchUnit,
  allResults,
  loading,
  onSearch,
  onAddToCart,
}) {
  const [headerProduct, setHeaderProduct] = useState(searchQuery)
  const [headerQty, setHeaderQty] = useState('')
  const [headerUnit, setHeaderUnit] = useState(searchUnit || 'kg')
  const [showAll, setShowAll] = useState(false)
  const defaultFilters = { minPrice: '', maxPrice: '', stores: [...STORES] }
  const [filters, setFilters] = useState(defaultFilters)

  useEffect(() => {
    setHeaderProduct(searchQuery)
    setHeaderUnit(searchUnit || 'kg')
    setShowAll(false)
  }, [searchQuery, searchUnit])

  const filteredResults = useMemo(() => {
    return allResults.filter((item) => {
      if (filters.minPrice !== '' && item.price < parseFloat(filters.minPrice)) return false
      if (filters.maxPrice !== '' && item.price > parseFloat(filters.maxPrice)) return false
      return filters.stores.some((store) => getStoreKey(store) === getStoreKey(item.store))
    })
  }, [allResults, filters])

  const sortedResults = useMemo(() => {
    return [...filteredResults].sort((a, b) => (a.unit_price || Infinity) - (b.unit_price || Infinity))
  }, [filteredResults])

  const best = sortedResults[0] || null
  const savings = calcSavings(sortedResults)
  const visibleResults = showAll ? sortedResults : sortedResults.slice(0, PAGE_SIZE)

  const handleSearch = () => {
    if (!headerProduct.trim()) return
    onSearch(headerProduct.trim(), headerQty, headerUnit)
  }

  return (
    <>
      <header className="topbar">
        <div className="brand-mark" onClick={() => onSearch(null)} role="button" tabIndex={0}>
          <div className="brand-mark-icon"><SparkIcon /></div>
          <div>
            <strong>SmartCompare</strong>
            <span>Search and compare</span>
          </div>
        </div>

        <div className="toolbar-search">
          <div className="search-input-wrap">
            <SearchIcon />
            <input
              type="text"
              value={headerProduct}
              placeholder="Search another product"
              onChange={(event) => setHeaderProduct(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && handleSearch()}
            />
          </div>
          <input
            className="search-qty"
            type="number"
            placeholder="Qty"
            value={headerQty}
            onChange={(event) => setHeaderQty(event.target.value)}
            min="0"
          />
          <select className="search-unit" value={headerUnit} onChange={(event) => setHeaderUnit(event.target.value)}>
            {UNITS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
          <button className="search-btn" onClick={handleSearch}>Search</button>
        </div>
      </header>

      <main className="results-layout">
        <FiltersSidebar
          filters={filters}
          onChange={(key, value) => setFilters((previous) => ({ ...previous, [key]: value }))}
          onReset={() => setFilters(defaultFilters)}
        />

        <section className="results-content">
          <section className="card-shell">
            <div className="section-top">
              <div>
                <div className="section-eyebrow">Search results</div>
                <h3>{searchQuery}</h3>
                <p className="spotlight-note">
                  {loading
                    ? 'Searching for the best offers...'
                    : `${sortedResults.length} offers found. Showing ${Math.min(visibleResults.length, sortedResults.length)} first.`}
                </p>
              </div>
            </div>
          </section>

          {loading ? (
            <div className="card-shell empty-inline">Searching for the best deals...</div>
          ) : sortedResults.length === 0 ? (
            <div className="card-shell empty-inline">No products matched these filters. Try a broader search or reset filters.</div>
          ) : (
            <>
              <BestValueCard
                product={best}
                searchQuery={searchQuery}
                savings={savings}
                onAddToCart={onAddToCart}
              />

              <section className="card-shell">
                <div className="section-top">
                  <div>
                    <div className="section-eyebrow">Top products</div>
                    <h3>Focused result list with a cleaner show-more flow</h3>
                  </div>
                </div>

                <div className="shopping-grid">
                  {visibleResults.map((product, index) => (
                    <ProductCard
                      key={`${product.store}-${product.product_name}-${index}`}
                      product={product}
                      rank={index + 1}
                      bestUnitPrice={best?.unit_price}
                      onAddToCart={onAddToCart}
                    />
                  ))}
                </div>

                {sortedResults.length > PAGE_SIZE ? (
                  <div className="more-wrap">
                    <button className="secondary-action" onClick={() => setShowAll((value) => !value)}>
                      {showAll ? 'Show less' : `Show more (${sortedResults.length - PAGE_SIZE})`}
                    </button>
                  </div>
                ) : null}
              </section>

              <PriceComparisonTable results={sortedResults} />
            </>
          )}
        </section>
      </main>
    </>
  )
}

export default function App() {
  const [view, setView] = useState('landing')   // 'landing' | 'results' | 'cart'
  const [prevView, setPrevView] = useState('landing')  // so cart knows where to go back
  const [searchQuery, setSearchQuery] = useState('')
  const [searchUnit, setSearchUnit] = useState('kg')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState(false)
  const [cartItems, setCartItems] = useState([])
  const [homeStore, setHomeStore] = useState('Walmart')
  const [homeSpotlightItems, setHomeSpotlightItems] = useState([])
  const [homeSpotlightLoading, setHomeSpotlightLoading] = useState(false)
  const [homeSpotlightNote, setHomeSpotlightNote] = useState('')

  const goToCart = useCallback(() => {
    setPrevView(view)
    setView('cart')
  }, [view])

  const backFromCart = useCallback(() => {
    setView(prevView)
  }, [prevView])

  const doSearch = useCallback(async (query, qty, unit) => {
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
      setApiError(true)
      setResults(DEMO_DATA)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!homeStore || view !== 'landing') return

    let active = true
    setHomeSpotlightLoading(true)

    fetchStoreHighlights(homeStore, 5)
      .then((payload) => {
        if (!active) return
        setHomeSpotlightItems(payload.data || [])
        setHomeSpotlightNote(payload.note || '')
      })
      .catch(() => {
        if (!active) return
        setHomeSpotlightItems(DEMO_DATA.slice(0, 4))
        setHomeSpotlightNote('Fallback spotlight is being shown because the API could not return store-specific products.')
      })
      .finally(() => {
        if (active) setHomeSpotlightLoading(false)
      })

    return () => { active = false }
  }, [homeStore, view])

  const addToCart = useCallback((product) => {
    setCartItems((previous) => {
      const existing = previous.find((item) => productKey(item) === productKey(product))
      if (existing) {
        return previous.map((item) =>
          productKey(item) === productKey(product) ? { ...item, cartQty: item.cartQty + 1 } : item
        )
      }
      return [...previous, { ...product, cartQty: 1 }]
    })
  }, [])

  const increaseCart = useCallback((product) => {
    setCartItems((previous) =>
      previous.map((item) =>
        productKey(item) === productKey(product) ? { ...item, cartQty: item.cartQty + 1 } : item
      )
    )
  }, [])

  const decreaseCart = useCallback((product) => {
    setCartItems((previous) =>
      previous
        .map((item) =>
          productKey(item) === productKey(product) ? { ...item, cartQty: item.cartQty - 1 } : item
        )
        .filter((item) => item.cartQty > 0)
    )
  }, [])

  const removeCart = useCallback((product) => {
    setCartItems((previous) => previous.filter((item) => productKey(item) !== productKey(product)))
  }, [])

  const clearCart = useCallback(() => setCartItems([]), [])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-mark" onClick={() => setView('landing')} role="button" tabIndex={0}>
          <div className="brand-mark-icon"><SparkIcon /></div>
          <div>
            <strong>SmartCompare</strong>
            <span>Customer-ready shopping flow</span>
          </div>
        </div>

        <div className="toolbar-search-spacer" />

        <TopCartBar
          cartItems={cartItems}
          onGoToCart={goToCart}
        />
      </header>

      {view === 'cart' ? (
        <CartPage
          cartItems={cartItems}
          onIncrease={increaseCart}
          onDecrease={decreaseCart}
          onRemove={removeCart}
          onClear={clearCart}
          onBack={backFromCart}
        />
      ) : view === 'landing' ? (
        <LandingPage
          onSearch={doSearch}
          selectedStore={homeStore}
          onSelectStore={setHomeStore}
          spotlightItems={homeSpotlightItems}
          spotlightLoading={homeSpotlightLoading}
          spotlightNote={homeSpotlightNote}
        />
      ) : (
        <ResultsPage
          searchQuery={searchQuery}
          searchUnit={searchUnit}
          allResults={results}
          loading={loading}
          onSearch={doSearch}
          onAddToCart={addToCart}
        />
      )}

      {apiError ? (
        <div className="demo-banner">
          Demo mode — API unreachable. Showing fallback products.
        </div>
      ) : null}
    </div>
  )
}

const DEMO_DATA = [
  {
    product_name: 'Great Value Whole Milk 1 Gallon',
    store: 'Walmart',
    price: 2.59,
    quantity: 3785,
    unit: 'ml',
    unit_price: 0.68,
    canonical_unit: 'L',
    category: 'milk',
    product_url: 'https://www.walmart.com/search?q=whole%20milk%201%20gallon',
    image_url: null,
  },
  {
    product_name: 'Good Gather Whole Milk 1 Gallon',
    store: 'Target',
    price: 3.19,
    quantity: 3785,
    unit: 'ml',
    unit_price: 0.84,
    canonical_unit: 'L',
    category: 'milk',
    product_url: 'https://www.target.com/s?searchTerm=whole%20milk%201%20gallon',
    image_url: null,
  },
  {
    product_name: 'Kirkland Organic Eggs 24 Count',
    store: 'Costco',
    price: 6.49,
    quantity: 24,
    unit: 'pack',
    unit_price: 0.2704,
    canonical_unit: 'pack',
    category: 'egg',
    product_url: 'https://www.costco.com/CatalogSearch?dept=All&keyword=eggs',
    image_url: null,
  },
  {
    product_name: 'Friendly Farms Whole Milk',
    store: 'Aldi',
    price: 2.89,
    quantity: 3785,
    unit: 'ml',
    unit_price: 0.76,
    canonical_unit: 'L',
    category: 'milk',
    product_url: 'https://new.aldi.us/results?q=whole%20milk',
    image_url: null,
  },
  {
    product_name: 'Simple Truth Organic Coffee Medium Roast',
    store: 'Kroger',
    price: 8.99,
    quantity: 340,
    unit: 'g',
    unit_price: 0.026,
    canonical_unit: '100g',
    category: 'coffee',
    product_url: 'https://www.kroger.com/search?query=coffee&searchType=default_search',
    image_url: null,
  },
  {
    product_name: '365 Organic Brown Rice',
    store: 'Whole Foods',
    price: 3.49,
    quantity: 907,
    unit: 'g',
    unit_price: 0.0038,
    canonical_unit: '100g',
    category: 'rice',
    product_url: 'https://www.wholefoodsmarket.com/products/all-products?text=brown+rice',
    image_url: null,
  },
]
