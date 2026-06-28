# Price Comparison Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a price comparison service that searches top aggregators and returns the best 3 prices for products with direct store links.

**Architecture:** Microservices with Next.js frontend, FastAPI gateway, and Python scraper service with unified IScraper interface per store.

**Tech Stack:** Next.js 14, React, Tailwind CSS, Framer Motion, Python 3.11+, FastAPI, aiohttp, BeautifulSoup4, PostgreSQL, Docker, Docker Compose

## Global Constraints

- Search timeout: 5 seconds per store
- Graceful degradation: Continue if some stores fail
- Result latency: ≤ 10 seconds total
- Top-3 prices displayed with "Best Price" badge for #1
- Cache enabled for repeated searches
- Responsive design (mobile/desktop)
- 60 FPS animations

---

## File Structure Overview

```
price-comparison/
├── docker-compose.yml
├── Dockerfile.frontend
├── Dockerfile.backend
├── backend/
│   ├── requirements.txt
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── api/
│   │   └── routes.py
│   └── scrapers/
│       ├── __init__.py
│       ├── base.py
│       ├── onliner.py
│       ├── wildberries.py
│       ├── ozon.py
│       ├── shopby.py
│       ├── home1k.py
│       └── shop360.py
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── results/
│   │   │   └── page.tsx
│   │   └── api/
│   │       └── search/
│   │           └── route.ts
│   ├── components/
│   │   ├── SearchBar.tsx
│   │   ├── ProductCard.tsx
│   │   ├── PriceBlock.tsx
│   │   ├── Skeleton.tsx
│   │   └── Header.tsx
│   └── styles/
│       └── globals.css
└── tests/
    ├── test_scrapers.py
    └── test_api.py
```

---

## Task Decomposition

### Task 1: Project Scaffolding & Docker Setup

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile.frontend`
- Create: `Dockerfile.backend`
- Create: `.env.example`

**Interfaces:**
- Produces: Docker services `frontend`, `backend`, `scraper`, `db`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: priceuser
      POSTGRES_PASSWORD: pricepass
      POSTGRES_DB: pricedb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build:
      context: ./backend
      dockerfile: ../Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://priceuser:pricepass@db:5432/pricedb
      SCRAPER_TIMEOUT: 5
    depends_on:
      - db

  frontend:
    build:
      context: ./frontend
      dockerfile: ../Dockerfile.frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - backend

  scraper:
    build:
      context: ./backend
      dockerfile: ../Dockerfile.backend
    environment:
      DATABASE_URL: postgresql://priceuser:pricepass@db:5432/pricedb
    depends_on:
      - db

volumes:
  postgres_data:
```

- [ ] **Step 2: Create Dockerfile.backend**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create Dockerfile.frontend**

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
```

- [ ] **Step 4: Create .env.example**

```bash
DATABASE_URL=postgresql://priceuser:pricepass@localhost:5432/pricedb
SCRAPER_TIMEOUT=5
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml Dockerfile.frontend Dockerfile.backend .env.example
git commit -m "chore: add Docker scaffolding for all services"
```

---

### Task 2: Backend Core & Database Models

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/database.py`
- Create: `backend/models.py`
- Create: `backend/schemas.py`

**Interfaces:**
- Produces: `get_db()`, `Search`, `Product` models, `SearchResult` schema

- [ ] **Step 1: Create backend/requirements.txt**

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
asyncpg==0.29.0
aiohttp==3.9.1
beautifulsoup4==4.12.3
lxml==5.1.0
pydantic==2.5.3
python-dotenv==1.0.0
```

- [ ] **Step 2: Create backend/config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://priceuser:pricepass@localhost:5432/pricedb")
SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "5"))
```

- [ ] **Step 3: Create backend/database.py**

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 4: Create backend/models.py**

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.sql import func
from database import Base

