"""Google AI (РФ) — реальная цена в России.

Только актуальные данные, без эвристики.
Цепочка как у Ozon (undetected-chromedriver):

1. Google Shopping (`tbm=shop`) через curl_cffi `impersonate=chrome124` — быстро, SSR
2. Яндекс.Маркет через curl_cffi
3. Google Shopping/AI Mode (`udm=50`) через undetected-chromedriver (как Ozon) — обходит капчу
4. ScraperAPI free tier (если задан SCRAPERAPI_KEY) — Google Shopping через резидентный прокси
5. OpenRouter AI (если задан OPENROUTER_API_KEY) — первый запрос = определение товара, ИИ ищет актуальную цену в РФ

Если все источники отдали капчу/пусто — возвращается `[]`, блок не
показывается. Никаких фейковых "≈ 25 000 ₽".
"""

import os
import re
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import quote_plus

from .base import ProductData

try:
    from utils.currency import get_rub_to_byn
except ModuleNotFoundError:
    from backend.utils.currency import get_rub_to_byn  # type: ignore

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

FALLBACK_RUB_TO_BYN = 0.035617  # на 2026-08-30 NBRB: 100 RUB = 3.5617 BYN

# как у Ozon — отдельный uc-браузер для Google, синглтон
_GGL_BROWSER = None
_GGL_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_GGL_LOCK = asyncio.Lock()
_GGL_WARMED_UP = False


def _detect_chrome_version() -> int:
    import subprocess

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


def _get_ggl_browser():
    global _GGL_BROWSER
    if _GGL_BROWSER is None:
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        ver = _detect_chrome_version()
        _GGL_BROWSER = uc.Chrome(headless=True, version_main=ver, options=options)
        try:
            _GGL_BROWSER.set_page_load_timeout(15)
            _GGL_BROWSER.set_script_timeout(12)
        except Exception:
            pass
    return _GGL_BROWSER


def _close_ggl_browser():
    global _GGL_BROWSER
    if _GGL_BROWSER is not None:
        try:
            _GGL_BROWSER.quit()
        except Exception:
            pass
        _GGL_BROWSER = None


def _extract_prices_from_html_static(html: str) -> list[float]:
    prices: list[float] = []
    for m in re.finditer(r'"price(?:Value)?"\s*:\s*"?(\d[\d\s\u00a0\u202f\.,]*)"?', html):
        raw = m.group(1)
        cleaned = raw.replace(" ", "").replace("\u00a0", "").replace("\u202f", "").replace("\xa0", "").replace(",", ".")
        try:
            v = float(re.search(r"\d+(?:\.\d+)?", cleaned).group(0))
            if 1000 <= v <= 600000:
                prices.append(v)
        except Exception:
            continue
    for m in re.finditer(r'(?:от\s*)?(\d[\d\s\u00a0\u202f]{2,}(?:[,\.]\d{2})?)\s*(?:₽|руб|RUB)', html, re.IGNORECASE):
        raw = m.group(1)
        cleaned = raw.replace(" ", "").replace("\u00a0", "").replace("\u202f", "").replace("\xa0", "").replace(",", ".")
        try:
            v = float(re.search(r"\d+(?:\.\d+)?", cleaned).group(0))
            if 1000 <= v <= 600000:
                prices.append(v)
        except Exception:
            continue
    return prices


