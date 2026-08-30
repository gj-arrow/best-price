"""AMD.by scraper — sphinx autocomplete endpoint (без браузера!).

AMD.by main site is protected by hg-security JS challenge, and the regular
search page (/search/?search=...) has a broken/full-text index that returns
"Показано с 0 по 0 из 0" for EVERY query. The working search is the sphinx
autocomplete endpoint:

    https://www.amd.by/index.php?route=extension/module/sphinxautocomplete&search=<query>

It's SSR HTML (no hg-security on it), works with plain aiohttp, and returns
classic OpenCart-ish blocks:
  div.row > div.search-prod-details > a.search-prod-name (name + URL)
  div.row > div.search-prod-details-price > .price-tov > .new-price (e.g. "5 632.84 ƃ")

Prices are in BYN (ƃ = Belarusian ruble).
"""

import re
from typing import Optional

from .base import IScraper, ProductData


class AmdScraper(IScraper):
    store_name = "AMD.by"

    async def _get_session(self):
        """sphinx autocomplete требует X-Requested-With: XMLHttpRequest — иначе redirect loop."""
        if self._session is None or self._session.closed:
            from .base import BROWSER_HEADERS, SSL_CONTEXT
            import aiohttp
            headers = dict(BROWSER_HEADERS)
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Accept"] = "text/html,*/*"
            self._session = aiohttp.ClientSession(
                headers=headers,
                connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
            )
        return self._session

    async def search(self, query: str) -> list[ProductData]:
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

        # sphinx autocomplete ищет по всем словам — оригинальный запрос обычно сразу работает
        queries = _queries_to_try(query)[:2]
        for q_try in queries:
            url = (
                "https://www.amd.by/index.php?route=extension/module/sphinxautocomplete"
                f"&search={q_try.replace(' ', '+')}"
            )
            html = await self._fetch(url, timeout=10)
            if not html:
                continue
            products = self._parse_html_content(html)
            if products:
                return products[:30]
        return []

    def _parse_html_content(self, html: str) -> list[ProductData]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        products: list[ProductData] = []
        items = soup.select(".search-prod-details")
        for item in items[:30]:
            prod = self._parse_item(item)
            if prod:
                products.append(prod)
        return products

    def _parse_item(self, item) -> Optional[ProductData]:
        link = item.select_one(".search-prod-name")
        if not link:
            return None
        name = link.get_text(strip=True)
        if not name or len(name) < 5:
            return None
        href = link.get("href", "")
        if href.startswith("/"):
            href = "https://www.amd.by" + href

        price = self._extract_price(item)
        if price is None or price <= 0:
            return None
        return ProductData(name=name.strip(), price=price, store=self.store_name, url=href)

    def _extract_price(self, item) -> Optional[float]:
        """Price is in the parent .row container: .search-prod-details-price .new-price.

        Text like "5 632.84 ƃ" (BYN). Take the first number.
        """
        # climb to .row (the block containing both details and price)
        row = item
        for _ in range(4):
            row = row.parent
            if row is None:
                return None
            if row.get("class") and "row" in row.get("class"):
                break
        price_el = row.select_one(".new-price") if row is not None else None
        if not price_el:
            return None
        text = price_el.get_text(strip=True)
        text = text.replace("\u00a0", " ").replace(" ", "")
        m = re.search(r"(\d+(?:[.,]\d+)?)", text)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None

    async def close(self) -> None:
        await super().close()