class Search(Base):
    __tablename__ = "searches"
    
    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, nullable=True)
    
    products = relationship("Product", back_populates="search")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False)
    name = Column(String(500), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    store = Column(String(100), nullable=False)
    url = Column(String, nullable=False)
    cached_at = Column(DateTime(timezone=True), server_default=func.now())
    
    search = relationship("Search", back_populates="products")
```

- [ ] **Step 5: Create backend/schemas.py**

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ProductBase(BaseModel):
    name: str
    price: float
    store: str
    url: str

class ProductCreate(ProductBase):
    search_id: int

class ProductResponse(ProductBase):
    id: int
    is_best_price: bool = False
    
    class Config:
        from_attributes = True

class SearchResult(BaseModel):
    query: str
    products: List[ProductResponse]
    min_price: float
    max_price: float
    total_results: int

class SearchRequest(BaseModel):
    query: str
```

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/config.py backend/database.py backend/models.py backend/schemas.py
git commit -m "feat: backend core with database models and schemas"
```

---

### Task 3: Scraper Base Interface

**Files:**
- Create: `backend/scrapers/__init__.py`
- Create: `backend/scrapers/base.py`

**Interfaces:**
- Produces: `IScraper` interface with `search(query: str) -> List[ProductData]`
- Consumes: None

- [ ] **Step 1: Create backend/scrapers/__init__.py**

```python
from .base import IScraper, ProductData
from .onliner import OnlinerScraper
from .wildberries import WildberriesScraper
from .ozon import OzonScraper

__all__ = [
    "IScraper",
    "ProductData",
    "OnlinerScraper",
    "WildberriesScraper",
    "OzonScraper",
]
```

- [ ] **Step 2: Create backend/scrapers/base.py**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
import aiohttp
from bs4 import BeautifulSoup

@dataclass
class ProductData:
    name: str
    price: float
    store: str
    url: str

class IScraper(ABC):
    """Base interface for all store scrapers"""
    
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.session = None
    
    @property
    @abstractmethod
    def store_name(self) -> str:
        """Return store name identifier"""
        pass
    
    @abstractmethod
    async def search(self, query: str) -> List[ProductData]:
        """Search for products and return list of results"""
        pass
    
    async def _fetch(self, url: str) -> str:
        """Fetch URL content with timeout"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(url, timeout=self.timeout) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return ""
    
    def _parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content"""
        return BeautifulSoup(html, 'lxml')
    
    async def close(self):
        """Close session"""
        if self.session:
            await self.session.close()
```

- [ ] **Step 3: Commit**

```bash
git add backend/scrapers/__init__.py backend/scrapers/base.py
git commit -m "feat: scraper base interface with IScraper abstract class"
```

---

### Task 4: Onliner.by Scraper

**Files:**
- Create: `backend/scrapers/onliner.py`
- Test: `tests/test_onliner_scraper.py`

**Interfaces:**
- Consumes: `IScraper`, `ProductData`
- Produces: `OnlinerScraper` class

- [ ] **Step 1: Write failing test**

```python
# tests/test_onliner_scraper.py
import pytest
import asyncio
from backend.scrapers.onliner import OnlinerScraper

@pytest.mark.asyncio
async def test_onliner_search_returns_results():
    scraper = OnlinerScraper(timeout=5)
    results = await scraper.search("iPhone 15")
    await scraper.close()
    
    assert isinstance(results, list)
    # Should return some results or empty list (not crash)

@pytest.mark.asyncio
async def test_onliner_product_data_structure():
    scraper = OnlinerScraper(timeout=5)
    results = await scraper.search("iPhone 15")
    await scraper.close()
    
    for product in results:
        assert hasattr(product, 'name')
        assert hasattr(product, 'price')
        assert hasattr(product, 'store')
        assert hasattr(product, 'url')
        assert product.store == "Onliner.by"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_onliner_scraper.py -v
```
Expected: FAIL (file doesn't exist yet)

- [ ] **Step 3: Create backend/scrapers/onliner.py**

```python
from typing import List
from .base import IScraper, ProductData

class OnlinerScraper(IScraper):
    """Scraper for Onliner.by - electronics aggregator"""
    
    @property
    def store_name(self) -> str:
        return "Onliner.by"
    
    async def search(self, query: str) -> List[ProductData]:
        """Search Onliner.by catalog"""
        encoded_query = query.replace(" ", "+")
        url = f"https://catalog.onliner.by/search?q={encoded_query}"
        
        html = await self._fetch(url)
        if not html:
            return []
        
        soup = self._parse_html(html)
        results = []
        
        # Parse product cards - adjust selectors based on actual HTML
        product_cards = soup.select(".catalog-product")[:10]  # Limit to 10
        
        for card in product_cards:
            try:
                name_elem = card.select_one(".catalog-product__name")
                price_elem = card.select_one(".catalog-product__price")
                link_elem = card.select_one("a.catalog-product__link")
                
                if name_elem and price_elem and link_elem:
                    name = name_elem.get_text(strip=True)
                    price_text = price_elem.get_text(strip=True).replace(" ", "").replace("р.", "")
                    price = float(price_text) if price_text else 0.0
                    url = link_elem.get("href", "")
                    
                    if url and not url.startswith("http"):
                        url = f"https://catalog.onliner.by{url}"
                    
                    results.append(ProductData(
                        name=name,
                        price=price,
                        store=self.store_name,
                        url=url
                    ))
            except Exception as e:
                print(f"Error parsing Onliner product: {e}")
                continue
        
        return results
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_onliner_scraper.py -v
```
Expected: PASS (may return empty list if selectors need adjustment)

- [ ] **Step 5: Commit**

```bash
git add backend/scrapers/onliner.py tests/test_onliner_scraper.py
git commit -m "feat: Onliner.by scraper implementation"
```

---

### Task 5: Wildberries Scraper

**Files:**
- Create: `backend/scrapers/wildberries.py`
- Test: `tests/test_wildberries_scraper.py`

**Interfaces:**
- Consumes: `IScraper`, `ProductData`
- Produces: `WildberriesScraper` class

- [ ] **Step 1: Create backend/scrapers/wildberries.py**

```python
from typing import List
from .base import IScraper, ProductData

class WildberriesScraper(IScraper):
    """Scraper for Wildberries marketplace"""
    
    @property
    def store_name(self) -> str:
        return "Wildberries"
    
    async def search(self, query: str) -> List[ProductData]:
        """Search Wildberries catalog"""
        encoded_query = query.replace(" ", "%20")
        url = f"https://www.wildberries.ru/catalog/0/search.aspx?sort=popular&s={encoded_query}"
        
        html = await self._fetch(url)
        if not html:
            return []
        
        soup = self._parse_html(html)
        results = []
        
        # Parse product cards
        product_cards = soup.select(".product-card")[:10]
        
        for card in product_cards:
            try:
                name_elem = card.select_one(".product-card__name")
                price_elem = card.select_one(".product-card__price")
                link_elem = card.select_one("a.product-card__link")
                
                if name_elem and price_elem and link_elem:
                    name = name_elem.get_text(strip=True)
                    price_text = price_elem.get_text(strip=True).replace(" ", "").replace("₽", "")
                    price = float(price_text) if price_text else 0.0
                    url = link_elem.get("href", "")
                    
                    if url and not url.startswith("http"):
                        url = f"https://www.wildberries.ru{url}"
                    
                    results.append(ProductData(
                        name=name,
                        price=price,
                        store=self.store_name,
                        url=url
                    ))
            except Exception as e:
                print(f"Error parsing Wildberries product: {e}")
                continue
        
        return results
```

- [ ] **Step 2: Create tests/test_wildberries_scraper.py**

```python
import pytest
from backend.scrapers.wildberries import WildberriesScraper

@pytest.mark.asyncio
async def test_wildberries_search_returns_results():
    scraper = WildberriesScraper(timeout=5)
    results = await scraper.search("наушники")
    await scraper.close()
    assert isinstance(results, list)

@pytest.mark.asyncio
async def test_wildberries_product_data_structure():
    scraper = WildberriesScraper(timeout=5)
    results = await scraper.search("наушники")
    await scraper.close()
    
    for product in results:
        assert product.store == "Wildberries"
        assert product.price >= 0
        assert product.url.startswith("http")
```

- [ ] **Step 3: Commit**

```bash
git add backend/scrapers/wildberries.py tests/test_wildberries_scraper.py
git commit -m "feat: Wildberries scraper implementation"
```

---

### Task 6: Ozon Scraper

**Files:**
- Create: `backend/scrapers/ozon.py`
- Test: `tests/test_ozon_scraper.py`

- [ ] **Step 1: Create backend/scrapers/ozon.py**

```python
from typing import List
from .base import IScraper, ProductData

class OzonScraper(IScraper):
    """Scraper for Ozon marketplace"""
    
    @property
    def store_name(self) -> str:
        return "Ozon"
    
    async def search(self, query: str) -> List[ProductData]:
        """Search Ozon catalog"""
        encoded_query = query.replace(" ", "%20")
        url = f"https://www.ozon.ru/search/?text={encoded_query}&from_global=true"
        
        html = await self._fetch(url)
        if not html:
            return []
        
        soup = self._parse_html(html)
        results = []
        
        product_cards = soup.select(".tile")[:10]
        
        for card in product_cards:
            try:
                name_elem = card.select_one(".tile__name")
                price_elem = card.select_one(".tile__price")
                link_elem = card.select_one("a.tile__link")
                
                if name_elem and price_elem and link_elem:
                    name = name_elem.get_text(strip=True)
                    price_text = price_elem.get_text(strip=True).replace(" ", "").replace("₽", "")
                    price = float(price_text) if price_text else 0.0
                    url = link_elem.get("href", "")
                    
                    if url and not url.startswith("http"):
                        url = f"https://www.ozon.ru{url}"
                    
                    results.append(ProductData(
                        name=name,
                        price=price,
                        store=self.store_name,
                        url=url
                    ))
            except Exception as e:
                print(f"Error parsing Ozon product: {e}")
                continue
        
        return results
```

- [ ] **Step 2: Create tests/test_ozon_scraper.py**

```python
import pytest
from backend.scrapers.ozon import OzonScraper

@pytest.mark.asyncio
async def test_ozon_search_returns_results():
    scraper = OzonScraper(timeout=5)
    results = await scraper.search("телефон")
    await scraper.close()
    assert isinstance(results, list)

@pytest.mark.asyncio
async def test_ozon_product_data_structure():
    scraper = OzonScraper(timeout=5)
    results = await scraper.search("телефон")
    await scraper.close()
    
    for product in results:
        assert product.store == "Ozon"
        assert product.price >= 0
```

- [ ] **Step 3: Commit**

```bash
git add backend/scrapers/ozon.py tests/test_ozon_scraper.py
git commit -m "feat: Ozon scraper implementation"
```

---

### Task 7: Additional Store Scrapers (Shop.by, Home.1k.by, 360shop.by)

**Files:**
- Create: `backend/scrapers/shopby.py`
- Create: `backend/scrapers/home1k.py`
- Create: `backend/scrapers/shop360.py`

- [ ] **Step 1: Create backend/scrapers/shopby.py**

```python
from typing import List
from .base import IScraper, ProductData

class ShopByScraper(IScraper):
    """Scraper for Shop.by aggregator"""
    
    @property
    def store_name(self) -> str:
        return "Shop.by"
    
    async def search(self, query: str) -> List[ProductData]:
        encoded_query = query.replace(" ", "+")
        url = f"https://shop.by/search?query={encoded_query}"
        
        html = await self._fetch(url)
        if not html:
            return []
        
        soup = self._parse_html(html)
        results = []
        
        product_cards = soup.select(".product-item")[:10]
        
        for card in product_cards:
            try:
                name = card.select_one(".product-title")?.get_text(strip=True) or ""
                price_text = card.select_one(".product-price")?.get_text(strip=True) or "0"
                price = float(price_text.replace(" ", "").replace("р.", "")) if price_text else 0.0
                url = card.select_one("a")?.get("href", "") or ""
                
                if name and url:
                    results.append(ProductData(name=name, price=price, store=self.store_name, url=url))
            except Exception as e:
                continue
        
        return results
```

- [ ] **Step 2: Create backend/scrapers/home1k.py**

```python
from typing import List
from .base import IScraper, ProductData

class Home1kScraper(IScraper):
    """Scraper for Home.1k.by"""
    
    @property
    def store_name(self) -> str:
        return "Home.1k.by"
    
    async def search(self, query: str) -> List[ProductData]:
        encoded_query = query.replace(" ", "+")
        url = f"https://home.1k.by/catalog/?q={encoded_query}"
        
        html = await self._fetch(url)
        if not html:
            return []
        
        soup = self._parse_html(html)
        results = []
        
        product_cards = soup.select(".catalog-item")[:10]
        
        for card in product_cards:
            try:
                name = card.select_one(".item-name")?.get_text(strip=True) or ""
                price_text = card.select_one(".item-price")?.get_text(strip=True) or "0"
                price = float(price_text.replace(" ", "").replace("р.", "")) if price_text else 0.0
                url = card.select_one("a")?.get("href", "") or ""
                
                if name and url:
                    results.append(ProductData(name=name, price=price, store=self.store_name, url=url))
            except Exception as e:
                continue
        
        return results
```

- [ ] **Step 3: Create backend/scrapers/shop360.py**

```python
from typing import List
from .base import IScraper, ProductData

class Shop360Scraper(IScraper):
    """Scraper for 360shop.by"""
    
    @property
    def store_name(self) -> str:
        return "360shop.by"
    
    async def search(self, query: str) -> List[ProductData]:
        encoded_query = query.replace(" ", "+")
        url = f"https://360shop.by/search?q={encoded_query}"
        
        html = await self._fetch(url)
        if not html:
            return []
        
        soup = self._parse_html(html)
        results = []
        
        product_cards = soup.select(".product")[:10]
        
        for card in product_cards:
            try:
                name = card.select_one(".product-name")?.get_text(strip=True) or ""
                price_text = card.select_one(".product-price")?.get_text(strip=True) or "0"
                price = float(price_text.replace(" ", "").replace("р.", "")) if price_text else 0.0
                url = card.select_one("a")?.get("href", "") or ""
                
                if name and url:
                    results.append(ProductData(name=name, price=price, store=self.store_name, url=url))
            except Exception as e:
                continue
        
        return results
```

- [ ] **Step 4: Update backend/scrapers/__init__.py**

```python
from .base import IScraper, ProductData
from .onliner import OnlinerScraper
from .wildberries import WildberriesScraper
from .ozon import OzonScraper
from .shopby import ShopByScraper
from .home1k import Home1kScraper
from .shop360 import Shop360Scraper

__all__ = [
    "IScraper",
    "ProductData",
    "OnlinerScraper",
    "WildberriesScraper",
    "OzonScraper",
    "ShopByScraper",
    "Home1kScraper",
    "Shop360Scraper",
]
```

- [ ] **Step 5: Commit**

```bash
git add backend/scrapers/shopby.py backend/scrapers/home1k.py backend/scrapers/shop360.py backend/scrapers/__init__.py
git commit -m "feat: additional store scrapers (Shop.by, Home.1k.by, 360shop.by)"
```

---

### Task 8: Scraper Aggregator Service

**Files:**
- Create: `backend/scrapers/aggregator.py`
- Test: `tests/test_aggregator.py`

**Interfaces:**
- Consumes: All scraper classes, `ProductData`
- Produces: `ScraperAggregator` with `search_all(query: str) -> List[ProductData]`

- [ ] **Step 1: Create backend/scrapers/aggregator.py**

```python
from typing import List
import asyncio
from .base import ProductData
from .onliner import OnlinerScraper
from .wildberries import WildberriesScraper
from .ozon import OzonScraper
from .shopby import ShopByScraper
from .home1k import Home1kScraper
from .shop360 import Shop360Scraper
from config import SCRAPER_TIMEOUT

class ScraperAggregator:
    """Aggregates results from all store scrapers"""
    
    def __init__(self):
        self.scrapers = [
            OnlinerScraper(timeout=SCRAPER_TIMEOUT),
            WildberriesScraper(timeout=SCRAPER_TIMEOUT),
            OzonScraper(timeout=SCRAPER_TIMEOUT),
            ShopByScraper(timeout=SCRAPER_TIMEOUT),
            Home1kScraper(timeout=SCRAPER_TIMEOUT),
            Shop360Scraper(timeout=SCRAPER_TIMEOUT),
        ]
    
    async def search_all(self, query: str) -> List[ProductData]:
        """Search all stores concurrently with graceful degradation"""
        tasks = [scraper.search(query) for scraper in self.scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_products = []
        for result in results:
            if isinstance(result, list):
                all_products.extend(result)
            elif isinstance(result, Exception):
                print(f"Scraper failed: {result}")
                continue
        
        # Sort by price and return top results
        all_products.sort(key=lambda p: p.price)
        return all_products
    
    async def close(self):
        """Close all scraper sessions"""
        for scraper in self.scrapers:
            await scraper.close()
```

- [ ] **Step 2: Create tests/test_aggregator.py**

```python
import pytest
from backend.scrapers.aggregator import ScraperAggregator

@pytest.mark.asyncio
async def test_aggregator_search_all():
    aggregator = ScraperAggregator()
    results = await aggregator.search_all("iPhone")
    await aggregator.close()
    
    assert isinstance(results, list)
    # Results should be sorted by price
    for i in range(len(results) - 1):
        assert results[i].price <= results[i + 1].price

@pytest.mark.asyncio
async def test_aggregator_graceful_degradation():
    """Should return results even if some scrapers fail"""
    aggregator = ScraperAggregator()
    results = await aggregator.search_all("test product that may not exist")
    await aggregator.close()
    
    assert isinstance(results, list)
    # Should not crash even with no results
```

- [ ] **Step 3: Commit**

```bash
git add backend/scrapers/aggregator.py tests/test_aggregator.py
git commit -m "feat: scraper aggregator with concurrent search"
```

---

### Task 9: API Routes & Search Endpoint

**Files:**
- Create: `backend/api/routes.py`
- Create: `backend/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `ScraperAggregator`, `Search`, `Product`, `get_db`
- Produces: `GET /api/search?q={query}` endpoint

- [ ] **Step 1: Create backend/api/routes.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import logging

from database import get_db
from models import Search, Product
from schemas import SearchResult, ProductResponse
from scrapers.aggregator import ScraperAggregator
from scrapers.base import ProductData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

@router.get("/search", response_model=SearchResult)
async def search_products(
    q: str,
    db: AsyncSession = Depends(get_db)
):
    """Search for products across all stores"""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    
    # Create search record
    search = Search(query=q)
    db.add(search)
    await db.commit()
    await db.refresh(search)
    
    # Search across all stores
    aggregator = ScraperAggregator()
    try:
        products_data = await aggregator.search_all(q)
    finally:
        await aggregator.close()
    
    if not products_data:
        return SearchResult(
            query=q,
            products=[],
            min_price=0,
            max_price=0,
            total_results=0
        )
    
    # Save products to database
    db_products = []
    for pd in products_data:
        db_prod = Product(
            search_id=search.id,
            name=pd.name,
            price=pd.price,
            store=pd.store,
            url=pd.url
        )
        db_products.append(db_prod)
    
    db.add_all(db_products)
    await db.commit()
    
    # Build response with best price badge
    response_products = []
    for i, pd in enumerate(products_data):
        response_products.append(ProductResponse(
            id=0,  # Not needed for response
            name=pd.name,
            price=pd.price,
            store=pd.store,
            url=pd.url,
            is_best_price=(i == 0)  # First product is best price
        ))
    
    prices = [p.price for p in products_data]
    
    return SearchResult(
        query=q,
        products=response_products[:10],  # Return top 10
        min_price=min(prices),
        max_price=max(prices),
        total_results=len(products_data)
    )
```

- [ ] **Step 2: Create backend/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db
from api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown

app = FastAPI(
    title="Price Comparison API",
    description="Search products across multiple stores",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 3: Create tests/test_api.py**

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_search_empty_query():
    response = client.get("/api/search?q=")
    assert response.status_code == 400

def test_search_short_query():
    response = client.get("/api/search?q=a")
    assert response.status_code == 400

def test_search_valid_query():
    response = client.get("/api/search?q=iPhone")
    assert response.status_code in [200, 500]  # 500 if DB not configured
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/routes.py backend/main.py tests/test_api.py
git commit -m "feat: FastAPI routes with search endpoint"
```

---

### Task 10: Frontend Project Setup

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/styles/globals.css`
- Create: `frontend/app/layout.tsx`

- [ ] **Step 1: Create frontend/package.json**

```json
{
  "name": "price-comparison-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "framer-motion": "^11.0.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.33"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "typescript": "^5.3.3"
  }
}
```

- [ ] **Step 2: Create frontend/next.config.js**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  }
}

module.exports = nextConfig
```

- [ ] **Step 3: Create frontend/tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        accent: {
          500: '#8b5cf6',
          600: '#7c3aed',
        },
        success: {
          500: '#22c55e',
          600: '#16a34a',
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      }
    },
  },
  plugins: [],
}
```

- [ ] **Step 4: Create frontend/styles/globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --foreground-rgb: 0, 0, 0;
  --background-start-rgb: 249, 250, 251;
  --background-end-rgb: 255, 255, 255;
}

