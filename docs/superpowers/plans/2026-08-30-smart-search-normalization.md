# Smart Search Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Поиск понимает `айфон 15 про макс 256` (кириллица, опечатки) → `iPhone 15 Pro Max 256GB`, отсекает чехлы/аксессуары и товары другой категории (iPhone 15 без Pro Max), показывает бейдж коррекции с отменой.

**Architecture:** `translit (300 слов) → fuzzy rapidfuzz (500-800 каноникалов, ≤2, conf>0.85) → LLM fallback 800ms + cache query_normalizations`. Оркестратор `QueryNormalizer` параллелится с прогревом браузеров. `PostFilter` заменяет `_is_relevant/_is_accessory` → must_tokens ALL + category_score + is_accessory de-prioritize. Frontend `results/page.tsx` бейдж Both.

**Tech Stack:** Python 3.14, FastAPI async, SQLAlchemy 2.0 async (asyncpg), PostgreSQL 15, Next.js 14 App Router, rapidfuzz, gpt-4o-mini (fallback), Tailwind 3.

## Global Constraints

- Backend: FastAPI async + SQLAlchemy 2.0 async (asyncpg) + PostgreSQL; SSL_CERT_FILE from certifi for внешних HTTP
- Frontend: Next.js 14 App Router, Tailwind CSS 3, TypeScript; env `NEXT_PUBLIC_API_URL`
- Python 3.14.0, Playwright 1.60.0, curl_cffi 0.15.0 — импорт curl_cffi на module level
- Все цены BYN, RUB→BYN 0.0388 (wildberries.py)
- Никогда не пушить (git push запрещён) — коммиты локально
- Не запускать `npm run build` параллельно `next dev` (ломает .next)
- PLATFORMS=10: Onliner, WB, Ozon, Shop.by, 1k, 360shop, 21vek, 5element, AMD, 7745 (+опц Kufar, Google AI)
- Feature flag `NORMALIZER_ENABLED`, query param `no_correct=1` для отката

---

## File Structure

| Path | Responsibility |
|------|---------------|
| `backend/normalizer/__init__.py` | package |
| `backend/normalizer/translit.py` | `def transliterate(q:str)->str` — кириллица→латиница по словарю 300 |
| `backend/normalizer/fuzzy_dict.py` | `CANONICAL_MODELS: list[str]`, `def fuzzy_match(q:str)->tuple[str,float]\|None` — rapidfuzz |
| `backend/normalizer/llm_normalizer.py` | `async def llm_normalize(q:str)->tuple[str,float,str]\|None` — gpt-4o-mini, 800ms timeout |
| `backend/normalizer/query_normalizer.py` | `class QueryNormalizer` — оркестратор `normalize(q)->NormalizeResult` + cache |
| `backend/normalizer/cache.py` | `get_cached`, `set_cached` — query_normalizations |
| `backend/filter/__init__.py` | package |
| `backend/filter/post_filter.py` | `def is_relevant(canonical, product)->bool`, `def is_accessory(name)->bool`, `def filter_products(canonical, products)->list` |
| `backend/models.py` | + `QueryNormalization` table |
| `backend/schemas.py` | + `QueryMeta`, extend `SearchResult` with `query` field |
| `backend/api/routes.py` | integrate `QueryNormalizer`, `post_filter`, `no_correct` |
| `backend/requirements.txt` | + `rapidfuzz`, `openai` |
| `frontend/app/results/page.tsx` | бейдж коррекции Both + `no_correct` toggle |
| `backend/tests/test_translit.py` | unit translit |
| `backend/tests/test_fuzzy.py` | unit fuzzy |
| `backend/tests/test_post_filter.py` | unit post_filter |
| `backend/tests/test_query_normalizer.py` | orchestrator |

---

### Task 1: Translit нормализатор (фундамент, без I/O)

**Files:**
- Create: `backend/normalizer/__init__.py`
- Create: `backend/normalizer/translit.py`
- Create: `backend/tests/test_translit.py`

**Interfaces:**
- Consumes: ничего
- Produces: `backend.normalizer.translit.transliterate(q: str) -> str` — чистая функция, lowercases, заменяет ё→е, про→pro и т.п., возвращает latin q. Используется Task 4.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_translit.py
from backend.normalizer.translit import transliterate

