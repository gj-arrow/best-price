"""AMD.by scraper via Playwright (anti-bot hg-security).

AMD.by is protected by a JS challenge that sets `hg-security` cookie via
`navigator.webdriver` check and a heavy `calc` loop. Plain aiohttp gets
401/403 or a 1.2k verification page. A real browser with webdriver hidden
usually passes after ~2s and reloads.

Search is at `https://www.amd.by/search/?query=<query>` (with slash) but
also accepts `https://amd.by/search?query=` (without www). The page is
SSR after challenge passes and contains `.search-prod-details` product
blocks. If the challenge still blocks (headless detected), we return [].
"""

import re
from typing import Optional

from .base import BrowserScraper, ProductData, _get_browser, _release_browser


class AmdScraper(BrowserScraper):
    store_name = "AMD.by"

    async def search(self, query: str) -> list[ProductData]:
        # Try both URL variants
        urls = [
            f"https://www.amd.by/search/?query={query.replace(' ', '+')}",
            f"https://amd.by/search?query={query.replace(' ', '+')}",
        ]
        browser = await _get_browser()
        page = None
        for url in urls:
            try:
                page = await browser.new_page()
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(5000)
                html = await page.content()
                # Check if still on verification (hg-security)
                if "hg-security" in html or "Verification" in html or len(html) < 5000:
                    # try waiting a bit more for auto-reload
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                if len(html) < 5000 or "Verification" in html:
                    await page.close()
                    page = None
                    continue
                products = self._parse_html_content(html)
                await page.close()
                page = None
                if products:
                    return products[:30]
                # If no products but page loaded, try next URL
            except Exception as e:
                print(f"AMD search failed for {query} at {url}: {e}")
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    page = None
                continue
        if page:
            try:
                await page.close()
            except Exception:
                pass
        await _release_browser()
        return []

    def _parse_html_content(self, html: str) -> list[ProductData]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        products: list[ProductData] = []
        # AMD search results: .search-prod-details or .product-thumb?
        # Observed CSS: .sphinxsearch .products .search-prod-details
        items = soup.select(".search-prod-details, .product-thumb, .product-layout")
        if not items:
            # fallback: any link to product
            items = soup.select('a[href*="/product/"]')
            # need to group by product block
            # Instead parse all product links directly
            seen = set()
            for a in soup.select('a[href*="/product/"]')[:30]:
                href = a.get("href", "")
                name = a.get_text(strip=True) or a.get("title", "")
                if not name or len(name) < 5:
                    # try parent title
                    parent = a.find_parent("div")
                    if parent:
                        name = parent.get_text(strip=True)[:80]
                if href.startswith("/"):
                    href = "https://www.amd.by" + href
                if href in seen:
                    continue
                seen.add(href)
                # find price nearby
                price = self._extract_price_for_link(a)
                if price is None or price <= 0:
                    continue
                if not name or len(name) < 5:
                    name = href.split("/")[-1].replace("-", " ")
                products.append(ProductData(name=name.strip(), price=price, store=self.store_name, url=href))
            return products

        for item in items[:30]:
            prod = self._parse_item(item)
            if prod:
                products.append(prod)
        return products

    def _parse_item(self, item) -> Optional[ProductData]:
        # name from a
        link = item.select_one("a[href]")
        if not link:
            return None
        name = link.get_text(strip=True) or link.get("title", "")
        if not name or len(name) < 5:
            # try heading
            h = item.select_one("h4, .name, .product-name")
            if h:
                name = h.get_text(strip=True)
        if not name:
            return None
        href = link.get("href", "")
        if href.startswith("/"):
            href = "https://www.amd.by" + href
        price = self._extract_price_for_link(item)
        if price is None or price <= 0:
            return None
        return ProductData(name=name.strip(), price=price, store=self.store_name, url=href)

    def _extract_price_for_link(self, elem) -> Optional[float]:
        # look for price in same block
        # AMD price is in .price, .price-tov, [class*="price"]
        price_el = elem.select_one(".price, .price-tov, [class*='price']")
        if not price_el:
            # climb up
            parent = elem.parent
            for _ in range(3):
                if not parent:
                    break
                price_el = parent.select_one(".price, .price-tov, [class*='price']")
                if price_el:
                    break
                parent = parent.parent
        if not price_el:
            return None
        text = price_el.get_text(strip=True)
        # text like "1 234,00 р." or "799.00"
        text = text.replace(" ", "").replace("\u00a0", "").replace(",", ".")
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    async def close(self) -> None:
        # BrowserScraper close is handled via _release_browser, but we called it manually
        pass