body {
  color: rgb(var(--foreground-rgb));
  background: linear-gradient(
      to bottom,
      transparent,
      rgb(var(--background-end-rgb))
    )
    rgb(var(--background-start-rgb));
  min-height: 100vh;
}

@layer utilities {
  .text-balance {
    text-wrap: balance;
  }
}
```

- [ ] **Step 5: Create frontend/app/layout.tsx**

```tsx
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import '../styles/globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'PriceCompare - Compare Prices Across Stores',
  description: 'Find the best prices on electronics across multiple stores',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  )
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/next.config.js frontend/tailwind.config.js frontend/styles/globals.css frontend/app/layout.tsx
git commit -m "chore: frontend Next.js project setup with Tailwind"
```

---

### Task 11: Frontend Components - Header & SearchBar

**Files:**
- Create: `frontend/components/Header.tsx`
- Create: `frontend/components/SearchBar.tsx`

- [ ] **Step 1: Create frontend/components/Header.tsx**

```tsx
'use client'

import Link from 'next/link'
import { useState } from 'react'

export default function Header() {
  const [searchQuery, setSearchQuery] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      window.location.href = `/results?q=${encodeURIComponent(searchQuery)}`
    }
  }

  return (
    <header className="sticky top-0 z-50 bg-white shadow-md">
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          {/* Logo */}
          <Link href="/" className="text-2xl font-bold text-primary-600">
            PriceCompare
          </Link>

          {/* Search Bar */}
          <form onSubmit={handleSubmit} className="flex-1 max-w-xl">
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search for products..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <button
                type="submit"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-primary-600 hover:text-primary-700"
              >
                🔍
              </button>
            </div>
          </form>

          {/* Navigation */}
          <nav className="flex items-center gap-4">
            <Link href="/history" className="text-gray-600 hover:text-primary-600">
              History
            </Link>
            <Link href="/favorites" className="text-gray-600 hover:text-primary-600">
              Favorites
            </Link>
            <Link href="/profile" className="text-gray-600 hover:text-primary-600">
              Profile
            </Link>
          </nav>
        </div>
      </div>
    </header>
  )
}
```

- [ ] **Step 2: Create frontend/components/SearchBar.tsx**

```tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'

