"""Kufar.by scraper via public search API (used goods + new)."""

import json
from typing import Optional
from urllib.parse import quote

from .base import IScraper, ProductData


class KufarScraper(IScraper):
    """Scraper for Kufar.by classifieds.

    Public API:
        GET https://api.kufar.by/search-api/v1/search/rendered-paginated
            ?query=<query>&lang=ru&size=30

    Response: {"ads": [{"subject": "...", "ad_link": "...",
                        "price_byn": "24000", "ad_parameters": [...]}, ...]}
    price_byn is in kopecks (1 BYN = 100). 0 means "price not specified / negotiable".
    Condition is in ad_parameters: p == "condition" -> vl == "Б/у" or "Новый".

    Kufar products are marked with " (б/у)" suffix when condition is Б/у
    so the frontend can distinguish used items.
    """

    store_name = "Kufar.by"

    async def search(self, query: str) -> list[ProductData]:
        encoded = quote(query)
        # lang=ru is required, size=30 matches aggregator limit
        url = f"https://api.kufar.by/search-api/v1/search/rendered-paginated?query={encoded}&lang=ru&size=30"

        session = await self._get_session()
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
                data = json.loads(text)
        except Exception as e:
            print(f"Kufar fetch failed for {query}: {e}")
            return []

        ads = data.get("ads") or []
        products: list[ProductData] = []
        for ad in ads[:30]:
            prod = self._parse_ad(ad)
            if prod:
                products.append(prod)

        return products

    def _parse_ad(self, ad: dict) -> Optional[ProductData]:
        name = (ad.get("subject") or "").strip()
        if not name:
            return None

        # Skip ads without price (price_byn == "0" or missing)
        price_byn_raw = ad.get("price_byn")
        if price_byn_raw is None:
            return None
        try:
            price_kopecks = int(str(price_byn_raw).strip())
        except (ValueError, TypeError):
            return None
        if price_kopecks <= 0:
            return None
        price = price_kopecks / 100.0

        url = ad.get("ad_link") or ""
        if not url:
            return None

        # Detect condition: Б/у vs Новый
        condition = None
        for param in ad.get("ad_parameters") or []:
            if param.get("p") == "condition":
                condition = param.get("vl")
                break

        # Mark used items so user sees it's б/у
        if condition == "Б/у":
            # avoid double suffix if already in name
            if "(б/у)" not in name.lower():
                name = f"{name} (б/у)"

        return ProductData(
            name=name,
            price=price,
            store=self.store_name,
            url=url,
        )