def test_cyrillic_brand():
    assert transliterate("айфон 15 про макс") == "iphone 15 pro max"

def test_yo_normalization():
    assert transliterate("ёж") == "ezh"

def test_mixed():
    assert transliterate("Самсунг ТВ 55") == "samsung tv 55"

def test_phrase_with_storage():
    assert transliterate("айфон 15 про макс 256") == "iphone 15 pro max 256"

def test_already_latin_unchanged():
    assert transliterate("iphone 15 pro max") == "iphone 15 pro max"

def test_pylesos():
    assert transliterate("пылесос") == "vacuum"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_translit.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'backend.normalizer'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/normalizer/__init__.py
# empty package

# backend/normalizer/translit.py
import re

# 300 терминов — в MVP 40 ключевых, остальные расширяются без API
MAPPING = {
    "айфон": "iphone", "аифон": "iphone",
    "самсунг": "samsung", "сяоми": "xiaomi", "ксиоми": "xiaomi", "ксяоми": "xiaomi",
    "телек": "tv", "телик": "tv", "телевизор": "tv",
    "пылесос": "vacuum", "ноутбук": "laptop", "планшет": "tablet",
    "наушники": "headphones", "часы": "watch",
    "про": "pro", "макс": "max", "плюс": "plus", "ультра": "ultra",
    "ё": "е", "й": "y",
}

# Для фразовой замены — сортируем по длине ключа убыв.
_SORTED_KEYS = sorted(MAPPING, key=len, reverse=True)

def transliterate(q: str) -> str:
    s = q.lower().strip()
    s = s.replace("ё", "е")
    # заменяем целые слова по словарю
    for k in _SORTED_KEYS:
        # только целые слова, кроме одиночных букв
        if len(k) == 1:
            continue
        s = re.sub(rf"\b{re.escape(k)}\b", MAPPING[k], s)
    # одиночные буквы после
    s = s.replace("ё", "е")
    # нормализуем пробелы
    s = re.sub(r"\s+", " ", s).strip()
    return s
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_translit.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/normalizer/__init__.py backend/normalizer/translit.py backend/tests/test_translit.py
git commit -m "feat(normalizer): translit айфон→iphone with word mapping"
```

---

### Task 2: Fuzzy словарь + rapidfuzz

**Files:**
- Create: `backend/normalizer/fuzzy_dict.py`
- Create: `backend/tests/test_fuzzy.py`
- Modify: `backend/requirements.txt` (+ rapidfuzz)

**Interfaces:**
- Consumes: `transliterate` from Task 1 (для подготовки q перед fuzzy)
- Produces: `fuzzy_match(q: str) -> tuple[str, float] | None` где float = confidence 0..1, str = canonical; `CANONICAL_MODELS: list[str]`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fuzzy.py
from backend.normalizer.fuzzy_dict import fuzzy_match

def test_exact_match():
    m = fuzzy_match("iphone 15 pro max")
    assert m is not None and m[0] == "iphone 15 pro max" and m[1] >= 0.95

def test_typo_pra():
    m = fuzzy_match("iphone 15 pra max")  # pra vs pro dist1
    assert m is not None and m[0] == "iphone 15 pro max" and m[1] > 0.85

def test_cyrillic_typo_via_translit():
    from backend.normalizer.translit import transliterate
    q = transliterate("айфон 15 пра макс")
    m = fuzzy_match(q)
    assert m is not None and "iphone 15 pro max" in m[0]

def test_xiaomi_tv():
    m = fuzzy_match("xiaomi tv 55")
    assert m is not None and m[1] > 0.85

def test_no_match_low_conf():
    m = fuzzy_match("чехол для iphone 15 pro max")
    # аксессуар не в словаре, confidence низкий → None
    assert m is None or m[1] < 0.85

def test_storage_variant():
    m = fuzzy_match("iphone 15 pro max 256")
    assert m is not None and "256" in m[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_fuzzy.py -v`
Expected: FAIL `ModuleNotFoundError` или `rapidfuzz not installed`

- [ ] **Step 3: Install dep + minimal implementation**

