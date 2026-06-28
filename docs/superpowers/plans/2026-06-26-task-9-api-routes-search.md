# Task 9: API Routes & Search Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement FastAPI application with search endpoint that validates queries, stores search history, calls ScraperAggregator, saves products, and returns results with best price flagging.

**Architecture:** FastAPI app with lifespan context manager for async session management. Single `/api/search` GET endpoint that orchestrates search flow: validate → create Search record → call aggregator → save products → return SearchResult with is_best_price flag. CORS middleware enabled for frontend access.

**Tech Stack:** FastAPI 0.109.0, SQLAlchemy 2.0 (async), Pydantic 2.5.3, asyncpg, aiohttp for HTTP client.

## Global Constraints

- Query validation: minimum 2 characters
- Use existing models.py (Search, Product) and schemas.py (SearchResult, ProductResponse, SearchRequest)
- Use existing ScraperAggregator.search_all() for product search
- Products sorted by price ascending (first product = best price)
- CORS middleware required for frontend access
- Health endpoint at GET /health

---

### Task 1: Update schemas.py for search request validation

**Files:**
- Modify: `backend/schemas.py`

**Interfaces:**
- Consumes: Existing Pydantic BaseModel imports
- Produces: SearchRequest schema with query validation (min 2 chars)

- [ ] **Step 1: Add min_length validation to SearchRequest.query field**

```python
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Search query (min 2 characters)")
    user_id: Optional[str] = None
```

- [ ] **Step 2: Verify schemas.py syntax**

Run: `python -m py_compile backend/schemas.py`
Expected: No output (syntax OK)

- [ ] **Step 3: Commit**

```bash
git add backend/schemas.py
git commit -m "feat: add query validation to SearchRequest schema"
```

---

### Task 2: Create backend/api/routes.py with search endpoint

**Files:**
- Create: `backend/api/routes.py`
- Create: `backend/api/__init__.py`

**Interfaces:**
- Consumes: 
  - `backend.database.get_db()` - async session dependency
  - `backend.models.Search, Product` - SQLAlchemy models
  - `backend.schemas.SearchResult` - response schema
  - `backend.scrapers.ScraperAggregator` - product search
- Produces: 
  - `router` - FastAPI APIRouter instance
  - `GET /api/search` - search endpoint

- [ ] **Step 1: Create backend/api/__init__.py**

```python
"""API module."""
```

- [ ] **Step 2: Create backend/api/routes.py with search endpoint**

```python
"""API routes for product search."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models import Search, Product
from backend.schemas import SearchResult, ProductResponse
from backend.scrapers import ScraperAggregator

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResult)
async def search_products(
    q: str = Query(..., min_length=2, description="Search query (min 2 characters)"),
    user_id: str | None = Query(None, description="Optional user ID"),
    db: AsyncSession = Depends(get_db),
) -> SearchResult:
    """
    Search products across all stores.
    
    - Creates Search record in database
    - Calls ScraperAggregator.search_all() for concurrent multi-store search
    - Saves found products to database
    - Returns SearchResult with is_best_price flag on first product
    """
    # Create Search record
    search = Search(query=q, user_id=user_id)
    db.add(search)
    await db.commit()
    await db.refresh(search)
    
    # Search all stores
    aggregator = ScraperAggregator()
    try:
        products_data = await aggregator.search_all(q)
    finally:
        await aggregator.close()
    
    # Save products to database
    db_products = []
    for idx, pdata in enumerate(products_data):
        product = Product(
            search_id=search.id,
            name=pdata.name,
            price=pdata.price,
            store=pdata.store,
            url=pdata.url,
        )
        db.add(product)
        db_products.append(product)
    
    await db.commit()
    
    # Build response with is_best_price flag
    response_products = []
    for idx, product in enumerate(db_products):
        response_products.append(
            ProductResponse(
                id=product.id,
                search_id=product.search_id,
                name=product.name,
                price=product.price,
                store=product.store,
                url=product.url,
                cached_at=product.cached_at,
                is_best_price=(idx == 0),  # First product = best price
            )
        )
    
    return SearchResult(
        id=search.id,
        query=search.query,
        timestamp=search.timestamp,
        user_id=search.user_id,
        products=response_products,
    )
```

- [ ] **Step 3: Verify routes.py syntax**

Run: `python -m py_compile backend/api/routes.py`
Expected: No output (syntax OK)

- [ ] **Step 4: Commit**

```bash
git add backend/api/__init__.py backend/api/routes.py
git commit -m "feat: create search endpoint with validation and DB storage"
```

---

### Task 3: Create backend/main.py with FastAPI app, CORS, lifespan, health

