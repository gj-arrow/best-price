"""Ozon.by scraper implementation using undetected-chromedriver.

Playwright НЕ работает — Variti детектит его chromium (и bundled headless-shell,
и channel="chrome") и отдаёт challenge "Похоже, нет соединения" (инцидент
fab_chlg_...). undetected-chromedriver проходит потому что патчит ChromeDriver
(скрывает webdriver + пересобирает под текущий Chrome). Обязательно version_main
должен совпадать с установленным Chrome (авто-детект).

Важно: /search/?text=... легально редиректит на /category/... (например
iphone → /category/smartfony-15502/apple-26303000/) — это НЕ блок, а нормальная
выдача. _on_search_page принимает и /category/.
"""

import os
import re
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import quote_plus

from .base import IScraper, ProductData

# SSL cert fix for Python 3.14 on macOS
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

# Lazy imports for heavyweight deps
_browser = None    # uc.Chrome instance
_executor = ThreadPoolExecutor(max_workers=1)
_LOCK = asyncio.Lock()  # ensure one search at a time (single browser)


def _detect_chrome_version() -> int:
    """Detect installed Chrome major version, fallback to 151."""
    import subprocess, re
    candidates = [
        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
        ["google-chrome", "--version"],
        ["chromium", "--version"],
    ]
    for cmd in candidates:
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=3)
            m = re.search(r"(\d+)\.", out)
            if m:
                return int(m.group(1))
        except Exception:
            continue
    return 151


def _get_browser():
    """Get or create the shared undetected-chromedriver browser instance."""
    global _browser
    if _browser is None:
        import undetected_chromedriver as uc
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        ver = _detect_chrome_version()
        # version_main must match installed Chrome version — авто-детект чтобы не ломаться при апдейте
        _browser = uc.Chrome(headless=True, version_main=ver, options=options)
        try:
            _browser.set_page_load_timeout(15)
            _browser.set_script_timeout(12)
        except Exception:
            pass
    return _browser


def _close_browser():
    """Close the shared browser instance."""
    global _browser
    if _browser is not None:
        try:
            _browser.quit()
        except Exception:
            pass
        _browser = None