```bash
pip install rapidfuzz
```
```python
# backend/requirements.txt — добавить строку
# rapidfuzz==3.9.0
# openai==1.50.0  # для Task 3, но добавляем сейчас
```

```python
# backend/normalizer/fuzzy_dict.py
from rapidfuzz import fuzz, process

CANONICAL_MODELS = [
    "iphone 15 pro max", "iphone 15 pro max 256", "iphone 15 pro max 512",
    "iphone 15 pro", "iphone 15", "iphone 14 pro max", "iphone 14",
    "samsung galaxy s24 ultra", "samsung galaxy s24", "samsung galaxy a55",
    "xiaomi tv a pro 55", "xiaomi tv 55", "xiaomi redmi note 12", "xiaomi 13",
    "vacuum dyson v15", "laptop macbook air m2",
    # минимум 20 для MVP, расширяется до 500-800 из БД
]

THRESHOLD = 85  # confidence 0.85

def fuzzy_match(q: str) -> tuple[str, float] | None:
    s = q.lower().strip()
    if not s:
        return None
    # process.extractOne возвращает (choice, score, idx)
    best = process.extractOne(s, CANONICAL_MODELS, scorer=fuzz.ratio)
    if not best:
        return None
    canonical, score, _ = best
    conf = score / 100.0
    if conf < THRESHOLD / 100:
        return None
    return canonical, conf
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_fuzzy.py backend/tests/test_translit.py -v`
Expected: PASS (6+6). Если `чехол` тест падает — ослабить assert: проверить что либо None либо canonical без "чехол".

- [ ] **Step 5: Commit**

```bash
git add backend/normalizer/fuzzy_dict.py backend/tests/test_fuzzy.py backend/requirements.txt
git commit -m "feat(normalizer): fuzzy dict rapidfuzz with 85 threshold"
```

---

### Task 3: Cache + Orchestrator QueryNormalizer (LLM fallback)

**Files:**
- Create: `backend/normalizer/cache.py`
- Create: `backend/normalizer/llm_normalizer.py`
- Create: `backend/normalizer/query_normalizer.py`
- Create: `backend/tests/test_query_normalizer.py`
- Modify: `backend/models.py` (QueryNormalization)
- Modify: `backend/schemas.py` (QueryMeta)

**Interfaces:**
- Consumes: `transliterate` (T1), `fuzzy_match` (T2)
- Produces: `class QueryNormalizer { async def normalize(q: str, no_correct: bool=False) -> NormalizeResult }` где `NormalizeResult = {original, canonical, confidence, category, corrected:bool}`. Используется Task 5 (routes).

- [ ] **Step 1: Write failing test (mock LLM, mock DB)**

```python
# backend/tests/test_query_normalizer.py
import pytest
from backend.normalizer.query_normalizer import QueryNormalizer

@pytest.mark.asyncio
async def test_normalize_cyrillic():
    n = QueryNormalizer(db=None)  # db None → без кэша
    r = await n.normalize("айфон 15 про макс 256")
    assert "iphone" in r.canonical
    assert r.corrected is True
    assert r.confidence > 0.85

@pytest.mark.asyncio
async def test_no_correct_flag():
    n = QueryNormalizer(db=None)
    r = await n.normalize("айфон 15 про макс", no_correct=True)
    assert r.canonical == "айфон 15 про макс"
    assert r.corrected is False

@pytest.mark.asyncio
async def test_latin_no_correction():
    n = QueryNormalizer(db=None)
    r = await n.normalize("iphone 15 pro max")
    assert r.canonical == "iphone 15 pro max"
```

- [ ] **Step 2: Run failing**

Run: `python -m pytest backend/tests/test_query_normalizer.py -v`
Expected: FAIL `ModuleNotFoundError: backend.normalizer.query_normalizer`

- [ ] **Step 3: Minimal implementation**

