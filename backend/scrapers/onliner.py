"""Onliner.by scraper implementation."""

import re
from typing import Optional

from .base import IScraper, ProductData


class OnlinerScraper(IScraper):
    """Scraper for Onliner.by electronics aggregator."""

    store_name = "Onliner.by"

    async def search(self, query: str) -> list[ProductData]:
        """
        Search for products on Onliner.by.

        Onliner SSR-renders search results with BEM classes:
          .catalog-form__offers-unit_primary  — product container
          h3.catalog-form__description a      — name + link
          .catalog-form__description_huge-additional — price "от1368,70 ƃ"
        """
        encoded_query = query.replace(" ", "+")
        url = f"https://catalog.onliner.by/search?q={encoded_query}"

        html = await self._fetch(url)
        if not html:
            return []

        soup = self._parse_html(html)
        products = []

        units = soup.select("div.catalog-form__offers-unit_primary")
        for unit in units[:30]:
            product = self._parse_unit(unit)
            if product:
                products.append(product)

        return products

    def _parse_unit(self, unit) -> Optional[ProductData]:
        """Parse a single Onliner product unit."""
        # Name from h3 > a
        name_elem = unit.select_one("h3.catalog-form__description a[href]")
        if not name_elem:
            return None
        name = name_elem.get_text(strip=True)
        if not name:
            return None

        # URL from the same link
        url = name_elem.get("href", "")
        if url.startswith("//"):
            url = "https:" + url

        # Price from .catalog-form__description_huge-additional
        price = self._extract_price(unit)

        return ProductData(
            name=name,
            price=price or 0.0,
            store=self.store_name,
            url=url,
        )

    def _extract_price(self, unit) -> Optional[float]:
        """Extract the minimum offer price.

        Onliner lists two prices in one element: the 'от' (from / min) price
        and a higher reference price, separated by the BYN glyph 'ƃ':
            'от239,00 ƃ289,00 ƃ'
        We take the FIRST number (the min offer price) — the one that matters
        for comparison. Previously the two numbers were concatenated into
        '239.00289.00', float() failed, and the product was dropped by the
        aggregator's price>0 filter.
        """
        price_elem = unit.select_one("div.catalog-form__description_huge-additional")
        if not price_elem:
            return None

        # separator=" " keeps adjacent text nodes from fusing numbers;
        # split on the currency glyph to isolate the first price chunk.
        text = price_elem.get_text(separator=" ", strip=True)
        first_segment = text.split("ƃ")[0]

        # First number in the chunk — tolerates 'от' prefix, thousand
        # separators (spaces / nbsp) and comma decimal separators.
        match = re.search(r"\d[\d\s]*[.,]?\d*", first_segment)
        if not match:
            return None

        raw = match.group(0).replace(" ", "").replace("\u00A0", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None

    async def close(self) -> None:
        """Clean up resources."""
        pass
