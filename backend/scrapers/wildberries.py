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

# Approximate conversion rate: 1 BYN ≈ 25.8 RUB (updated periodically)
RUB_TO_BYN = 0.0388


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

        encoded = query.replace(" ", "%20")
        url = (
            "https://search.wb.ru/exactmatch/ru/common/v9/search"
            f"?ab_testing=false&appType=1&curr=rub"
            f"&dest=-1257786"
            f"&query={encoded}"
            f"&resultset=catalog&sort=popular&spp=0&suppressSpellcheck=false"
        )

        # WB rate-limits (429) under burst traffic. Retry up to 3 times with
        # a short backoff so a single user search survives a transient block.
        data = None
        for attempt in range(3):
            try:
                resp = curl_requests.get(url, impersonate="chrome124", timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                if resp.status_code == 429 and attempt < 2:
                    time.sleep(2 * (attempt + 1))  # 2s, 4s
                    continue
                return []
            except Exception:
                return []

        if data is None:
            return []

        raw_products = data.get("products", [])

        results: list[ProductData] = []
        for p in raw_products[:30]:
            name = p.get("name", "").strip()
            if not name:
                continue

            # Price is in sizes[0]["price"]["product"] (kopeks)
            price = 0.0
            sizes = p.get("sizes", [])
            if sizes and "price" in sizes[0]:
                price_kopeks = sizes[0]["price"].get("product") or sizes[0]["price"].get("basic", 0)
                if price_kopeks:
                    # Convert from RUB kopeks → BYN
                    price = (price_kopeks / 100.0) * RUB_TO_BYN

            nm_id = p.get("id")
            url = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx" if nm_id else ""

            results.append(ProductData(
                name=name,
                price=round(price, 2),
                store=self.store_name,
                url=url,
            ))

        return results

    async def close(self) -> None:
        """Clean up resources."""
        pass