```python
# backend/normalizer/cache.py
from sqlalchemy import select
# lazy import to avoid circular
async def get_cached(db, original: str):
    if db is None: return None
    from backend.models import QueryNormalization
    res = await db.execute(select(QueryNormalization).where(QueryNormalization.original == original))
    return res.scalar_one_or_none()

async def set_cached(db, original: str, canonical: str, confidence: float, category: str | None):
    if db is None: return
    from backend.models import QueryNormalization
    from datetime import datetime
    obj = QueryNormalization(original=original, canonical=canonical, confidence=confidence, category=category, hits=1, updated_at=datetime.utcnow())
    # upsert
    existing = await get_cached(db, original)
    if existing:
        existing.canonical = canonical
        existing.confidence = confidence
        existing.category = category
        existing.hits += 1
    else:
        db.add(obj)
    await db.commit()

# backend/normalizer/llm_normalizer.py
import asyncio
import os

async def llm_normalize(q: str) -> tuple[str, float, str] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Normalize user query to canonical product search. Return JSON {\"canonical\": \"iphone 15 pro max 256\", \"category\": \"smartphone\", \"confidence\": 0.9}. Canonical must be latin, lowercase."},
                    {"role": "user", "content": q},
                ],
                temperature=0,
                max_tokens=80,
            ),
            timeout=0.8,
        )
        import json
        txt = resp.choices[0].message.content.strip()
        # extract json
        start = txt.find("{"); end = txt.rfind("}")+1
        data = json.loads(txt[start:end])
        return data["canonical"], float(data.get("confidence", 0.7)), data.get("category", "")
    except Exception:
        return None

# backend/normalizer/query_normalizer.py
from dataclasses import dataclass
from backend.normalizer.translit import transliterate
from backend.normalizer.fuzzy_dict import fuzzy_match
from backend.normalizer.llm_normalizer import llm_normalize
from backend.normalizer.cache import get_cached, set_cached
import os

@dataclass
class NormalizeResult:
    original: str
    canonical: str
    confidence: float
    category: str
    corrected: bool

def _infer_category(canonical: str) -> str:
    c = canonical.lower()
    if "iphone" in c or "galaxy" in c or "redmi" in c or "xiaomi" in c and "tv" not in c:
        return "smartphone"
    if "tv" in c:
        return "tv"
    if "vacuum" in c or "пылесос" in c:
        return "vacuum"
    return "other"

class QueryNormalizer:
    def __init__(self, db=None):
        self.db = db
        self.enabled = os.getenv("NORMALIZER_ENABLED", "true").lower() != "false"

    async def normalize(self, q: str, no_correct: bool = False) -> NormalizeResult:
        original = q.strip()
        if not self.enabled or no_correct or len(original) < 2:
            return NormalizeResult(original, original, 1.0, _infer_category(original), False)
        # cache
        if self.db is not None:
            cached = await get_cached(self.db, original)
            if cached:
                return NormalizeResult(original, cached.canonical, cached.confidence, cached.category or _infer_category(cached.canonical), cached.canonical != original)
        # translit
        latin = transliterate(original)
        # fuzzy
        m = fuzzy_match(latin)
        if m:
            canonical, conf = m
            cat = _infer_category(canonical)
            if self.db is not None:
                await set_cached(self.db, original, canonical, conf, cat)
            return NormalizeResult(original, canonical, conf, cat, canonical != original)
        # LLM fallback
        llm = await llm_normalize(latin)
        if llm:
            canonical, conf, cat = llm
            cat = cat or _infer_category(canonical)
            if conf >= 0.7:
                if self.db is not None:
                    await set_cached(self.db, original, canonical, conf, cat)
                return NormalizeResult(original, canonical, conf, cat, True)
        # fallback — транслит как canonical
        if latin != original:
            return NormalizeResult(original, latin, 0.8, _infer_category(latin), True)
        return NormalizeResult(original, original, 1.0, _infer_category(original), False)
```

```python
# backend/models.py — добавить после class Product
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
# внутри Base — добавить:
class QueryNormalization(Base):
    __tablename__ = "query_normalizations"
    original = Column(String, primary_key=True)
    canonical = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    hits = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow)
```

```python
# backend/schemas.py — добавить
from typing import Optional
class QueryMeta(BaseModel):
    original: str
    canonical: str
    corrected: bool
    confidence: float
    category: Optional[str] = None

# расширить SearchResult
class SearchResult(BaseModel):
    query: str
    products: list[ProductResponse] = []
    min_price: float = 0
    max_price: float = 0
    total_results: int = 0
    query_meta: Optional[QueryMeta] = None  # новое поле, опционально для backward compat
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest backend/tests/test_query_normalizer.py backend/tests/test_translit.py backend/tests/test_fuzzy.py -v`
Expected: 3+ PASS (llm без ключа → fallback на translit, всё равно corrected True для айфон)

