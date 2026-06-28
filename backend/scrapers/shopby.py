"""Shop.by scraper implementation."""

import re
from typing import Optional

from .base import IScraper, ProductData


class ShopByScraper(IScraper):
    """Scraper for Shop.by price aggregator.

    Shop.by is a Belarusian price aggregator (like Onliner and 1k.by). Its
    search endpoint is `https://shop.by/find/?findtext=...` (GET, discovered
    from the homepage `<form action="/find/" method="get">` with an
    `<input name="findtext">`). The page is SERVER-SIDE RENDERED — no JS
    needed. (Earlier note that it was a "JS SPA" was wrong: that conclusion
    came from probing `/search/?q=`, an endpoint Shop.by does not use, which
    redirects to the homepage. The real endpoint `/find/?findtext=` returns
    product cards directly in the HTML.)

    Each result card shows a product MODEL with the minimum price across all
    offers ("1 499,00 p." — space is the thousands separator, comma the
    decimal). Currency is BYN ("p." = рублей).
    """

    store_name = "Shop.by"

    async def search(self, query: str) -> list[ProductData]:
        """Search for products on Shop.by.

        Selectors (verified against live HTML):
          div.ModelList__ModelBlockItem   — card container
          a.ModelList__LinkModel          — product name + relative URL (href)
          span.PriceBlock__PriceValue     — min price, e.g. "1 499,00 p."
        """
        encoded_query = query.replace(" ", "+")
        url = f"https://shop.by/find/?findtext={encoded_query}"

        html = await self._fetch(url)
        if not html:
            return []

        soup = self._parse_html(html)
        products: list[ProductData] = []

        # Each card has 2 elements carrying ModelList__LinkModel: the real
        # <a> (with href + name) and a <span> image wrapper. Select anchors.
        for card in soup.select("div.ModelList__ModelBlockItem")[:30]:
            product = self._parse_card(card)
            if product:
                products.append(product)

        return products

    def _parse_card(self, card) -> Optional[ProductData]:
        """Parse a Shop.by model card into a ProductData."""
        link = card.select_one("a.ModelList__LinkModel")
        if link is None:
            return None

        name = link.get_text(" ", strip=True)
        if not name or len(name) < 3:
            return None

        href = link.get("href", "")
        if href.startswith("//"):
            url = "https:" + href
        elif href.startswith("/"):
            url = "https://shop.by" + href
        else:
            url = href

        price = self._parse_price(card)

        return ProductData(
            name=name,
            price=price or 0.0,
            store=self.store_name,
            url=url,
        )

    def _parse_price(self, card) -> Optional[float]:
        """Extract the min offer price from the card's PriceBlock.

        Renders as '1 499,00 p.' — drop spaces (thousands grouping), convert
        the comma decimal separator to a dot.
        """
        price_elem = card.select_one("span.PriceBlock__PriceValue")
        if price_elem is None:
            return None
        text = price_elem.get_text(" ", strip=True)
        match = re.search(r"\d[\d\s\u00A0]*[.,]\d{1,2}", text)
        if not match:
            return None
        raw = (
            match.group(0)
            .replace(" ", "")
            .replace("\u00A0", "")
            .replace(",", ".")
        )
        try:
            return float(raw)
        except ValueError:
            return None

    async def close(self) -> None:
        """Clean up resources."""
        pass
