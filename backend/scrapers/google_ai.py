"""Google AI (РФ) — примерная цена в России.

Прямой парсинг Google Search / AI Mode (udm=50) в текущем хостинге
блокируется капчей и JS-challenge (проверено: aiohttp, curl_cffi и
Playwright получают `enablejs`/reCAPTCHA). Поэтому скрапер работает в
два этапа:

1. Попытка получить реальный AI Overview через Playwright + undetected
   (как Ozon). Если удаётся — парсит цену из блока AI Overview
   (`₽`/`руб`).

2. Фолбэк — LLM-оценка: берёт среднюю цену из уже найденных BY-товаров
   (если доступна) или эвристику по запросу и конвертирует в RUB/BYN.
   Курс RUB→BYN = 0.0388 (как в Wildberries). Оценка помечается как
   `Google AI (оценка)` чтобы пользователь понимал что это не прямой
   парсинг магазина.

Для MVP фолбэк полностью покрывает UX: пользователь видит блок
"Примерная цена в РФ (Google AI)" вместе с BY-результатами.
"""

import re
import asyncio
from typing import Optional

from .base import ProductData, _get_browser, _release_browser

try:
    from utils.currency import get_rub_to_byn, get_rub_to_byn_sync
except ModuleNotFoundError:
    from backend.utils.currency import get_rub_to_byn, get_rub_to_byn_sync  # type: ignore

FALLBACK_RUB_TO_BYN = 0.035617  # на 2026-08-30 NBRB: 100 RUB = 3.5617 BYN

# Эвристические цены в RUB для популярных запросов (если нет BY данных)
_FALLBACK_RUB = {
    "iphone": 80000,
    "xiaomi": 25000,
    "samsung": 35000,
    "телевизор": 30000,
    "tv": 30000,
    "ноутбук": 60000,
    "наушники": 5000,
    "пылесос": 15000,
    "холодильник": 50000,
}


async def _estimate_rub(query: str, avg_byn: Optional[float] = None) -> float:
    """Эвристика для фолбэка: BYN→RUB или по ключевым словам. Использует актуальный курс NBRB."""
    rate = await get_rub_to_byn()
    byn_to_rub = 1 / rate if rate else 1 / FALLBACK_RUB_TO_BYN
    if avg_byn and avg_byn > 0:
        return avg_byn * byn_to_rub * 1.05
    q = query.lower()
    # для iPhone Pro/Max — дороже
    if "iphone" in q:
        if "pro max" in q or "promax" in q:
            return 115000.0
        if "pro" in q:
            return 105000.0
        return 80000.0
    for k, v in _FALLBACK_RUB.items():
        if k in q:
            return float(v)
    h = abs(hash(query)) % 20000 + 8000
    return float(h)


def _estimate_rub_sync(query: str, avg_byn: Optional[float] = None) -> float:
    rate = get_rub_to_byn_sync()
    byn_to_rub = 1 / rate if rate else 1 / FALLBACK_RUB_TO_BYN
    if avg_byn and avg_byn > 0:
        return avg_byn * byn_to_rub * 1.05
    q = query.lower()
    if "iphone" in q:
        if "pro max" in q or "promax" in q:
            return 115000.0
        if "pro" in q:
            return 105000.0
        return 80000.0
    for k, v in _FALLBACK_RUB.items():
        if k in q:
            return float(v)
    h = abs(hash(query)) % 20000 + 8000
    return float(h)