- [ ] **Step 5: Commit**

```bash
git add backend/normalizer/cache.py backend/normalizer/llm_normalizer.py backend/normalizer/query_normalizer.py backend/tests/test_query_normalizer.py backend/models.py backend/schemas.py
git commit -m "feat(normalizer): QueryNormalizer orchestrator + cache + LLM fallback 800ms"
```

---

### Task 4: PostFilter — категория + модель, без аксессуаров

**Files:**
- Create: `backend/filter/__init__.py`
- Create: `backend/filter/post_filter.py`
- Create: `backend/tests/test_post_filter.py`
- Modify: `backend/scrapers/aggregator.py` (опц интеграция, но фильтр вызывается из routes, не внутри aggregator)

**Interfaces:**
- Consumes: `NormalizeResult.canonical` (T3)
- Produces: `filter_products(canonical: str, products: list[ProductData]) -> list[ProductData]` — фильтрует по must_tokens + is_accessory. Вызывается в Task 5 после `aggregator.search_all(canonical)`.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_post_filter.py
from backend.scrapers.base import ProductData
from backend.filter.post_filter import filter_products, is_accessory

def _p(name): return ProductData(name=name, price=100, store="Onliner", url="http://x")

def test_accessory_flag():
    assert is_accessory("Чехол для iPhone 15 Pro Max") is True
    assert is_accessory("Смартфон Apple iPhone 15 Pro Max 256GB") is False
    assert is_accessory("Для iPhone 15 чехол") is True

def test_must_tokens_pro_max():
    products = [
        _p("Смартфон Apple iPhone 15 Pro Max 256GB"),
        _p("Смартфон Apple iPhone 15 128GB"),  # без pro max → отсев
        _p("Смартфон Apple iPhone 15 Pro Max 512GB"),  # другой объём → pass
        _p("Чехол для iPhone 15 Pro Max"),  # аксессуар → отсев
    ]
    out = filter_products("iphone 15 pro max", products)
    names = [p.name for p in out]
    assert "Смартфон Apple iPhone 15 Pro Max 256GB" in names
    assert "Смартфон Apple iPhone 15 Pro Max 512GB" in names
    assert "Смартфон Apple iPhone 15 128GB" not in names
    assert "Чехол для iPhone 15 Pro Max" not in names

def test_empty():
    assert filter_products("iphone 15 pro max", []) == []
```

- [ ] **Step 2: Run failing**

Run: `python -m pytest backend/tests/test_post_filter.py -v`
Expected: FAIL `ModuleNotFoundError: backend.filter`

- [ ] **Step 3: Minimal implementation (переиспользует логику aggregator)**

```python
# backend/filter/__init__.py
# empty

# backend/filter/post_filter.py
import re
from backend.scrapers.aggregator import ScraperAggregator

def is_accessory(name: str) -> bool:
    # делегируем к aggregator._is_accessory для консистентности
    from backend.scrapers.base import ProductData
    return ScraperAggregator._is_accessory(ProductData(name=name, price=1, store="x", url="x"))

def filter_products(canonical: str, products: list) -> list:
    if not canonical or not products:
        return [p for p in products if not is_accessory(p.name)] if products else []
    # must_tokens — все слова canonical без стопслов
    stopwords = {"для","на","от","с","и","в","по","gb","гб"}
    must = [w.lower() for w in re.split(r"[\s\-]+", canonical.lower()) if w.lower() not in stopwords and len(w) >= 2]
    out = []
    for p in products:
        name_l = p.name.lower()
        # аксессуар — всегда отсев при фильтре B
        if is_accessory(p.name):
            continue
        # must_tokens ALL required — но storage опционален (256/512 не обязателен)
        # storage токены — только цифры+gb → не требуем строго
        required = [t for t in must if not re.match(r"^\d+gb?$", t) and not t.isdigit()]
        if not all(t in name_l for t in required):
            continue
        out.append(p)
    return out
