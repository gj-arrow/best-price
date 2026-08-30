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
from .google_ai import GoogleAiScraper


class ScraperAggregator:
    """
    Aggregates multiple store scrapers for concurrent product search.

    Initializes 10 base scrapers (Onliner, WB, Ozon, Shop.by, Home1k, 360shop,
    21vek, 5element, AMD, 7745) + optional Kufar (б/у) + Google AI (РФ)
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
        self._google_ai = GoogleAiScraper()
        self._include_kufar = include_kufar

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

        strong = [w for w in query_words if re.search(r"\d", w) and re.search(r"[a-zа-яё]", w)]
        weak = [w for w in query_words if re.search(r"\d", w) and not re.search(r"[a-zа-яё]", w)]
        words = [w for w in query_words if not re.search(r"\d", w)]

        if strong:
            if not all(s in name_lower for s in strong):
                return False
            return any(w in name_lower for w in words) if words else True

        if not all(w in name_lower for w in weak):
            return False
        return any(w in name_lower for w in words) if words else True

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
        first_word = name.lower().split(maxsplit=1)[0].strip(".,;:()\"'«»") if name else ""
        if first_word in ("для", "for"):
            return True

        tokens = name.split()[:3]
        for tok in tokens:
            for sub in tok.lower().split("-"):
                word = sub.strip(".,;:()\"'«»")
                if word in ScraperAggregator._ACCESSORY_WORDS:
                    return True
        return False

    async def search_all(self, query: str, include_kufar: Optional[bool] = None, include_google_ai: bool = True) -> list[ProductData]:
        """
        Search all stores concurrently for products matching the query.
        
        Uses asyncio.gather for concurrent execution with graceful degradation.
        If a scraper fails, its results are silently skipped and other results
        are still returned. Results are sorted by price (ascending).

        Args:
            query: Search term/product name
            include_kufar: if True include Kufar.by (б/у)
            include_google_ai: if True include Google AI (РФ) estimate
            
        Returns:
            List of ProductData objects from all stores, sorted by price
        """
        # Resolve include_kufar (method param overrides constructor default)
        use_kufar = include_kufar if include_kufar is not None else self._include_kufar

        # Extract significant query words for relevance filtering
        query_words = self._extract_query_words(query)

        # Create search tasks for all scrapers (+ optional Kufar + Google AI)
        scrapers_to_run = list(self.scrapers)
        if use_kufar:
            scrapers_to_run.append(self._kufar)
        # Google AI (РФ) — всегда пробуем, быстрый фолбэк ~6с
        # Не блокируем основной поиск: запускаем параллельно
        if include_google_ai:
            scrapers_to_run.append(self._google_ai)
        search_tasks = [scraper.search(query) for scraper in scrapers_to_run]

        # Execute all searches concurrently with graceful degradation
        results = await asyncio.gather(*search_tasks, return_exceptions=True)

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
        all_products.sort(key=lambda p: (self._is_accessory(p), p.price))
        seen_stores: set[str] = set()
        deduped: list[ProductData] = []
        for p in all_products:
            if p.store not in seen_stores:
                seen_stores.add(p.store)
                deduped.append(p)

        # Present results to the user ordered by price (cheapest first),
        # regardless of the accessory tier used for dedup selection.
        deduped.sort(key=lambda p: p.price)
        return deduped

    async def close(self) -> None:
        """Clean up resources for all scrapers."""
        all_scrapers = list(self.scrapers) + [self._kufar, self._google_ai]
        await asyncio.gather(
            *[scraper.close() for scraper in all_scrapers],
            return_exceptions=True
        )