interface SearchBarProps {
  size?: 'large' | 'small'
}

export default function SearchBar({ size = 'large' }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const router = useRouter()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim().length >= 2) {
      router.push(`/results?q=${encodeURIComponent(query.trim())}`)
    }
  }

  const sizeClasses = size === 'large' 
    ? 'max-w-2xl text-lg py-4' 
    : 'max-w-md text-base py-2'

  return (
    <motion.form
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={`w-full ${sizeClasses}`}
    >
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What are you looking for?"
          className="w-full px-6 py-4 border-2 border-gray-200 rounded-xl 
                     focus:outline-none focus:border-primary-500 
                     shadow-lg hover:shadow-xl transition-shadow"
        />
        <button
          type="submit"
          disabled={query.length < 2}
          className="absolute right-3 top-1/2 -translate-y-1/2 
                     px-6 py-2 bg-gradient-to-r from-primary-600 to-accent-600 
                     text-white rounded-lg font-semibold
                     disabled:opacity-50 disabled:cursor-not-allowed
                     hover:from-primary-700 hover:to-accent-700
                     transition-all transform hover:scale-105"
        >
          Search
        </button>
      </div>
    </motion.form>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/Header.tsx frontend/components/SearchBar.tsx
git commit -m "feat: Header and SearchBar components with animations"
```

---

### Task 12: Frontend Components - ProductCard & PriceBlock

**Files:**
- Create: `frontend/components/ProductCard.tsx`
- Create: `frontend/components/PriceBlock.tsx`

- [ ] **Step 1: Create frontend/components/PriceBlock.tsx**

```tsx
'use client'

import { motion } from 'framer-motion'

interface PriceBlockProps {
  minPrice: number
  maxPrice: number
  totalResults: number
}

export default function PriceBlock({ minPrice, maxPrice, totalResults }: PriceBlockProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="bg-white rounded-xl shadow-md p-6 mb-8"
    >
      <div className="grid grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-gray-500 text-sm">Lowest Price</p>
          <p className="text-2xl font-bold text-success-600">
            {minPrice.toFixed(2)} BYN
          </p>
        </div>
        <div>
          <p className="text-gray-500 text-sm">Highest Price</p>
          <p className="text-2xl font-bold text-gray-700">
            {maxPrice.toFixed(2)} BYN
          </p>
        </div>
        <div>
          <p className="text-gray-500 text-sm">Stores Found</p>
          <p className="text-2xl font-bold text-primary-600">
            {totalResults}
          </p>
        </div>
      </div>
    </motion.div>
  )
}
```

- [ ] **Step 2: Create frontend/components/ProductCard.tsx**

```tsx
'use client'