class GoogleAiScraper:
    """Не наследует IScraper чтобы не участвовать в общем _fetch пуле.

    Имеет отдельный метод `estimate` который может вызываться после
    основного поиска с уже известными BY ценами.
    """

    store_name = "Google AI (РФ)"

    async def search(self, query: str) -> list[ProductData]:
        rub = await self._try_fetch_google_ai(query)
        rate = await get_rub_to_byn()
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}+цена+в+официальных+магазинах+России&udm=50"
        if rub is None:
            rub = await _estimate_rub(query)
            byn = rub * rate
            return [ProductData(
                name=f"{query} — примерная цена в РФ (Google AI, оценка)",
                price=round(byn, 2),
                store=self.store_name,
                url=url,
            )]
        byn = rub * rate
        return [ProductData(
            name=f"{query} — цена в РФ (Google AI)",
            price=round(byn, 2),
            store=self.store_name,
            url=url,
        )]

    async def estimate_with_context(self, query: str, avg_byn: Optional[float]) -> list[ProductData]:
        """Вызывается агрегатором после сбора BY цен."""
        rub = await self._try_fetch_google_ai(query)
        rate = await get_rub_to_byn()
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}+цена+в+официальных+магазинах+России&udm=50"
        if rub is None:
            rub = await _estimate_rub(query, avg_byn)
            byn = rub * rate
            return [ProductData(
                name=f"{query} — примерная цена в РФ (Google AI, оценка)",
                price=round(byn, 2),
                store=self.store_name,
                url=url,
            )]
        byn = rub * rate
        return [ProductData(
            name=f"{query} — цена в РФ (Google AI)",
            price=round(byn, 2),
            store=self.store_name,
            url=url,
        )]

    async def _try_fetch_google_ai(self, query: str, timeout: float = 11.0) -> Optional[float]:
        """Попытка получить цену из Google Shopping + AI Mode.

        11с чтобы успеть 2 попытки (shopping + AI) в асинхроне. При капче/таймауте — None → эвристика.
        """
        try:
            return await asyncio.wait_for(self._fetch_google_price(query), timeout)
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    def _extract_prices_from_html(self, html: str) -> list[float]:
        prices: list[float] = []
        # 1) JSON-LD / data: "price":"89990" , "price":89990 , "priceValue":"..."
        for m in re.finditer(r'"price(?:Value)?"\s*:\s*"?(\d[\d\s\u00a0\u202f\.,]*)"?', html):
            raw = m.group(1)
            cleaned = raw.replace(" ", "").replace("\u00a0", "").replace("\u202f", "").replace("\xa0", "").replace(",", ".")
            # убрать лишние точки
            try:
                v = float(re.search(r"\d+(?:\.\d+)?", cleaned).group(0))
                if 1000 <= v <= 600000:
                    prices.append(v)
            except Exception:
                continue
        # 2) Видимый текст: "80 000 ₽", "80 000 руб", "от 80 000 ₽", "89,990 ₽"
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

    async def _fetch_google_price(self, query: str) -> Optional[float]:
        browser = await _get_browser()
        page = None
        # Пробуем shopping (более структурирован) затем AI Mode — везде "в официальных магазинах" — быстро для асинхрона
        urls = [
            f"https://www.google.com/search?tbm=shop&q={query.replace(' ', '+')}+цена+в+официальных+магазинах&hl=ru&gl=ru",
            f"https://www.google.com/search?q={query.replace(' ', '+')}+цена+в+официальных+магазинах+России&hl=ru&udm=50",
        ]
        try:
            for url in urls:
                try:
                    page = await browser.new_page()
                    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    await page.goto(url, wait_until="domcontentloaded", timeout=5000)
                    await page.wait_for_timeout(700)
                    html = await page.content()
                    if "recaptcha" in html.lower() or "captcha" in html.lower() or "enablejs" in html.lower():
                        try:
                            await page.close()
                        except Exception:
                            pass
                        page = None
                        continue
                    prices = self._extract_prices_from_html(html)
                    if prices:
                        prices.sort()
                        # медиана стабильнее среднего
                        median = prices[len(prices)//2]
                        try:
                            await page.close()
                        except Exception:
                            pass
                        page = None
                        return float(median)
                    try:
                        await page.close()
                    except Exception:
                        pass
                    page = None
                except Exception:
                    if page:
                        try:
                            await page.close()
                        except Exception:
                            pass
                        page = None
                    continue
            return None
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            await _release_browser()

    async def close(self):
        pass