**Files:**
- Create: `backend/main.py`

**Interfaces:**
- Consumes:
  - `backend.database.init_db` - database initialization
  - `backend.api.routes.router` - API router
- Produces:
  - `app` - FastAPI application instance

- [ ] **Step 1: Create backend/main.py with full application setup**

```python
"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup: initialize database
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Product Search API",
    description="Multi-store product search with price comparison",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
```

- [ ] **Step 2: Verify main.py syntax**

Run: `python -m py_compile backend/main.py`
Expected: No output (syntax OK)

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: create FastAPI app with CORS, lifespan, and health endpoint"
```

---

### Task 4: Create tests/test_api.py with comprehensive test coverage

**Files:**
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes:
  - `fastapi.testclient.TestClient`
  - `backend.main.app`
- Produces: Test functions for health, validation, search endpoint

- [ ] **Step 1: Create tests/test_api.py with health endpoint test**

```python
"""API endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_ok(self):
        """Health endpoint returns status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run health test to verify it passes**

Run: `pytest tests/test_api.py::TestHealthEndpoint::test_health_returns_ok -v`
Expected: PASS

- [ ] **Step 3: Add search validation tests**

```python
class TestSearchValidation:
    """Tests for search query validation."""

    def test_search_rejects_empty_query(self):
        """Empty query returns 422 validation error."""
        response = client.get("/api/search?q=")
        assert response.status_code == 422

    def test_search_rejects_single_char_query(self):
        """Single character query returns 422 validation error."""
        response = client.get("/api/search?q=a")
        assert response.status_code == 422

    def test_search_accepts_two_char_query(self):
        """Two character query is accepted (minimum valid length)."""
        response = client.get("/api/search?q=ab")
        # May return 200 with empty products or error from scrapers
        # but should NOT be 422 validation error
        assert response.status_code != 422
```

- [ ] **Step 4: Run validation tests**

Run: `pytest tests/test_api.py::TestSearchValidation -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Add search endpoint integration test**

```python
class TestSearchEndpoint:
    """Tests for GET /api/search endpoint."""

    def test_search_returns_search_result_structure(self):
        """Search endpoint returns SearchResult structure."""
        response = client.get("/api/search?q=test")
        assert response.status_code == 200
        
        data = response.json()
        assert "id" in data
        assert "query" in data
        assert data["query"] == "test"
        assert "timestamp" in data
        assert "products" in data
        assert isinstance(data["products"], list)

    def test_search_products_have_required_fields(self):
        """Products in search result have required fields."""
        response = client.get("/api/search?q=laptop")
        assert response.status_code == 200
        
        data = response.json()
        for product in data["products"]:
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert "is_best_price" in product

    def test_first_product_has_best_price_flag(self):
        """First product in results has is_best_price=True."""
        response = client.get("/api/search?q=phone")
        assert response.status_code == 200
        
        data = response.json()
        if data["products"]:  # If any products found
            assert data["products"][0]["is_best_price"] is True
            # Verify only first product has flag
            for product in data["products"][1:]:
                assert product["is_best_price"] is False
```

- [ ] **Step 6: Run all API tests**

Run: `pytest tests/test_api.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 7: Commit**

```bash
git add tests/test_api.py
git commit -m "test: add comprehensive API endpoint tests"
```

---

### Task 5: Verify end-to-end functionality

**Files:**
- No file changes

**Interfaces:**
- Uses all components from Tasks 1-4

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/test_api.py -v`
Expected: All 6 tests PASS

- [ ] **Step 2: Verify application starts correctly**

Run: `cd backend && python -m uvicorn main:app --reload --port 8000`
Expected: Server starts without errors

- [ ] **Step 3: Test health endpoint manually**

Run: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 4: Test search endpoint**

Run: `curl "http://localhost:8000/api/search?q=laptop"`
Expected: SearchResult JSON with products array

- [ ] **Step 5: Commit final verification**

```bash
git add .
git commit -m "chore: verify Task 9 API routes end-to-end"
```

---

## Summary

**Files Created:**
- `backend/api/__init__.py` - API module init
- `backend/api/routes.py` - Search endpoint implementation
- `backend/main.py` - FastAPI application entry point
- `tests/test_api.py` - Comprehensive API tests

**Files Modified:**
- `backend/schemas.py` - Added query validation (min_length=2)

**Endpoints:**
- `GET /health` - Health check
- `GET /api/search?q={query}` - Product search with validation, DB storage, best price flagging

**Test Coverage:**
- Health endpoint returns ok
- Query validation (empty, single char, minimum valid)
- SearchResult structure validation
- Product field validation
- is_best_price flag correctness
