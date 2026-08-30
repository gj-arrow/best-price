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
        Fallback: если canonical "apple iphone ..." не дал результатов
        (сайт иногда не находит с apple+storage) — пробуем stripped.
        """
        import re

        def _strip_storage(q: str) -> str:
            return re.sub(r"\s*\d+\s*(gb|гб|гбайт|tb|тб)\b", "", q, flags=re.I).strip()

        def _queries_to_try(q: str) -> list[str]:
            qs = [q]
            no_apple = re.sub(r"\bapple\b", "", q, flags=re.I).strip()
            no_apple = re.sub(r"\s{2,}", " ", no_apple)
            if no_apple and no_apple not in qs and len(no_apple) >= 2:
                qs.append(no_apple)
            no_storage = _strip_storage(q)
            if no_storage and no_storage not in qs and len(no_storage) >= 2:
                qs.append(no_storage)
            both = _strip_storage(no_apple) if no_apple else _strip_storage(q)
            both = re.sub(r"\s{2,}", " ", both).strip()
            if both and both not in qs and len(both) >= 2:
                qs.append(both)
            return qs

        for q_try in _queries_to_try(query):
            encoded_query = q_try.replace(" ", "+")
            url = f"https://360shop.by/catalog/search?q={encoded_query}"

            html = await self._fetch(url)
            if not html:
                continue

            soup = self._parse_html(html)
            products = []

            items = soup.select("div.catalog_item.main_item_wrapper")
            for item in items[:30]:
                product = self._parse_item(item)
                if product:
                    products.append(product)

            if products:
                return products
            # если нашли 0, но страница не содержит "Сожалеем" — возможно селектор устарел, пробуем fallback
            # если содержит "Сожалеем" — товара нет, пробуем следующий q_try
        return []

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
