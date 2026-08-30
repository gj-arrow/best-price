"""5element.by scraper via Diginetica autocomplete API (fallback Playwright)."""

import re
import json
import os
from typing import Optional
from urllib.parse import quote_plus

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

import aiohttp

from .base import BrowserScraper, ProductData, _get_browser, _release_browser


class FiveElementScraper(BrowserScraper):
    """Scraper for 5element.by — Diginetica API first, Playwright fallback.

    Ранее поиск шёл через Playwright ввод в `input[placeholder*="Поиск товара"]`
    и парсинг `name/code/price` из HTML. Но после ввода `iPhone 17 Pro Max`
    страница отдавала только хиты с `17` (Xiaomi Redmi 17) а iPhone не попадал
    — Diginetica suggestions грузятся XHR, а HTML содержит прелоад homepage.
    Прямой API `autocomplete.diginetica.net` отдаёт релевантные iPhone сразу
    (проверено для `iPhone 17 Pro Max 256` и `айфон 17 про макс 256`).
    Поэтому первично бьём в API, fallback — старый Playwright путь.
    """

    store_name = "5element.by"
    _DIGINETICA_URL = "https://autocomplete.diginetica.net/autocomplete"
    _API_KEY = "08IE0509XQ"

    async def search(self, query: str) -> list[ProductData]:
        # 1) быстрый путь — Diginetica API (a la Wildberries)
        try:
            api_products = await self._search_via_api(query)
            if api_products:
                return api_products[:30]
        except Exception as e:
            print(f"5element api search failed for {query}: {e}")
        # 2) fallback — старый Playwright (на случай смены apiKey)
        return await self._search_via_browser(query)

    async def _search_via_api(self, query: str) -> list[ProductData]:
        params = {
            "st": query,
            "apiKey": self._API_KEY,
            "strategy": "advanced_xname,zero_queries",
            "productsSize": "20",
            "regionId": "global",
            "forIs": "true",
            "showUnavailable": "true",
            "withContent": "false",
            "withSku": "false",
        }
        # quote_plus для корректного пробела
        qs = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        url = f"{self._DIGINETICA_URL}?{qs}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://5element.by/",
        }
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        products: list[ProductData] = []
        for prod in (data.get("products") or [])[:30]:
            name = (prod.get("name") or "").strip()
            # API отдаёт "APPLE Смартфон Apple iPhone 17 Pro Max 256GB ..." — чистим двойной бренд
            price_raw = prod.get("price") or prod.get("oldPrice") or 0
            try:
                price = float(str(price_raw).replace(",", "."))
            except ValueError:
                continue
            link = prod.get("link_url") or ""
            if link.startswith("/"):
                link = "https://5element.by" + link
            if not name or price <= 0 or not link:
                continue
            products.append(ProductData(name=name, price=price, store=self.store_name, url=link))
        return products

    async def _search_via_browser(self, query: str) -> list[ProductData]:
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
            await inp.first.press_sequentially(query, delay=80)
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