def _parse_tiles(browser) -> list[ProductData]:
    """Extract products from the currently loaded Ozon search page."""
    from selenium.webdriver.common.by import By

    tiles = browser.find_elements(By.CSS_SELECTOR, "[data-index]")
    products = []
    seen_names = set()

    for tile in tiles:
        try:
            href = None
            name = ""
            # Each tile has 2-3 links pointing to the same product.
            # Pick the longest text link = the product name (skip badge links).
            links = tile.find_elements(By.CSS_SELECTOR, 'a[href*="/product/"]')
            for link in links:
                t = link.text.strip()
                href = link.get_attribute("href")
                if len(t) > len(name):
                    name = t

            if not name or len(name) < 10 or not href:
                continue

            # Extract BYN prices from THIS tile only
            # Ozon tile часто содержит 2 цены: полную (3 869,78 BYN) и
            # месячный платёж рассрочки (898,70 BYN × 12 мес). В DOM они
            # в разных <span> — проверка "×" in pe.text не ловит случай
            # <span>898,70 BYN</span><span>× 4 мес</span>. Поэтому смотрим
            # на весь tile.text и на соседей.
            try:
                tile_text = tile.text or ""
            except Exception:
                tile_text = ""

            price_els = tile.find_elements(By.XPATH, './/*[contains(text(), "BYN")]')
            prices = []
            for pe in price_els:
                text = pe.text.strip()
                # быстрый отсев: если в самом элементе уже есть маркер рассрочки
                if "×" in text or "мес" in text.lower() or "рассроч" in text.lower():
                    continue
                # контекст: родитель и соседний элемент (покрывает разнесённые span'ы)
                try:
                    parent_text = pe.find_element(By.XPATH, "..").text or ""
                except Exception:
                    parent_text = ""
                try:
                    sib = pe.find_element(By.XPATH, "following-sibling::*[1]")
                    sib_text = sib.text or "" if sib else ""
                except Exception:
                    sib_text = ""
                combined = f"{text} {parent_text} {sib_text}".lower()
                if "×" in combined or "мес" in combined or "рассроч" in combined:
                    continue

                match = re.search(r"([\d\u2009\s]+),(\d+)\s*BYN", text)
                if not match:
                    continue
                # Дополнительно: если в tile.text рядом с этой ценой есть ×/мес/рассрочка
                # — это точно платёж рассрочки, даже если он в другом span'е.
                # Ищем цену в tile_text и смотрим ±30 символов.
                try:
                    raw_price = match.group(0)
                    # ищем вхождение цены в tile_text (по цифрам, чтобы не зависеть от \u2009)
                    price_digits = re.sub(r"[^\d,]", "", raw_price)
                    idx = -1
                    # пробуем найти по сырому куску
                    if raw_price.strip() in tile_text:
                        idx = tile_text.index(raw_price.strip())
                    elif price_digits and price_digits in re.sub(r"[^\d,]", "", tile_text):
                        # fallback — не можем точно локализовать, пропускаем проверку
                        idx = -1
                    if idx != -1:
                        window = tile_text[max(0, idx - 2): idx + len(raw_price) + 30].lower()
                        if "×" in window or "мес" in window or "рассроч" in window:
                            continue
                except Exception:
                    pass

                int_part = match.group(1).replace("\u2009", "").replace(" ", "").replace("\xa0", "")
                dec_part = match.group(2)
                try:
                    prices.append(float(f"{int_part}.{dec_part}"))
                except ValueError:
                    continue

            # Fallback: если ничего не нашли через per-element, пробуем распарсить весь tile.text
            # (покрывает случай когда BYN в псевдоэлементе / shadow)
            if not prices and tile_text:
                for m in re.finditer(r"([\d\u2009\s]+),(\d+)\s*BYN", tile_text):
                    after = tile_text[m.end(): m.end() + 30].lower()
                    before = tile_text[max(0, m.start() - 20): m.start()].lower()
                    if "×" in after or "мес" in after or "рассроч" in after or "рассроч" in before:
                        continue
                    # также пропустим если после цены сразу × в after
                    if "×" in m.group(0):
                        continue
                    int_part = m.group(1).replace("\u2009", "").replace(" ", "").replace("\xa0", "")
                    dec_part = m.group(2)
                    try:
                        prices.append(float(f"{int_part}.{dec_part}"))
                    except ValueError:
                        continue

            if not prices:
                continue

            # Эвристика: месячный платёж всегда << полной цены.
            # Если в тайле остались [3869, 898], 898 < 0.45*3869 → выкидываем рассрочку.
            # Карта Ozon даёт -5..10%, поэтому 0.45 безопасен (не тронет скидку по карте).
            if len(prices) >= 2:
                prices.sort()
                # пока минимальный сильно меньше максимального — это рассрочка/кэшбек-платёж
                while len(prices) >= 2 and min(prices) < 0.45 * max(prices):
                    prices.pop(0)

            if not prices:
                continue

            current_price = min(prices)  # после фильтрации — реальная цена (с картой если есть)

            # Deduplicate by truncated name
            name_key = name[:60].lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            products.append(ProductData(
                name=name[:200],
                price=round(current_price, 2),
                store="Ozon",
                url=href,
            ))

        except Exception:
            continue

    products.sort(key=lambda p: p.price)
    return products[:30]


def _on_search_page(browser) -> bool:
    """Quick URL check: are we on search or category results?

    Variti sometimes redirects the search GET to the homepage outright.
    Ozon also legitimately redirects /search/?text=iphone → /category/smartfony/.../apple-...
    which is a valid listing page with the same [data-index] tiles. Both are accepted.
    A stronger junk check (_results_match_query) runs after parsing.
    """
    try:
        current = browser.current_url or ""
    except Exception:
        return False
    return "/search/" in current or "/category/" in current