def _fetch_google_uc_sync(query: str) -> tuple[Optional[float], Optional[str]]:
    """Синхронный фетч Google через undetected-chromedriver (как Ozon)."""
    global _GGL_WARMED_UP
    encoded = quote_plus(query)
    urls = [
        f"https://www.google.com/search?tbm=shop&q={encoded}+цена&hl=ru&gl=ru&pws=0",
        f"https://www.google.com/search?q={encoded}+цена+в+официальных+магазинах+России&hl=ru&udm=50",
    ]
    for attempt in range(2):
        try:
            browser = _get_ggl_browser()
        except Exception:
            _close_ggl_browser()
            _GGL_WARMED_UP = False
            continue
        try:
            if not _GGL_WARMED_UP:
                try:
                    browser.get("https://www.google.com/")
                    time.sleep(0.9)
                    _GGL_WARMED_UP = True
                except Exception:
                    _close_ggl_browser()
                    _GGL_WARMED_UP = False
                    continue
            for url in urls:
                try:
                    browser.get(url)
                except Exception as e:
                    # browser died between attempts — пересоздать
                    if "no such window" in str(e).lower() or "web view not found" in str(e).lower():
                        _close_ggl_browser()
                        _GGL_WARMED_UP = False
                        break
                    continue
                # ждём как у Ozon: tiles/цены, а не фиксированный sleep
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    try:
                        # Shopping: .sh-dgr__grid-result / [data-docid] / цена ₽
                        WebDriverWait(browser, 8).until(
                            lambda d: "₽" in (d.page_source or "") or "руб" in (d.page_source or "").lower() or d.find_elements(By.CSS_SELECTOR, "[data-docid], .sh-dgr__grid-result, [data-shopping-container]")
                        )
                    except Exception:
                        time.sleep(1.0)
                    time.sleep(0.4)
                    try:
                        browser.execute_script("window.scrollBy(0, 800);")
                        time.sleep(0.5)
                    except Exception:
                        pass
                except Exception:
                    time.sleep(0.8)
                try:
                    html = browser.page_source or ""
                except Exception:
                    continue
                low = html.lower()
                if "recaptcha" in low or "captcha" in low or "enablejs" in low or "unusual traffic" in low:
                    continue
                prices = _extract_prices_from_html_static(html)
                if prices:
                    prices.sort()
                    # отбрасываем выбросы-аксессуары <5к
                    filtered = [p for p in prices if p >= 5000]
                    use = filtered if filtered else prices
                    use.sort()
                    median = use[len(use) // 2]
                    return float(median), url
                # если цен нет — возможно Google отдал AI Mode без shopping — пробуем следующий url
                try:
                    _ = html[:1200]
                except Exception:
                    pass
                continue
            # если обе url дали капчу/пусто — пересоздать браузер свежим фингерпринтом
            _close_ggl_browser()
            _GGL_WARMED_UP = False
            continue
        except Exception:
            _close_ggl_browser()
            _GGL_WARMED_UP = False
            continue
    return None, None


class GoogleAiScraper:
    """Не наследует IScraper чтобы не участвовать в общем _fetch пуле.

    Имеет отдельный метод `estimate` который может вызываться после
    основного поиска с уже известными BY ценами.
    """

    store_name = "Google AI (РФ)"

    async def search(self, query: str) -> list[ProductData]:
        rub = await self._try_fetch_real_ru_price(query)
        if rub is None:
            return []  # нет реальных данных — не показываем фейк
        rate = await get_rub_to_byn()
        byn = rub * rate
        # ссылка ведёт на тот источник, откуда реально взяли цену (Google или Яндекс.Маркет)
        url = getattr(self, "_last_source_url", f"https://www.google.com/search?q={quote_plus(query)}+цена+в+официальных+магазинах+России&udm=50")
        return [ProductData(
            name=f"{query} — цена в РФ (актуально)",
            price=round(byn, 2),
            store=self.store_name,
            url=url,
        )]

    async def estimate_with_context(self, query: str, avg_byn: Optional[float]) -> list[ProductData]:
        """Вызывается агрегатором после сбора BY цен. Эвристика отключена."""
        # avg_byn не используется для фейка — только реальные источники
        return await self.search(query)

    async def _try_fetch_real_ru_price(self, query: str, timeout: float = 22.0) -> Optional[float]:
        """Реальные источники: Google Shopping (curl) → Яндекс.Маркет (curl) → Google Playwright."""
        try:
            return await asyncio.wait_for(self._fetch_real_price_chain(query), timeout)
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    async def _fetch_real_price_chain(self, query: str) -> Optional[float]:
        # 1. Google Shopping через curl_cffi (быстро, SSR)
        rub = await self._fetch_google_shopping_curl(query)
        if rub is not None:
            return rub
        # 2. Яндекс.Маркет через curl_cffi
        rub = await self._fetch_yandex_market_curl(query)
        if rub is not None:
            return rub
        # 3. Google через undetected-chromedriver (как Ozon) — обходит капчу
        rub = await self._fetch_google_uc(query)
        if rub is not None:
            return rub
        # 4. ScraperAPI free tier — Google Shopping через резидентный прокси (если не сработало напрямую)
        rub = await self._fetch_scraperapi_google(query)
        if rub is not None:
            return rub
        # 5. OpenRouter AI — первый запрос = определение товара, ИИ ищет цену (бесплатно с free-моделью)
        rub = await self._fetch_openrouter_price(query)
        if rub is not None:
            return rub
        return None

    async def _try_fetch_google_ai(self, query: str, timeout: float = 11.0) -> Optional[float]:
        """Совместимость: старый вызов → новая цепочка."""
        return await self._try_fetch_real_ru_price(query, timeout=timeout)

    def _extract_prices_from_html(self, html: str) -> list[float]:
        return _extract_prices_from_html_static(html)

    # ---------- curl_cffi helpers (реальные данные без Playwright) ----------

    def _curl_get_sync(self, url: str, timeout: int = 8) -> Optional[str]:
        """Синхронный GET через curl_cffi с impersonate, фолбэк на urllib."""
        # 1. curl_cffi (обходит TLS-фингерпринт Google/Яндекса)
        try:
            from curl_cffi import requests as crequests  # type: ignore

            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
            resp = crequests.get(url, impersonate="chrome124", timeout=timeout, headers=headers)
            if resp.status_code == 200 and resp.text and len(resp.text) > 1500:
                low = resp.text.lower()
                # даже если есть капча — вернём html, фильтр выше отсеет
                return resp.text
            if resp.status_code in (429, 403):
                return None
        except Exception:
            pass
        # 2. urllib фолбэк (если curl_cffi не установлен)
        try:
            import urllib.request

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ru-RU"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read().decode("utf-8", errors="ignore")
                if len(data) > 1500:
                    return data
        except Exception:
            pass
        return None

    async def _curl_get(self, url: str, timeout: int = 8) -> Optional[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._curl_get_sync, url, timeout)

    async def _fetch_google_shopping_curl(self, query: str) -> Optional[float]:
        """Google Shopping SSR через curl_cffi — реальные цены без JS."""
        encoded = quote_plus(query)
        urls = [
            f"https://www.google.com/search?tbm=shop&q={encoded}+цена&hl=ru&gl=ru&pws=0",
            f"https://www.google.ru/search?tbm=shop&q={encoded}+цена&hl=ru&gl=ru&pws=0",
        ]
        for url in urls:
            html = await self._curl_get(url)
            if not html:
                continue
            low = html.lower()
            if "recaptcha" in low or "captcha" in low or "enablejs" in low or "unusual traffic" in low:
                continue
            prices = self._extract_prices_from_html(html)
            if prices:
                prices.sort()
                median = prices[len(prices) // 2]
                self._last_source_url = url
                return float(median)
        return None

    async def _fetch_yandex_market_curl(self, query: str) -> Optional[float]:
        """Яндекс.Маркет — агрегатор оф. цен РФ, менее блокируемый из BY."""
        encoded = quote_plus(query)
        urls = [
            f"https://market.yandex.ru/search?text={encoded}&glfilter=7893318%3A1",  # оф. ритейлеры
            f"https://market.yandex.ru/search?text={encoded}",
        ]
        for url in urls:
            html = await self._curl_get(url)
            if not html:
                continue
            low = html.lower()
            if "captcha" in low or "капча" in low:
                continue
            prices = self._extract_prices_from_html(html)
            # Яндекс.Маркет дополнительно: цены в data-autotest-value или meta
            if not prices:
                # пробуем вытянуть из JSON в странице
                for m in re.finditer(r'"price"\s*:\s*(\d{4,6})', html):
                    try:
                        v = float(m.group(1))
                        if 1000 <= v <= 600000:
                            prices.append(v)
                    except Exception:
                        continue
            if prices:
                # для Маркета берём медиану, отбрасываем выбросы <5к (аксессуары)
                filtered = [p for p in prices if p >= 5000]
                if not filtered:
                    filtered = prices
                filtered.sort()
                median = filtered[len(filtered) // 2]
                self._last_source_url = url
                return float(median)
        return None

    async def _fetch_google_uc(self, query: str) -> Optional[float]:
        """Google через undetected-chromedriver в thread-pool (как Ozon)."""
        async with _GGL_LOCK:
            loop = asyncio.get_running_loop()

            def _run():
                rub, url = _fetch_google_uc_sync(query)
                if rub is not None and url:
                    self._last_source_url = url
                return rub

            return await loop.run_in_executor(_GGL_EXECUTOR, _run)

    async def _fetch_scraperapi_google(self, query: str) -> Optional[float]:
        """ScraperAPI free tier — Google Shopping через прокси, без SerpApi."""
        api_key = os.getenv("SCRAPERAPI_KEY") or os.getenv("SCRAPER_API_KEY") or os.getenv("SCRAPERAPI_API_KEY")
        if not api_key:
            return None
        encoded = quote_plus(query)
        target = f"https://www.google.com/search?tbm=shop&q={encoded}+цена&hl=ru&gl=ru&pws=0"
        # ScraperAPI: http://api.scraperapi.com?api_key=KEY&url=TARGET&render=true&country_code=ru
        scraper_url = f"http://api.scraperapi.com?api_key={api_key}&url={quote_plus(target)}&render=true&country_code=ru"
        html = await self._curl_get(scraper_url, timeout=15)
        if not html:
            return None
        low = html.lower()
        if "recaptcha" in low or "captcha" in low or "enablejs" in low:
            return None
        prices = self._extract_prices_from_html(html)
        if prices:
            prices.sort()
            median = prices[len(prices) // 2]
            self._last_source_url = target
            return float(median)
        return None

    def _openrouter_get_sync(self, query: str) -> tuple[Optional[float], Optional[str]]:
        """Синхронный запрос к OpenRouter — первый запрос = определение товара."""
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY")
        if not api_key:
            return None, None
        model = os.getenv("OPENROUTER_MODEL", "perplexity/sonar")
        # первый запрос — чёткое определение товара из canonical query
        prompt = (
            f"Найди актуальную цену товара '{query}' в официальных магазинах России "
            f"(DNS, М.Видео, Ситилинк, Эльдорадо, Яндекс.Маркет) в рублях на сегодня. "
            f"Верни ТОЛЬКО JSON: {{\"price_rub\": 36990, \"url\": \"https://...\", \"source\": \"dns-shop.ru\"}} "
            f"Если не нашёл — {{\"price_rub\": null}}. Без текста вокруг."
        )
        try:
            import json as _json

            # пробуем curl_cffi, фолбэк urllib
            payload = _json.dumps(
                {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 400,
                }
            )
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "http://localhost:3000"),
                "X-Title": os.getenv("OPENROUTER_TITLE", "price-comparison-by"),
            }
            # curl_cffi
            try:
                from curl_cffi import requests as crequests  # type: ignore

                resp = crequests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=payload,
                    headers=headers,
                    impersonate="chrome124",
                    timeout=12,
                )
                if resp.status_code != 200:
                    return None, None
                data = resp.json()
            except Exception:
                import urllib.request

                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=payload.encode(),
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=12) as r:
                    data = _json.loads(r.read().decode())

            content = ""
            try:
                content = data["choices"][0]["message"]["content"] or ""
            except Exception:
                return None, None
            # вытаскиваем JSON и цену
            m = re.search(r'"price_rub"\s*:\s*(null|\d[\d\s\.,]*)', content, re.IGNORECASE)
            if m:
                raw = m.group(1)
                if "null" in raw.lower():
                    return None, None
                cleaned = raw.replace(" ", "").replace("\xa0", "").replace(",", ".")
                v = float(re.search(r"\d+(?:\.\d+)?", cleaned).group(0))
                if 1000 <= v <= 600000:
                    # достаём url если есть
                    um = re.search(r'"url"\s*:\s*"([^"]+)"', content)
                    url = um.group(1) if um else f"https://openrouter.ai/search?q={quote_plus(query)}"
                    return v, url
            # фолбэк — любой ₽ в ответе
            prices = _extract_prices_from_html_static(content)
            if prices:
                prices.sort()
                return float(prices[len(prices) // 2]), f"https://openrouter.ai/search?q={quote_plus(query)}"
        except Exception:
            return None, None
        return None, None

    async def _fetch_openrouter_price(self, query: str) -> Optional[float]:
        """OpenRouter AI через первый запрос-определение товара."""
        if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY")):
            return None
        loop = asyncio.get_running_loop()

        def _run():
            rub, url = self._openrouter_get_sync(query)
            if rub is not None and url:
                self._last_source_url = url
            return rub

        try:
            return await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=13)
        except asyncio.TimeoutError:
            return None

    # старый Playwright путь оставлен для совместимости, теперь проксирует на uc
    async def _fetch_google_price(self, query: str) -> Optional[float]:
        return await self._fetch_google_uc(query)

    async def close(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_GGL_EXECUTOR, _close_ggl_browser)
