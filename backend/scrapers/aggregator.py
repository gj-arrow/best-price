"""Scraper aggregator for concurrent multi-store product search."""

import asyncio
import re
from typing import Optional

from .base import ProductData
from .onliner import OnlinerScraper
from .wildberries import WildberriesScraper
from .ozon import OzonScraper
from .shopby import ShopByScraper
from .home1k import Home1kScraper
from .shop360 import Shop360Scraper
from .v21vek import V21VekScraper
from .kufar import KufarScraper
from .five_element import FiveElementScraper
from .amd import AmdScraper
from .shop7745 import Shop7745Scraper


class ScraperAggregator:
    """
    Aggregates multiple store scrapers for concurrent product search.

    Initializes 10 base scrapers (Onliner, WB, Ozon, Shop.by, Home1k, 360shop,
    21vek, 5element, AMD, 7745) + optional Kufar (б/у)
    and provides unified search interface with concurrent execution.
    """

    def __init__(self, include_kufar: bool = False):
        """Initialize scrapers.

        Args:
            include_kufar: if True, include Kufar.by (used goods) in search.
                           Kufar is opt-in via the "Добавить Kufar" button
                           because many users don't want б/у items.
        """
        self.scrapers = [
            OnlinerScraper(),
            WildberriesScraper(),
            OzonScraper(),
            ShopByScraper(),
            Home1kScraper(),
            Shop360Scraper(),
            V21VekScraper(),
            FiveElementScraper(),
            AmdScraper(),
            Shop7745Scraper(),
        ]
        self._kufar = KufarScraper()
        self._include_kufar = include_kufar
        self._last_debug: list[dict] = []

    @staticmethod
    def _extract_query_words(query: str) -> list[str]:
        """Extract significant words from user query (≥2 chars, skip stopwords)."""
        stopwords = frozenset({
            "для", "на", "от", "с", "и", "в", "по", "у", "о", "из", "к", "за",
            "без", "до", "про", "через", "под", "над", "об", "не", "или",
            "for", "with", "and", "the", "to", "of", "in", "from", "by", "at", "on",
        })
        return [w.lower() for w in query.split()
                if len(w) >= 2 and w.lower() not in stopwords]

    @staticmethod
    def _is_relevant(product: ProductData, query_words: list[str]) -> bool:
        """Check product name matches the query using model-token logic.

        Query tokens are split into:
          - strong model IDs: contain BOTH letters and digits
            (e.g. "af-ze7226-a", "a55pro") — unique enough to identify the
            product on their own; sellers often omit the brand word.
          - weak model tokens: digits only (e.g. "55") — not unique.
          - word tokens: no digits (brand / category, e.g. "roome", "air").

        Rule:
          - If the query has strong model IDs, ALL of them must be present in
            the product name, plus at least one word token (blocks pure
            accessory matches like "Чехол для AF-ZE7226-A").
          - Otherwise require all weak model tokens and at least one word
            token (if any words exist).

        This is more permissive than the old "all query words required" rule:
        Wildberries lists "Аэрогриль Air Fry AF-ZE7226-A" (no "Roome" brand)
        which the old rule dropped — costing real matches. The strong-ID
        check still rejects unrelated junk (homepage recommendations Ozon
        serves under anti-bot) because those names lack the model ID.
        """
        if not query_words:
            return True

        name_lower = product.name.lower()
        # нормализуем для storage типа "256 гб" vs "256gb" и размеров "45 мм" vs "45mm" (cyrillic → latin)
        name_lower_norm = name_lower.replace("гб", "gb").replace("гбайт", "gb").replace("мм", "mm").replace("см", "cm")
        name_nospace = re.sub(r"[^a-zа-яё0-9]", "", name_lower_norm).replace("мм", "mm")

        def _contains_word(haystack: str, needle: str) -> bool:
            # граница слова: через \b, чтобы "15" не матчило "150", "max" не матчило "maxi"
            return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None

        # бренд-специфика: если ищут iphone — в товаре должен быть iphone, иначе Xiaomi с pro max пролезет
        if "iphone" in query_words and not _contains_word(name_lower, "iphone"):
            return False

        # storage типа "256gb"/"256 гб" — не модель, не требуем строго, иначе 5element отдаёт Xiaomi с 256gb
        def _is_storage_token(t: str) -> bool:
            return bool(re.match(r"^\d+\s*(gb|гб|гбайт|tb|тб)$", t.lower().replace(" ", "")))

        strong = [w for w in query_words if re.search(r"\d", w) and re.search(r"[a-zа-яё]", w) and not _is_storage_token(w)]
        weak = [w for w in query_words if re.search(r"\d", w) and not re.search(r"[a-zа-яё]", w)]
        words = [w for w in query_words if not re.search(r"\d", w)]

        if strong:
            for s in strong:
                s_norm = s.lower().replace("гб", "gb").replace("гбайт", "gb").replace("мм", "mm").replace("см", "cm")
                s_nospace = re.sub(r"[^a-zа-яё0-9]", "", s_norm).replace("мм", "mm")
                has = _contains_word(name_lower, s.lower()) or _contains_word(name_lower_norm, s_norm) or s_nospace in name_nospace
                # также матчим 45mm → 45 мм (разнесённые токены)
                if not has and re.match(r"^\d+mm$", s_nospace):
                    num = re.match(r"^(\d+)mm$", s_nospace).group(1)
                    has = _contains_word(name_lower_norm, num) and "mm" in name_lower_norm
                # storage: "256gb" должен матчить "256 гб" / "256 gb" — уже покрыто nospace/norm
                if not has:
                    return False
            return any(_contains_word(name_lower, w) or _contains_word(name_lower_norm, w) for w in words) if words else True

        if weak and not all(_contains_word(name_lower, w) for w in weak):
            return False
        return any(_contains_word(name_lower, w) for w in words) if words else True

    # Russian words that mark a listing as an ACCESSORY or SPARE PART to the
    # query's device, not the device itself. Checked against the first few
    # tokens of the product name (its category noun / descriptors), so
    # "Чехол для Xiaomi Redmi Note 12", "Аккумулятор ... совместим с Xiaomi"
    # and "6.67-дюймовый OEM-экран для Redmi Note 12" are all flagged, while
    # "Смартфон Xiaomi Redmi Note 12" and "Аэрогриль Roome Air Fry ..." are not.
    _ACCESSORY_WORDS = frozenset({
        # protective / carrying accessories
        "чехол", "чехла", "пленка", "пленки", "защитная", "защитный",
        "защитное", "стекло", "бампер", "стикер", "наклейка", "сумка",
        "ремешок", "браслет", "кольцо", "брелок",
        # power / connectivity accessories
        "кабель", "зарядное", "зарядный", "зарядка", "адаптер",
        "переходник", "пульт", "картридж", "фильтр",
        # spare parts / repair components
        "аккумулятор", "экран", "дисплей", "матрица", "модуль", "шлейф",
        "разъем", "динамик", "камера", "кнопка", "плата", "блок",
        # compatibility / replacement markers (accessory, not the device)
        "совместим", "замена", "ремонт", "oem",
        # stands / holders
        "подставка", "держатель",
    })

    @staticmethod
    def _is_accessory(product: ProductData) -> bool:
        """True if the product name reads as an accessory / spare part for
        the queried device rather than the device itself.

        Signals:
          - Name starts with "для"/"for" — always an "для [device]" accessory
            listing (the device itself never starts with "for").
          - An accessory word appears among the FIRST THREE name tokens
            (the category noun plus size/spec descriptors). Tokens are split
            on whitespace and hyphens, so "6.67-дюймовый OEM-экран для Redmi
            Note 12" is caught via the "oem"/"экран" sub-tokens.
        """
        name = product.name.strip()
        lowers = name.lower()
        # если в первых 4 токенах есть "для"/"for" — это аксессуар "X для Y"
        first_tokens = [t.strip(".,;:()\"'«»").lower() for t in name.split()[:4]]
        if "для" in first_tokens or "for" in first_tokens:
            return True
        if lowers.startswith("для ") or lowers.startswith("for "):
            return True

        tokens = name.split()[:3]
        for tok in tokens:
            for sub in tok.lower().split("-"):
                word = sub.strip(".,;:()\"'«»")
                if word in ScraperAggregator._ACCESSORY_WORDS:
                    return True
        return False

    async def search_all(self, query: str, include_kufar: Optional[bool] = None) -> list[ProductData]:
        """
        Search all stores concurrently for products matching the query.
        
        Uses asyncio.gather for concurrent execution with graceful degradation.
        If a scraper fails, its results are silently skipped and other results
        are still returned. Results are sorted by price (ascending).

        Args:
            query: Search term/product name
            include_kufar: if True include Kufar.by (б/у)
            
        Returns:
            List of ProductData objects from all stores, sorted by price
        """
        # Resolve include_kufar (method param overrides constructor default)
        use_kufar = include_kufar if include_kufar is not None else self._include_kufar

        # Extract significant query words for relevance filtering
        query_words = self._extract_query_words(query)

        # Create search tasks for all scrapers (+ optional Kufar)
        scrapers_to_run = list(self.scrapers)
        if use_kufar:
            scrapers_to_run.append(self._kufar)
        search_tasks = [scraper.search(query) for scraper in scrapers_to_run]

        # Execute all searches concurrently with graceful degradation
        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Build per-store debug: ok / empty / error with counts
        self._last_debug = []
        for scraper, result in zip(scrapers_to_run, results):
            store = getattr(scraper, "store_name", scraper.__class__.__name__)
            if isinstance(result, Exception):
                self._last_debug.append({"store": store, "status": "error", "found": 0, "error": str(result)[:300]})
                continue
            if not isinstance(result, list):
                self._last_debug.append({"store": store, "status": "empty", "found": 0})
                continue
            # count raw and relevant
            relevant = [p for p in result if p.price > 0 and self._is_relevant(p, query_words)]
            if not result:
                self._last_debug.append({"store": store, "status": "empty", "found": 0})
            elif not relevant:
                # searched ok but nothing relevant (товара нет)
                self._last_debug.append({"store": store, "status": "empty", "found": 0})
            else:
                # есть релевантные, но после dedup может остаться 0 аксессуаров? считаем ok
                self._last_debug.append({"store": store, "status": "ok", "found": len(relevant)})

        # Flatten results, filtering out exceptions, None values, zero prices,
        # and irrelevant products (accessories, wrong models)
        all_products: list[ProductData] = []
        for result in results:
            if isinstance(result, Exception):
                # Graceful degradation: skip failed scrapers
                continue
            if isinstance(result, list):
                for p in result:
                    if p.price > 0 and self._is_relevant(p, query_words):
                        all_products.append(p)

        # Per store, prefer the cheapest NON-ACCESSORY match (the device
        # the user searched for). Only fall back to accessories if a store
        # lists nothing else. Sort key: (is_accessory, price) → non-
        # accessories sort first, then by price within each tier.
        # Kufar is a marketplace — keep multiple listings (up to 10), not 1 per store.
        all_products.sort(key=lambda p: (self._is_accessory(p), p.price))
        seen_stores: set[str] = set()
        deduped: list[ProductData] = []
        kufar_keep = 10
        kufar_added = 0
        for p in all_products:
            is_kufar = p.store == self._kufar.store_name
            if is_kufar:
                if kufar_added < kufar_keep:
                    deduped.append(p)
                    kufar_added += 1
                continue
            if p.store not in seen_stores:
                seen_stores.add(p.store)
                deduped.append(p)

        # Present results to the user ordered by price (cheapest first),
        # regardless of the accessory tier used for dedup selection.
        # Keep Kufar listings sorted by price among themselves
        deduped.sort(key=lambda p: p.price)
        return deduped

    async def close(self) -> None:
        """Clean up resources for all scrapers."""
        all_scrapers = list(self.scrapers) + [self._kufar]
        await asyncio.gather(
            *[scraper.close() for scraper in all_scrapers],
            return_exceptions=True
        )