def _results_match_query(products: list[ProductData], query: str) -> bool:
    """Did Ozon return actual search results, not recommendation junk?

    Variti can serve a /search/ URL whose page body is filled with
    homepage-style recommendation carousels (same `[data-index]` tiles,
    unrelated products). The URL check alone can't catch this. We treat the
    result as real only if at least one parsed tile's name contains the
    query's STRONG model token — the alphanumeric ID unique to the product
    (e.g. "af-ze7226-a"). Recommendation junk never contains it.
    """
    if not products:
        return False
    # Strong token = a query word with BOTH letters and digits.
    import re
    strong = [w.lower() for w in query.split()
              if len(w) >= 2 and re.search(r"\d", w) and re.search(r"[a-zа-яё]", w.lower())]
    if not strong:
        # No strong token to anchor on — accept any results (can't tell).
        return True
    return any(s in p.name.lower() for p in products for s in strong)


# Tracks whether the shared browser has done a homepage warmup yet.
# A fresh undetected-chromedriver session that jumps straight to /search/
# trips Variti more often than one that loads the homepage first (human-like).
_warmed_up = False


def _search_sync(query: str) -> list[ProductData]:
    """
    Synchronous Ozon search implementation.
    Runs in a thread pool to not block the async event loop.

    Anti-bot strategy (Variti serves junk ~80% of the time otherwise):
      1. On a fresh browser, load the Ozon homepage first (human-like
         warmup) before searching.
      2. Navigate to the search URL, wait for tiles.
      3. Reject the result if the URL was redirected away from /search/ or
         /category/ OR if no parsed tile contains the query's strong model
         token (recommendation junk lacks it).
      4. On rejection, close + recreate the browser (fresh fingerprint)
         and retry. Up to 2 attempts.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    global _warmed_up

    encoded = quote_plus(query)
    url = f"https://www.ozon.by/search/?text={encoded}"

    products: list[ProductData] = []
    for attempt in range(2):
        browser = _get_browser()
        try:
            # Human-like warmup: load homepage once per browser session.
            if not _warmed_up:
                browser.get("https://www.ozon.by/")
                time.sleep(0.8)
                _warmed_up = True

            browser.get(url)

            # Wait for product tiles — category pages use same [data-index]
            WebDriverWait(browser, 14).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-index]"))
            )

            # Give JS a moment to render
            time.sleep(0.6)

            # Scroll to trigger lazy loading
            browser.execute_script("window.scrollBy(0, 800);")
            time.sleep(0.6)

            # Two-stage junk detection:
            #   (a) URL redirected away from /search/ or /category/ → homepage soft-block
            #   (b) tiles present but none match the query's model token →
            #       recommendation carousels served under a search URL
            if not _on_search_page(browser):
                print(f"Ozon: redirected off search/category "
                      f"(url={browser.current_url[:60]}), recreating browser "
                      f"(attempt {attempt + 1}/2)")
                _close_browser()
                _warmed_up = False
                continue

            products = _parse_tiles(browser)

            if not _results_match_query(products, query):
                print(f"Ozon: tiles are recommendation junk (no model token), "
                      f"recreating browser (attempt {attempt + 1}/2)")
                _close_browser()
                _warmed_up = False
                continue

            return products

        except Exception as e:
            print(f"Ozon search error (attempt {attempt + 1}/2): {e}")
            _close_browser()
            _warmed_up = False
            continue

    return products


class OzonScraper(IScraper):
    """Scraper for Ozon.by marketplace.

    Uses undetected-chromedriver with headless Chrome to bypass
    Ozon's Variti anti-bot protection. Requires real Chrome installed.
    Prices in BYN (Belarusian rubles).
    """

    store_name = "Ozon"

    async def search(self, query: str) -> list[ProductData]:
        """Search products on Ozon.by. Runs Selenium in a thread pool."""
        async with _LOCK:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(_executor, _search_sync, query)

    async def close(self) -> None:
        """Close browser in thread pool."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_executor, _close_browser)