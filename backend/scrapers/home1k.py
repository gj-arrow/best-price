"""1k.by / Home.1k.by scraper implementation."""

import re
from typing import Optional

from .base import IScraper, ProductData


class Home1kScraper(IScraper):
    """Scraper for 1k.by / home.1k.by price aggregator.

    1k.by is a Belarusian price aggregator (like Onliner). Its search page
    (`https://1k.by/products/search?s_keywords=...`) is server-side rendered
    and lists product cards. Each card shows the product name/link and a
    PRICE RANGE ("239,00 – 379,00б.р.") spanning all stores — we take the
    minimum (cheapest offer) for comparison. Currency is BYN ("б.р." =
    белорусских рублей).
    """

    store_name = "1k.by"

    async def search(self, query: str) -> list[ProductData]:
        """Search for products on 1k.by.

        Selectors (verified against live HTML):
          a.prod__link   — product name + URL (href is absolute)
          div.prod__price — "239,00 – 379,00б.р.Сравнить все цены"
        """
        encoded_query = query.replace(" ", "+")
        url = f"https://1k.by/products/search?s_keywords={encoded_query}"

        html = await self._fetch(url)
        if not html:
            return []

        soup = self._parse_html(html)
        products = []

        for link in soup.select("a.prod__link")[:30]:
            product = self._parse_card(link)
            if product:
                products.append(product)

        return products

    def _parse_card(self, link_elem) -> Optional[ProductData]:
        """Parse a 1k.by product card from its name link element."""
        name = link_elem.get_text(strip=True)
        if not name or len(name) < 3:
            return None

        url = link_elem.get("href", "")
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://1k.by" + url

        # Price lives in a sibling/cousin div.prod__price within the card.
        # Walk up to the nearest ancestor that contains the price element.
        price = self._find_price(link_elem)

        return ProductData(
            name=name,
            price=price or 0.0,
            store=self.store_name,
            url=url,
        )

    def _find_price(self, link_elem) -> Optional[float]:
        """Find the card's price element and return the minimum offer price.

        1k.by renders a price range: '239,00 – 379,00б.р.Сравнить все цены'.
        We take the FIRST number (cheapest offer). Walk up from the name link
        to locate the shared card ancestor that also holds div.prod__price.
        """
        node = link_elem
        for _ in range(8):
            node = node.parent
            if node is None:
                break
            price_elem = node.select_one("div.prod__price")
            if price_elem:
                text = price_elem.get_text(" ", strip=True)
                # First number before the range dash / currency marker.
                # Handles comma decimal separators and nbsp/space grouping.
                match = re.search(r"\d[\d\s\u00A0]*[.,]\d{1,2}", text)
                if not match:
                    return None
                raw = match.group(0).replace(" ", "").replace("\u00A0", "").replace(",", ".")
                try:
                    return float(raw)
                except ValueError:
                    return None
        return None

    async def close(self) -> None:
        """Clean up resources."""
        pass
