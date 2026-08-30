"""7745.by scraper via Playwright (hg-security anti-bot).

7745.by is behind hg-security JS challenge (same as amd.by) that blocks plain
aiohttp with a 1.2k verification page. A real browser with webdriver hidden
passes after ~2s and reloads.

Search is at `https://7745.by/search?keys=<query>` (with keys param).
For generic queries the server sometimes 302s to a catalog category
(e.g. /catalog/televizory) — both contain `.catalog-item` product cards.
Page is SSR after challenge passes. If the challenge still blocks, we return [].

Product card observed structure:
  .catalog-item  — container (schema.org ListItem)
    meta[itemprop="url"] content="product/0992860" — relative product path
    a.line-clamp-3[title] or a[href^="/product/"] — name + URL (same href)
    span[data-price] — price in BYN (e.g. data-price="1472.94", text "1 472,94 р.")
    Fallback price: span text containing "р." inside .catalog-item__price-box
"""

import re
from typing import Optional
from urllib.parse import quote_plus

from .base import BrowserScraper, ProductData, _get_browser, _release_browser


class Shop7745Scraper(BrowserScraper):
    store_name = "7745.by"

    async def search(self, query: str) -> list[ProductData]:
        encoded = quote_plus(query)
        url = f"https://7745.by/search?keys={encoded}"
        browser = await _get_browser()
        page = None
        try:
            page = await browser.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            html = await page.content()
            if len(html) < 5000 or "Verification" in html or "hg-security" in html:
                await page.wait_for_timeout(2000)
                html = await page.content()
            if len(html) < 5000 or "Verification" in html:
                return []
            products = self._parse_html_content(html)
            if products:
                return products[:30]
            # retry waiting a bit more in case catalog lazy-loads
            await page.wait_for_timeout(1500)
            html = await page.content()
            return self._parse_html_content(html)[:30]
        except Exception as e:
            print(f"7745 search failed for {query}: {e}")
            return []
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            await _release_browser()

    def _parse_html_content(self, html: str) -> list[ProductData]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".catalog-item")
        if not items:
            return []
        products: list[ProductData] = []
        for item in items[:30]:
            prod = self._parse_item(item)
            if prod:
                products.append(prod)
        return products

    def _parse_item(self, item) -> Optional[ProductData]:
        # Name + URL: anchor with title attribute pointing to /product/ is the product name
        # (class is `line-clamp-3!` with `!` so `a.line-clamp-3` fails). Prefer title-bearing anchor.
        link = item.select_one('a[title][href^="/product/"]')
        if not link:
            link = item.select_one('a.line-clamp-3[href^="/product/"]')
        if not link:
            # fallback: any a with href /product/ that has meaningful product text
            # need to skip credit/rassrochka badges (class benefit, text "Кредит", "От ")
            candidates = item.select('a[href^="/product/"]')
            for c in candidates:
                cls = " ".join(c.get("class", [])) if c.get("class") else ""
                if "benefit" in cls:
                    continue
                txt = c.get_text(strip=True)
                if not txt or len(txt) < 5:
                    continue
                if "В корзину" in txt or "Кредит" in txt or txt.startswith("От "):
                    continue
                link = c
                break
            if not link:
                # last fallback: use image alt
                img = item.select_one('img[alt]')
                if img:
                    # name from alt, url from meta
                    name = img.get("alt", "").strip()
                    if name:
                        url = self._extract_url(item)
                        price = self._extract_price(item)
                        if price is not None and url:
                            return ProductData(name=name, price=price, store=self.store_name, url=url)
                return None

        name = link.get("title") or link.get_text(strip=True)
        name = name.strip()
        if not name or len(name) < 3:
            return None

        href = link.get("href", "")
        if href.startswith("/"):
            href = "https://7745.by" + href

        price = self._extract_price(item)
        if price is None or price <= 0:
            return None

        return ProductData(name=name, price=price, store=self.store_name, url=href)

    def _extract_url(self, item) -> Optional[str]:
        meta = item.select_one('meta[itemprop="url"]')
        if meta:
            content = meta.get("content", "")
            if content:
                if content.startswith("/"):
                    return "https://7745.by" + content
                if content.startswith("product/"):
                    return "https://7745.by/" + content
                if content.startswith("http"):
                    return content
        link = item.select_one('a[href^="/product/"]')
        if link:
            href = link.get("href", "")
            if href.startswith("/"):
                return "https://7745.by" + href
        return None

    def _extract_price(self, item) -> Optional[float]:
        # Primary: span[data-price] -> data-price attribute is canonical BYN
        price_el = item.select_one('span[data-price]')
        if price_el:
            raw = price_el.get("data-price") or price_el.get_text(strip=True)
            try:
                # data-price is like "1472.94"
                cleaned = raw.replace("\u00a0", "").replace(" ", "").replace(",", ".")
                # keep only digits and dot
                m = re.search(r"(\d+(?:\.\d+)?)", cleaned)
                if m:
                    return float(m.group(1))
            except ValueError:
                pass
        # Fallback: text inside .catalog-item__price-box containing р.
        box = item.select_one('.catalog-item__price-box')
        if box:
            text = box.get_text(strip=True)
            # text like "1 472,94 р." — take first number
            text = text.replace("\u00a0", " ").replace(" ", "")
            text = text.replace(",", ".")
            m = re.search(r"(\d+(?:\.\d+)?)", text)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    return None
        # Last resort: any price-like text in item
        text = item.get_text(" ", strip=True).replace("\u00a0", " ")
        m = re.search(r"(\d[\d\s]*[,\.]\d{2})\s*р", text)
        if m:
            try:
                cleaned = m.group(1).replace(" ", "").replace(",", ".")
                return float(cleaned)
            except ValueError:
                return None
        return None

    async def close(self) -> None:
        pass
