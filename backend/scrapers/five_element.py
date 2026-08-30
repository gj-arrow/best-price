"""5element.by scraper via Playwright (Diginetica suggestions)."""

import re
import json
from typing import Optional

from .base import BrowserScraper, ProductData, _get_browser, _release_browser


class FiveElementScraper(BrowserScraper):
    """Scraper for 5element.by (JS-heavy, Diginetica).

    Search is JS-driven: typing in `input[placeholder*="Поиск товара"]`
    loads suggestions via Diginetica with embedded JSON containing
    product `name` and `price`. Full catalog search via GET is not SSR
    (`/catalog?search=` returns generic catalog without filtering).
    So we use a real browser to trigger the suggestion and parse the
    resulting HTML for product JSON.
    """

    store_name = "5element.by"

    async def search(self, query: str) -> list[ProductData]:
        browser = await _get_browser()
        page = None
        try:
            page = await browser.new_page()
            # hide webdriver flag (helps with anti-bot)
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            await page.goto("https://5element.by/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)

            # locate search input
            inp = page.locator('input[placeholder*="Поиск товара"]')
            if await inp.count() == 0:
                inp = page.locator('input[placeholder*="Поиск"]')
            if await inp.count() == 0:
                return []
            await inp.first.click()
            await inp.first.fill(query)
            await page.wait_for_timeout(4000)

            html = await page.content()
            # The page after typing contains JSON blobs like:
            # "name":"Смартфон Xiaomi Redmi 17 8GB/256GB ...","price":799
            # Extract those via regex (with unescape for &quot;)
            products = self._parse_from_html(html, query)
            # Fallback: try to click search button if regex found nothing
            if not products:
                btn = page.locator('form.h-search button')
                if await btn.count() > 0:
                    try:
                        await btn.first.click()
                        await page.wait_for_timeout(4000)
                        html2 = await page.content()
                        products = self._parse_from_html(html2, query)
                        # also try direct product links
                        if not products:
                            products = self._parse_links(html2)
                    except Exception:
                        pass
            return products[:30]
        except Exception as e:
            print(f"5element search failed for {query}: {e}")
            return []
        finally:
            if page:
                await page.close()
            await _release_browser()

    def _parse_from_html(self, html: str, query: str = "") -> list[ProductData]:
        """Parse product JSON embedded in HTML after suggestion load.
        
        Looks for `"name":"<...>","code":"...","price":<int>`
        The price is in BYN (integer, e.g. 799).
        HTML from Playwright has `&quot;` entities, so we unescape first.
        Filters by query words to avoid returning homepage hits (HAFF, ASUS)
        when the user searched for Xiaomi.
        """
        import html as html_lib
        html = html_lib.unescape(html)
        products: list[ProductData] = []
        query_words = [w.lower() for w in query.split() if len(w) >= 2]
        # Regex for product objects: name, code, price
        # Example: "name":"Смартфон Xiaomi Redmi 17 8GB/256GB RU (фиолетовый)","code":"smartfon-xiaomi-...","price":799
        pattern = re.compile(r'"name"\s*:\s*"([^"]+)"\s*,\s*"code"\s*:\s*"([^"]+)"[^}]{0,500}?"price"\s*:\s*"?(\d+)"?', re.DOTALL)
        seen = set()
        for m in pattern.finditer(html):
            name = m.group(1).strip()
            code = m.group(2).strip()
            try:
                price = float(m.group(3))
            except ValueError:
                continue
            if not name or price <= 0:
                continue
            # Filter by query words (avoid homepage hits)
            if query_words and not any(w in name.lower() for w in query_words):
                continue
            # Deduplicate by code
            if code in seen:
                continue
            seen.add(code)
            url = f"https://5element.by/products/{code}" if not code.startswith("http") else code
            products.append(ProductData(name=name, price=price, store=self.store_name, url=url))
            if len(products) >= 20:
                break
        return products

    def _parse_links(self, html: str) -> list[ProductData]:
        """Fallback: parse visible product links if JSON regex found nothing."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        products: list[ProductData] = []
        for a in soup.select('a[href*="/products/"]')[:30]:
            title = a.get("title") or a.get_text(strip=True)
            if not title or "Xiaomi" not in title:
                continue
            href = a.get("href", "")
            if href.startswith("/"):
                href = "https://5element.by" + href
            # Try to find price near the link: look for sibling with price class
            price = None
            parent = a.parent
            if parent:
                price_el = parent.select_one('[class*="price"]')
                if price_el:
                    txt = price_el.get_text(strip=True).replace(" ", "").replace(",", ".")
                    try:
                        price = float(re.sub(r"[^0-9.]", "", txt))
                    except ValueError:
                        price = None
            if price is None:
                continue
            products.append(ProductData(name=title, price=price, store=self.store_name, url=href))
        return products
