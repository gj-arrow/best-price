# Price Comparison Project (Belarus)

## Stack

- **Backend:** FastAPI async + SQLAlchemy 2.0 async (asyncpg) + PostgreSQL
- **Frontend:** Next.js 14 App Router, Tailwind CSS 3, framer-motion 11, TypeScript
- **Python:** 3.14.0 (macOS), Playwright 1.60.0 (chromium 1223), curl_cffi 0.15.0
- **Currency:** All prices in BYN (Belarusian rubles)

## Local Dev Commands

```sh
# Backend (from /backend/)
SSL_CERT_FILE=$(python3 -m certifi) uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend (from /frontend/)
npm run dev

# PostgreSQL
brew services run postgresql@15
```

Test search: `curl -s "http://localhost:8000/api/search?q=Xiaomi+TV" | python3 -m json.tool`

## SSL Cert Workaround (Python 3.14 macOS)

All external HTTP (aiohttp, curl_cffi, urllib, undetected-chromedriver) requires `SSL_CERT_FILE` from `certifi`. Set via env var or `os.environ.setdefault()`. Without it: `[SSL: CERTIFICATE_VERIFY_FAILED]`.

## Scraper Architecture

Entrypoint: `/backend/api/routes.py` → `ScraperAggregator.search_all()` → `asyncio.gather(return_exceptions=True)` on all 6 scrapers concurrently. Results sorted by price ascending, limited to 30.

### Relevance Filter (`aggregator._is_relevant`)

Model-token based, NOT "all query words required" (old rule dropped WB real products because sellers omit the brand):
- **strong model IDs** = query tokens with BOTH letters and digits (e.g. `af-ze7226-a`, `a55pro`) → ALL must be in product name, plus ≥1 word token (blocks "Чехол для AF-ZE7226-A").
- **weak model tokens** = digits only (e.g. `55`) → all required + ≥1 word token.
- **word tokens** = no digits (brand/category). ≥1 must appear.
- This drops Ozon homepage junk (lacks the model ID) while keeping WB's "Аэрогриль Air Fry AF-ZE7226-A" (no "Roome" but has the strong ID).

### Accessory De-prioritization (`aggregator._is_accessory`)

Per store, the cheapest RELEVANT match isn't always the device — a case/charger/spare part is cheaper and shares the model tokens. `search_all` dedups keeping, per store, the cheapest NON-ACCESSORY match (falling back to accessories only if a store lists nothing else). Sort key per product: `(is_accessory, price)`.

`_is_accessory` flags a name if it starts with `для`/`for`, OR if any of the first 3 tokens (split on whitespace + hyphens) is in `_ACCESSORY_WORDS`: чехол, пленка, защитн*, стекло, кабель, заряд*, адаптер, переходник, пульт, картридж, фильтр, бампер, стикер, наклейка, сумка, ремешок, браслет, кольцо, брелок, аккумулятор, экран, дисплей, матрица, модуль, шлейф, разъем, динамик, камера, кнопка, плата, блок, совместим, замена, ремонт, oem, подставка, держатель. Caught: "Чехол для Xiaomi Redmi Note 12", "Аккумулятор ... совместим с Xiaomi", "6.67-дюймовый OEM-экран для Redmi Note 12", "Для Xiaomi ... ЖК-экран". Residual edge: parts named as bare model codes (e.g. WB "Note 12 4G для Xiaomi Redmi Note 12 4G 22111317I") slip through — no accessory word in first 3 tokens.

### Scrapers

