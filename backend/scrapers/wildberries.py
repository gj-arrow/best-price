"""Wildberries.ru scraper implementation.

Uses curl_cffi to impersonate a real browser TLS fingerprint,
bypassing Wildberries' WAF (which blocks standard HTTP clients with 498).

NB: WB prices are in RUB, they get converted to BYN via a hardcoded rate.
"""

import asyncio
import time
from typing import Optional

from .base import IScraper, ProductData

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    from utils.currency import get_rub_to_byn_sync
except ModuleNotFoundError:
    from backend.utils.currency import get_rub_to_byn_sync  # type: ignore

FALLBACK_RUB_TO_BYN = 0.035617


class WildberriesScraper(IScraper):
    """Scraper for Wildberries.ru via their internal search API."""

    store_name = "Wildberries"

    async def search(self, query: str) -> list[ProductData]:
        """
        Search products via Wildberries' internal JSON API.

        Uses curl_cffi with Chrome 124 impersonation to bypass WAF.
        curl_cffi calls are run in a thread executor to avoid blocking.
        """
        products = await asyncio.to_thread(self._search_sync, query)
        return products

    def _search_sync(self, query: str) -> list[ProductData]:
        """Synchronous search — runs in thread pool."""
        if not HAS_CURL_CFFI:
            return []

        # Wildberries exactmatch is flaky with canonical "apple iphone 17 pro max 256gb"
        # (apple + storage). Если первый запрос вернул 0 — пробуем stripped варианты.
        # Порядок: оригинал → без apple → без storage → без обоих (iphone 17 pro max)
        import re

        def _strip_storage(q: str) -> str:
            return re.sub(r"\s*\d+\s*(gb|гб|гбайт|tb|тб)\b", "", q, flags=re.I).strip()

        def _queries_to_try(q: str) -> list[str]:
            qs = [q]
            no_apple = re.sub(r"\bapple\b", "", q, flags=re.I).strip()
            no_apple = re.sub(r"\s{2,}", " ", no_apple)
            if no_apple and no_apple not in qs:
                qs.append(no_apple)
            no_storage = _strip_storage(q)
            if no_storage and no_storage not in qs:
                qs.append(no_storage)
            both = _strip_storage(no_apple) if no_apple else _strip_storage(q)
            both = re.sub(r"\s{2,}", " ", both).strip()
            if both and both not in qs:
                qs.append(both)
            # гарантируем минимум "iphone 17 pro max"
            return qs

        # небольшой stagger для burst 11 scrapers
        import random
        time.sleep(random.uniform(0.1, 0.6))
        # пробуем до 2 вариантов: оригинал и stripped без apple/storage (fallback быстрый)
        queries = _queries_to_try(query)[:2]
        for q_try in queries:
            encoded = q_try.replace(" ", "%20")
            url = (
                "https://search.wb.ru/exactmatch/ru/common/v9/search"
                f"?ab_testing=false&appType=1&curr=rub"
                f"&dest=-1257786"
                f"&query={encoded}"
                f"&resultset=catalog&sort=popular&spp=0&suppressSpellcheck=false"
            )
            data = None
            for attempt in range(2):
                try:
                    resp = curl_requests.get(url, impersonate="chrome124", timeout=8)
                    if resp.status_code == 200:
                        data = resp.json()
                        break
                    if resp.status_code in (429, 500, 502, 503) and attempt < 1:
                        time.sleep(1.0)
                        continue
                    break
                except Exception:
                    if attempt < 1:
                        time.sleep(0.7)
                        continue
                    break
            if data is None:
                continue
            raw_products = data.get("products", [])
            if raw_products:
                results: list[ProductData] = []
                for p in raw_products[:30]:
                    name = p.get("name", "").strip()
                    if not name:
                        continue
                    price = 0.0
                    sizes = p.get("sizes", [])
                    if sizes and "price" in sizes[0]:
                        price_kopeks = sizes[0]["price"].get("product") or sizes[0]["price"].get("basic", 0)
                        if price_kopeks:
                            price = (price_kopeks / 100.0) * get_rub_to_byn_sync()
                    nm_id = p.get("id")
                    url_p = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx" if nm_id else ""
                    results.append(ProductData(name=name, price=round(price, 2), store=self.store_name, url=url_p))
                if results:
                    return results
        return []

    async def close(self) -> None:
        """Clean up resources."""
        pass