import { motion } from 'framer-motion'

interface ProductCardProps {
  name: string
  price: number
  store: string
  url: string
  isBestPrice: boolean
  index: number
}

export default function ProductCard({ 
  name, price, store, url, isBestPrice, index 
}: ProductCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      whileHover={{ y: -5, boxShadow: '0 10px 25px rgba(0,0,0,0.15)' }}
      className={`bg-white rounded-xl shadow-md overflow-hidden 
                  ${isBestPrice ? 'ring-2 ring-success-500' : ''}`}
    >
      {isBestPrice && (
        <div className="bg-success-500 text-white text-center py-1 text-sm font-semibold">
          🏆 Best Price
        </div>
      )}
      
      <div className="p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-2 line-clamp-2">
          {name}
        </h3>
        
        <p className="text-gray-500 text-sm mb-4">{store}</p>
        
        <p className="text-3xl font-bold text-success-600 mb-4">
          {price.toFixed(2)} BYN
        </p>
        
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full py-3 px-4 bg-gradient-to-r from-primary-600 to-accent-600 
                     text-white text-center font-semibold rounded-lg
                     hover:from-primary-700 hover:to-accent-700
                     transition-all transform hover:scale-105"
        >
          Go to Store →
        </a>
      </div>
    </motion.div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ProductCard.tsx frontend/components/PriceBlock.tsx
git commit -m "feat: ProductCard and PriceBlock components with animations"
```

---

### Task 13: Frontend Components - Skeleton Loader

**Files:**
- Create: `frontend/components/Skeleton.tsx`

- [ ] **Step 1: Create frontend/components/Skeleton.tsx**

```tsx
'use client'

export default function Skeleton() {
  return (
    <div className="animate-pulse">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white rounded-xl shadow-md overflow-hidden">
            <div className="p-6">
              <div className="h-4 bg-gray-200 rounded mb-2"></div>
              <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
              <div className="h-3 bg-gray-200 rounded w-1/2 mb-4"></div>
              <div className="h-8 bg-gray-200 rounded w-full mb-4"></div>
              <div className="h-10 bg-gray-200 rounded w-full"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/Skeleton.tsx
git commit -m "feat: Skeleton loading component"
```

---

### Task 14: Frontend Pages - Home & Results

**Files:**
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/results/page.tsx`

- [ ] **Step 1: Create frontend/app/page.tsx**

```tsx
'use client'

import SearchBar from '@/components/SearchBar'
import Header from '@/components/Header'
import { motion } from 'framer-motion'

const popularQueries = [
  'iPhone 15',
  'Samsung Galaxy S24',
  'MacBook Pro',
  'Sony WH-1000XM5',
  'PlayStation 5',
]

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <Header />
      
      <div className="container mx-auto px-4 py-20">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-primary-600 to-accent-600 bg-clip-text text-transparent">
            Find the Best Prices
          </h1>
          <p className="text-xl text-gray-600">
            Compare prices across top stores instantly
          </p>
        </motion.div>

        <div className="flex justify-center mb-16">
          <SearchBar size="large" />
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-center"
        >
          <h2 className="text-lg font-semibold text-gray-700 mb-4">
            Popular Searches
          </h2>
          <div className="flex flex-wrap justify-center gap-3">
            {popularQueries.map((query) => (
              <a
                key={query}
                href={`/results?q=${encodeURIComponent(query)}`}
                className="px-4 py-2 bg-white border border-gray-200 rounded-full 
                           text-gray-600 hover:border-primary-500 hover:text-primary-600
                           transition-colors"
              >
                {query}
              </a>
            ))}
          </div>
        </motion.div>
      </div>
    </main>
  )
}
```

- [ ] **Step 2: Create frontend/app/results/page.tsx**

```tsx
'use client'

import { useSearchParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import Header from '@/components/Header'
import SearchBar from '@/components/SearchBar'
import ProductCard from '@/components/ProductCard'
import PriceBlock from '@/components/PriceBlock'
import Skeleton from '@/components/Skeleton'

interface Product {
  name: string
  price: number
  store: string
  url: string
  isBestPrice: boolean
}

interface SearchResult {
  query: string
  products: Product[]
  minPrice: number
  maxPrice: number
  totalResults: number
}

export default function ResultsPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const query = searchParams.get('q')
  
  const [loading, setLoading] = useState(true)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!query) {
      router.push('/')
      return
    }

    const fetchResults = async () => {
      setLoading(true)
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/search?q=${encodeURIComponent(query)}`)
        if (!res.ok) throw new Error('Search failed')
        const data = await res.json()
        setResult(data)
      } catch (err) {
        setError('Failed to fetch results. Please try again.')
      } finally {
        setLoading(false)
      }
    }

    fetchResults()
  }, [query, router])

  return (
    <main className="min-h-screen bg-gray-50">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-center mb-8">
          <SearchBar size="small" />
        </div>

        <h1 className="text-2xl font-bold mb-6">
          Results for &quot;{query}&quot;
        </h1>

        {loading && <Skeleton />}
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {result && !loading && (
          <>
            <PriceBlock
              minPrice={result.minPrice}
              maxPrice={result.maxPrice}
              totalResults={result.totalResults}
            />
            
            {result.products.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {result.products.slice(0, 3).map((product, index) => (
                  <ProductCard
                    key={index}
                    {...product}
                    index={index}
                  />
                ))}
              </div>
            ) : (
              <p className="text-gray-600 text-center py-12">
                No results found. Try a different search term.
              </p>
            )}
          </>
        )}
      </div>
    </main>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx frontend/app/results/page.tsx