| Store | Method | Status | Gotchas |
|-------|--------|--------|---------|
| **Onliner.by** | aiohttp + BeautifulSoup (SSR) | ✅ | BEM classes: `catalog-form__offers-unit_primary`, `catalog-form__description_huge-additional`. **Price element holds TWO numbers**: `от239,00 ƃ289,00 ƃ` (min offer + reference). `_extract_price` splits on `ƃ`, takes first segment's first number via regex. Old code concatenated both → `float()` failed → price 0 → aggregator `price>0` filter dropped product (looked like "not found"). |
| **Wildberries** | curl_cffi `impersonate="chrome124"` | ✅ | Internal API `search.wb.ru/exactmatch/ru/common/v9/search`. Price in `sizes[0]["price"]["product"]` (kopecks RUB). Convert: `/ 100 * 0.0388`. **Import curl_cffi at MODULE level** — Python 3.14 can't see thread imports. **429 rate-limit** under burst traffic — `_search_sync` retries up to 3× with 2s/4s backoff. WB product names often omit the brand (e.g. "Аэрогриль Air Fry AF-ZE7226-A" — no "Roome"), so the aggregator's relevance filter must NOT require all query words. |
| **Ozon** | undetected-chromedriver `headless=True` | ✅ | Playwright blocked by Variti anti-bot. **Must match Chrome version**: `version_main=149`. `version_main` MUST match `Google Chrome --version`. Selenium runs in `ThreadPoolExecutor(max_workers=1)` wrapped in `asyncio.Lock`. Browser singleton reused across searches. CSS classes are hashed — extract from `[data-index]` tiles. Each tile has 2-3 identical links — code picks longest text to skip badge links. **Variti sometimes serves homepage instead of /search/** — page still has `[data-index]` tiles (recommendation carousels) so the wait passes and junk gets parsed. `_search_sync` retries 5×: (a) on a fresh browser loads the homepage first (human-like warmup, tracked via `_warmed_up`), (b) checks `"/search/" in current_url`, (c) after parsing checks `_results_match_query` — at least one tile name must contain the query's STRONG model token (alphanumeric ID; recommendation junk never has it). On either failure closes + recreates the browser (fresh fingerprint) and retries. Query is URL-encoded with `quote_plus`. Reliability ~4/5 searches; Variti fully blocks ~1 in 5 sessions across all retries. |
| **360shop.by** | aiohttp + BeautifulSoup (Bitrix) | ✅ | `div.catalog_item.main_item_wrapper` |
| **1k.by** | aiohttp + BeautifulSoup (SSR) | ✅ | Price aggregator (like Onliner). URL: `https://1k.by/products/search?s_keywords=...` (NOT search?q=). Selectors: `a.prod__link` = name + URL (absolute); `div.prod__price` = range `"239,00 – 379,00б.р.Сравнить все цены"` — take FIRST number (min offer), BYN (`б.р.` = белорусских рублей). `_find_price` walks up from the name link to the card ancestor holding the price div. |
| **Shop.by** | aiohttp + BeautifulSoup (SSR) | ✅ | Price aggregator (like Onliner/1k.by). Search endpoint is `https://shop.by/find/?findtext=...` (GET) — discovered from the homepage `<form action="/find/" method="get">` with `<input name="findtext">`. **NOT `/search/?q=`** — that endpoint doesn't exist on Shop.by and redirects to the homepage (earlier "JS SPA, unsolvable" conclusion came from probing the wrong URL). Page is fully server-side rendered. Selectors: `div.ModelList__ModelBlockItem` = card; `a.ModelList__LinkModel` = name + relative URL (prepend `https://shop.by`; each card has 2 elements with this class — a `<span>` image wrapper and the real `<a>`, select the anchor); `span.PriceBlock__PriceValue` = min price `"1 499,00 p."` (space = thousands, comma = decimal, BYN). |

### Browser Singletons

- **Playwright:** Module-level globals in `base.py` (`_browser`, `_browser_playwright`), refcounted via `_get_browser()`/`_release_browser()`. Used by `BrowserScraper` base class.
- **undetected-chromedriver:** Module-level `_browser` in `ozon.py`. Created once, reused across searches. Runs in `ThreadPoolExecutor` background thread.

## Backend Files

| Path | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app, CORS (localhost:3000), lifespan DB init |
| `backend/api/routes.py` | GET `/api/search?q=` — runs scrapers, persists to DB |
| `backend/scrapers/base.py` | `IScraper` ABC, `ProductData` dataclass, shared `_fetch`/`_parse_html`, Playwright singleton |
| `backend/scrapers/aggregator.py` | Concurrent `asyncio.gather` across 6 scrapers |
| `backend/scrapers/{store}.py` | Per-store scraper |

## Frontend Key Files

| Path | Purpose |
|------|---------|
| `frontend/app/page.tsx` | Landing page with search + category pills |
| `frontend/app/results/page.tsx` | Search results grid with sort/filter |
| `frontend/components/ProductCard.tsx` | Product card with price highlight |
| `frontend/components/Skeleton.tsx` | Loading skeleton |
| `frontend/app/layout.tsx` | Root layout, viewport metadata (must be **separate** `const viewport`, not inside `metadata`) |

## UI Gotchas

- Border colors: set via `* { border-color: #e2e8f0 }` in globals.css `@layer base`, NOT via Tailwind `@apply border-border` (undefined CSS variable).
- Tailwind requires `postcss.config.js` with `tailwindcss` + `autoprefixer` plugins.
- Body background: Tailwind class on `<body>` in layout.tsx, not CSS variables.

## Docker

- 4 services: db (PostgreSQL 15), backend (FastAPI), frontend (Next.js), scraper.
- Launched via `docker-compose up --build` from root.
- Corporate SSL: Dockerfile configures `pip --trusted-host`, npm `strict-ssl false`.

## Known Issues

- **Shop.by**: works via `https://shop.by/find/?findtext=...` (SSR). Earlier "JS SPA, unsolvable" was wrong — came from probing `/search/?q=` (non-existent endpoint → homepage redirect). Real endpoint discovered from homepage search form.
- **Ozon headless Chrome**: `version_main` must match `Google Chrome --version`. Breakage expected on Chrome update. `undetected-chromedriver` patches ChromeDriver — may need reinstall.
- **RUB→BYN rate**: Hardcoded at 0.0388 in `wildberries.py`. Stale rate will misprice WB products.
- **Ozon tile selector**: `[data-index]` matches product tiles. Each tile has 2-3 identical links — code picks longest text to skip badge links.
- **Backend restart**: Must kill old uvicorn process before starting new one (port conflict).
