"""360shop.by scraper implementation."""

import re
from typing import Optional

from .base import IScraper, ProductData


class Shop360Scraper(IScraper):
    """Scraper for 360shop.by online store (Bitrix-based)."""

    store_name = "360shop.by"

    async def search(self, query: str) -> list[ProductData]:
        """
        Search for products on 360shop.by.

        Bitrix shop structure:
          div.catalog_item.main_item_wrapper.item_wrap — product container
          div.item-title a — name + URL
          span.price_value — price number
          span.price_currency — price currency
        """
        encoded_query = query.replace(" ", "+")
        url = f"https://360shop.by/catalog/search?q={encoded_query}"

        html = await self._fetch(url)
        if not html:
            return []

        soup = self._parse_html(html)
        products = []

        items = soup.select("div.catalog_item.main_item_wrapper")
        for item in items[:30]:
            product = self._parse_item(item)
            if product:
                products.append(product)

        return products

    def _parse_item(self, item) -> Optional[ProductData]:
        """Parse 360shop product item."""
        # Name from item-title
        title_elem = item.select_one("div.item-title a")
        if not title_elem:
            return None
        name = title_elem.get_text(strip=True)
        if not name:
            return None

        # URL
        url = title_elem.get("href", "")
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://360shop.by" + url

        # Price
        price = self._extract_price(item)

        return ProductData(
            name=name,
            price=price or 0.0,
            store=self.store_name,
            url=url,
        )

    def _extract_price(self, item) -> Optional[float]:
        """Extract price — span.price_value inside .js_price_wrapper."""
        price_elem = item.select_one("span.price_value")
        if not price_elem:
            return None
        text = price_elem.get_text(strip=True).replace(" ", "").replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    async def close(self) -> None:
        """Clean up resources."""
        pass