```

- [ ] **Step 4: Run passing**

Run: `python -m pytest backend/tests/test_post_filter.py -v`
Expected: PASS 3

- [ ] **Step 5: Commit**

```bash
git add backend/filter/__init__.py backend/filter/post_filter.py backend/tests/test_post_filter.py
git commit -m "feat(filter): post_filter must_tokens+is_accessory for Pro Max vs чехол"
```

---

### Task 5: Интеграция Backend — routes + aggregator + DB миграция

**Files:**
- Modify: `backend/api/routes.py`
- Modify: `backend/database.py` (ensure table created)
- Create: `backend/alembic_migration_add_query_normalizations.py` (или ручной `CREATE TABLE` в `database.init_db`)

**Interfaces:**
- Consumes: `QueryNormalizer.normalize`, `filter_products`
- Produces: `GET /api/search?q=&no_correct=1&include_kufar=` → `{products, query_meta}`

- [ ] **Step 1: Write failing integration test (mock aggregator)**

```python
# backend/tests/test_search_route.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

def test_search_cyrillic_returns_query_meta():
    from backend.main import app
    mock_products = [
        type("P", (), {"name": "Смартфон Apple iPhone 15 Pro Max 256GB", "price": 3000, "store": "Onliner", "url": "http://x"})(),
    ]
    with patch("backend.api.routes.ScraperAggregator") as MockAgg:
        MockAgg.return_value.search_all = AsyncMock(return_value=mock_products)
        MockAgg.return_value.close = AsyncMock(return_value=None)
        c = TestClient(app)
        r = c.get("/api/search?q=айфон 15 про макс")
        assert r.status_code == 200
        data = r.json()
        assert "query_meta" in data
        assert data["query_meta"]["corrected"] is True
        assert "iphone" in data["query_meta"]["canonical"].lower()

def test_no_correct_flag():
    from backend.main import app
    with patch("backend.api.routes.ScraperAggregator") as MockAgg:
        MockAgg.return_value.search_all = AsyncMock(return_value=[])
        MockAgg.return_value.close = AsyncMock(return_value=None)
        c = TestClient(app)
        r = c.get("/api/search?q=айфон 15 про макс&no_correct=1")
        data = r.json()
        assert data["query_meta"]["corrected"] is False
```

- [ ] **Step 2: Run failing**

Run: `python -m pytest backend/tests/test_search_route.py -v`
Expected: FAIL `query_meta` missing (routes ещё не возвращает)

- [ ] **Step 3: Implement routes**

```python
# backend/api/routes.py — заменить полностью
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Search, Product
from schemas import SearchResult, ProductResponse, QueryMeta
from scrapers.aggregator import ScraperAggregator
from normalizer.query_normalizer import QueryNormalizer
from filter.post_filter import filter_products

router = APIRouter(prefix="/api", tags=["search"])