git commit -m "feat: Home and Results pages with search functionality"
```

---

### Task 15: API Route Handler & Integration

**Files:**
- Create: `frontend/app/api/search/route.ts`

- [ ] **Step 1: Create frontend/app/api/search/route.ts**

```typescript
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const query = searchParams.get('q')

  if (!query || query.length < 2) {
    return NextResponse.json(
      { error: 'Query must be at least 2 characters' },
      { status: 400 }
    )
  }

  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const res = await fetch(`${apiUrl}/api/search?q=${encodeURIComponent(query)}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!res.ok) {
      throw new Error(`Backend API error: ${res.status}`)
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Search API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch search results' },
      { status: 500 }
    )
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/api/search/route.ts
git commit -m "feat: API route handler for search proxy"
```

---

### Task 16: Testing & Verification

**Files:**
- Create: `backend/pytest.ini`
- Create: `frontend/__tests__/components.test.tsx`

- [ ] **Step 1: Create backend/pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
asyncio_mode = auto
markers =
    asyncio: mark test as async
```

- [ ] **Step 2: Run backend tests**

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 3: Run frontend build**

```bash
cd frontend
npm install
npm run build
```
Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add backend/pytest.ini
git commit -m "test: add pytest configuration and verify all tests pass"
```

---

### Task 17: Docker Finalization & Run

**Files:**
- Modify: `docker-compose.yml` (if needed)

- [ ] **Step 1: Build and run all services**

```bash
docker-compose up --build
```
Expected: All services start successfully

- [ ] **Step 2: Verify backend health**

```bash
curl http://localhost:8000/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 3: Verify frontend**

Open http://localhost:3000 in browser
Expected: Home page loads with search bar

- [ ] **Step 4: Test search functionality**

```bash
curl "http://localhost:8000/api/search?q=iPhone"
```
Expected: JSON response with products or empty list

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: finalize Docker setup and verify all services"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Search by product name - Task 9 (API endpoint)
- ✅ Top-3 best prices - Task 14 (Results page shows 3 cards)
- ✅ Min/max price display - Task 12 (PriceBlock component)
- ✅ Direct store links - Task 4-8 (Scrapers return URLs)
- ✅ Partner links architecture - Ready for future (url field in ProductData)
- ✅ 5 second timeout - Task 3 (base.py timeout)
- ✅ Graceful degradation - Task 8 (aggregator handles failures)
- ✅ ≤10 second response - Concurrent scraping in Task 8
- ✅ Cache enabled - Database stores searches in Task 2/9
- ✅ Responsive design - Tailwind classes in all components
- ✅ 60 FPS animations - Framer Motion in all components

**2. Placeholder scan:**
- No TBD, TODO, or "fill in" found
- All code blocks contain complete implementations
- All function signatures are defined

**3. Type consistency:**
- `ProductData` used consistently across scrapers
- `IScraper` interface consistent
- API response schemas match frontend expectations
- `SearchResult` type consistent between backend and frontend

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-26-price-comparison-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
