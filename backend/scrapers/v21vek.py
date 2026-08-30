"""21vek.by scraper via gate search-composer suggest API."""

import json
import re
from typing import Optional
from urllib.parse import quote_plus

from .base import IScraper, ProductData


class V21VekScraper(IScraper):
    """Scraper for 21vek.by online hypermarket.

    21vek is Next.js + SSR with client hydration; product listing is not in
    static HTML. The public autocomplete API provides product suggestions with
    name, url and price and is sufficient for price comparison:

        GET https://gate.21vek.by/search-composer/api/v1/search/suggest
            ?query=<query>&mode=desktop

    Response: {"data":[{"group_type":"products","items":[...]}]}
    each item: {"name": "...", "url": "/mobile/...html", "price": "1 249,00 Ҕ"}
    """

    store_name = "21vek.by"

    async def search(self, query: str) -> list[ProductData]:
        encoded = quote_plus(query)
        url = f"https://gate.21vek.by/search-composer/api/v1/search/suggest?query={encoded}&mode=desktop"

        # Use shared session but with gate-specific referer/origin
        session = await self._get_session()
        headers = {
            "Referer": f"https://www.21vek.by/search/?q={encoded}",
            "Origin": "https://www.21vek.by",
            "Accept": "application/json, text/plain, */*",
        }
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
                data = json.loads(text)
        except Exception as e:
            print(f"21vek fetch failed for {query}: {e}")
            return []

        products: list[ProductData] = []
        try:
            for group in data.get("data", []):
                if group.get("group_type") != "products":
                    continue
                for item in group.get("items", [])[:30]:
                    prod = self._parse_item(item)
                    if prod:
                        products.append(prod)
                break  # only first products group
        except Exception as e:
            print(f"21vek parse failed: {e}")
            return []

        return products

    def _parse_item(self, item: dict) -> Optional[ProductData]:
        name = (item.get("name") or "").strip()
        if not name:
            return None

        rel_url = item.get("url") or ""
        if rel_url.startswith("/"):
            url = "https://www.21vek.by" + rel_url
        elif rel_url.startswith("http"):
            url = rel_url
        else:
            url = "https://www.21vek.by/" + rel_url

        price = self._parse_price(item.get("price"))
        if price is None or price <= 0:
            return None

        return ProductData(
            name=name,
            price=price,
            store=self.store_name,
            url=url,
        )

    def _parse_price(self, raw: Optional[str]) -> Optional[float]:
        if not raw:
            return None
        # "1 249,00 Ҕ" -> "1249.00"
        text = raw.strip()
        # remove currency glyphs and spaces
        text = text.replace("Ҕ", "").replace("р.", "").strip()
        text = text.replace("\u00a0", " ").replace(" ", "")
        text = text.replace(",", ".")
        # keep only digits and dot
        text = re.sub(r"[^0-9.]", "", text)
        try:
            return float(text) if text else None
        except ValueError:
            return None