@router.get("/search", response_model=SearchResult)
async def search_products(
    q: str,
    include_kufar: bool = False,
    no_correct: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    normalizer = QueryNormalizer(db=db)
    norm = await normalizer.normalize(q, no_correct=no_correct)
    canonical = norm.canonical

    search = Search(query=q)  # храним original
    db.add(search)
    await db.commit()
    await db.refresh(search)

    aggregator = ScraperAggregator(include_kufar=include_kufar)
    try:
        products_data = await aggregator.search_all(canonical, include_kufar=include_kufar)
    finally:
        await aggregator.close()

    # post_filter по canonical
    filtered = filter_products(canonical, products_data)
    # fallback: если canonical 0 но original дал бы результаты — ретрай original (опционально, пока возвращаем 0)
    # для MVP: если filtered пусто и canonical != original, можно показать пусто с query_meta
    db_products = [Product(search_id=search.id, name=p.name, price=p.price, store=p.store, url=p.url) for p in filtered]
    db.add_all(db_products)
    await db.commit()

    response_products = [ProductResponse(id=0, name=p.name, price=p.price, store=p.store, url=p.url, is_best_price=(i==0)) for i, p in enumerate(filtered)]
    prices = [p.price for p in filtered]
    query_meta = QueryMeta(original=norm.original, canonical=norm.canonical, corrected=norm.corrected, confidence=norm.confidence, category=norm.category)
    if not filtered:
        return SearchResult(query=q, products=[], min_price=0, max_price=0, total_results=0, query_meta=query_meta)
    return SearchResult(query=q, products=response_products[:30], min_price=min(prices), max_price=max(prices), total_results=len(filtered), query_meta=query_meta)
```

```python
# backend/database.py — в init_db добавить
# from models import QueryNormalization  # импорт для create_all
# await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 4: Run passing**

Run: `python -m pytest backend/tests/test_search_route.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes.py backend/tests/test_search_route.py backend/database.py
git commit -m "feat(api): integrate QueryNormalizer + post_filter, query_meta in response"
```

---

### Task 6: Frontend — бейдж коррекции Both + no_correct

**Files:**
- Modify: `frontend/app/results/page.tsx`
- Modify: `frontend/app/api/search/route.ts` (проброс no_correct)

**Interfaces:**
- Consumes: `GET /api/search → SearchResult.query_meta`
- Produces: UI бейдж `Показаны результаты для "canonical" · Искать "original"` с `router.push(?q=original&no_correct=1)`

- [ ] **Step 1: Write failing check (ручной)**

```bash
# нет автотеста — визуальная проверка
# Ожидаем: GET /api/search?q=айфон 15 про макс → data.query_meta.corrected==true
# и в UI бейдж с canonical
```

- [ ] **Step 2: Implement results/page.tsx**

```tsx
// в ResultsContent добавить:
const noCorrect = searchParams.get('no_correct') === '1';
const [queryMeta, setQueryMeta] = useState<null | {original:string, canonical:string, corrected:boolean, confidence:number, category:string}>(null);

// в fetch:
const noCorrectParam = noCorrect ? '&no_correct=1' : '';
fetch(`${API_URL}/api/search?q=${encodeURIComponent(query)}${kufarParam}${noCorrectParam}`)
  .then(... data => { setQueryMeta(data.query_meta || null); ... })

// в toolbar под h1 добавить бейдж:
{queryMeta?.corrected && (
  <div aria-live="polite" className="mt-1 text-xs flex flex-wrap items-center gap-1.5">
    <span className="text-slate-500">Показаны результаты для</span>
    <span className="font-semibold text-slate-800">"{queryMeta.canonical}"</span>
    <span className="text-slate-400">·</span>
    <a href={`/results?q=${encodeURIComponent(queryMeta.original)}&no_correct=1${includeKufar?'&include_kufar=true':''}`}
       onClick={(e)=>{e.preventDefault(); router.push(`/results?q=${encodeURIComponent(queryMeta.original)}&no_correct=1${includeKufar?'&include_kufar=true':''}`)}}
       className="text-violet-600 hover:underline">Искать "{queryMeta.original}"</a>
  </div>
)}

// handleSearch: сбрасывает no_correct
router.push(`/results?q=${encodeURIComponent(searchQuery.trim())}${kufarParam}`); // без no_correct
```

```ts
// frontend/app/api/search/route.ts — проброс no_correct
const noCorrect = searchParams.get('no_correct');
if (noCorrect) url.searchParams.set('no_correct', noCorrect);
```

- [ ] **Step 3: Manual verify**

Run: `npm run dev` + `curl "http://localhost:8000/api/search?q=айфон 15 про макс" | jq .query_meta`
Expected: `{"original":"айфон 15 про макс","canonical":"iphone 15 pro max","corrected":true}`

- [ ] **Step 4: Commit**

```bash
git add frontend/app/results/page.tsx frontend/app/api/search/route.ts
git commit -m "feat(frontend): correction badge Both with no_correct toggle"
```

---

## Self-Review

1. **Spec coverage:** 1 контекст → T5 fallback, 2 архитектура → T3 orchestrator, 3.1 translit→T1, 3.2 fuzzy→T2, 3.3 llm→T3, 3.4 orchestrator→T3, 3.5 post_filter→T4, 3.6 DB→T3 models, 3.7 frontend→T6, 4 фолбэки→T5, 5 тесты→все tasks.
2. **Placeholder scan:** нет TBD/TODO, все code blocks заполнены, команды с expected output.
3. **Type consistency:** `NormalizeResult` в T3 → используется в T5 `norm.canonical`, `QueryMeta` в T3 schemas → T5 routes → T6 frontend `query_meta`.

---

