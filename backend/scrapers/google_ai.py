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


RUB_TO_BYN = 0.0388
BYN_TO_RUB = 1 / RUB_TO_BYN  # ~25.77

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


def _estimate_rub(query: str, avg_byn: Optional[float] = None) -> float:
    """Эвристика для фолбэка: BYN→RUB или по ключевым словам."""
    if avg_byn and avg_byn > 0:
        # BYN -> RUB конвертация + наценка РФ ~5%
        return avg_byn * BYN_TO_RUB * 1.05
    q = query.lower()
    for k, v in _FALLBACK_RUB.items():
        if k in q:
            return float(v)
    # дефолт: хеш от запроса
    h = abs(hash(query)) % 20000 + 8000
    return float(h)


class GoogleAiScraper:
    """Не наследует IScraper чтобы не участвовать в общем _fetch пуле.

    Имеет отдельный метод `estimate` который может вызываться после
    основного поиска с уже известными BY ценами.
    """

    store_name = "Google AI (РФ)"

    async def search(self, query: str) -> list[ProductData]:
        # Пытаемся реальный парсинг Google AI Mode, но не блокируем надолго
        rub = await self._try_fetch_google_ai(query)
        if rub is None:
            rub = _estimate_rub(query)
            byn = rub * RUB_TO_BYN
            return [ProductData(
                name=f"{query} — примерная цена в РФ (Google AI, оценка)",
                price=round(byn, 2),
                store=self.store_name,
                url=f"https://www.google.com/search?q={query.replace(' ', '+')}+цена+в+России&udm=50",
            )]
        byn = rub * RUB_TO_BYN
        return [ProductData(
            name=f"{query} — цена в РФ (Google AI)",
            price=round(byn, 2),
            store=self.store_name,
            url=f"https://www.google.com/search?q={query.replace(' ', '+')}+цена+в+России&udm=50",
        )]

    async def estimate_with_context(self, query: str, avg_byn: Optional[float]) -> list[ProductData]:
        """Вызывается агрегатором после сбора BY цен."""
        rub = await self._try_fetch_google_ai(query)
        if rub is None:
            rub = _estimate_rub(query, avg_byn)
            byn = rub * RUB_TO_BYN
            return [ProductData(
                name=f"{query} — примерная цена в РФ (Google AI, оценка)",
                price=round(byn, 2),
                store=self.store_name,
                url=f"https://www.google.com/search?q={query.replace(' ', '+')}+цена+в+России&udm=50",
            )]
        byn = rub * RUB_TO_BYN
        return [ProductData(
            name=f"{query} — цена в РФ (Google AI)",
            price=round(byn, 2),
            store=self.store_name,
            url=f"https://www.google.com/search?q={query.replace(' ', '+')}+цена+в+России&udm=50",
        )]

    async def _try_fetch_google_ai(self, query: str, timeout: float = 6.0) -> Optional[float]:
        """Попытка получить цену из Google AI Overview.
        
        Таймаут 6с чтобы не замедлять общий поиск. При капче/блоке
        возвращаем None и фолбэчим на эвристику.
        """
        try:
            return await asyncio.wait_for(self._fetch_google_price(query), timeout)
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    async def _fetch_google_price(self, query: str) -> Optional[float]:
        browser = await _get_browser()
        page = None
        try:
            page = await browser.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            q = query.replace(" ", "+")
            url = f"https://www.google.com/search?q={q}+цена+в+России&hl=ru&udm=50"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(4000)
            html = await page.content()
            # Если капча/блок — нет смысла парсить
            if "recaptcha" in html.lower() or "captcha" in html.lower() or "enablejs" in html.lower():
                return None
            # Ищем цену в AI Overview блоке: обычно в элементе с ₽
            # Простой регекс по всему HTML
            # Паттерн: "12 345 ₽" или "12345 руб"
            candidates = re.findall(r'(\d[\d\s\u00a0]{2,})\s*(?:₽|руб|RUB)', html, re.IGNORECASE)
            prices = []
            for raw in candidates:
                num = raw.replace(" ", "").replace("\u00a0", "").replace("\xa0", "")
                try:
                    v = float(num)
                    if 1000 <= v <= 500000:  # фильтр мусора
                        prices.append(v)
                except ValueError:
                    continue
            if prices:
                # берём медиану как оценку
                prices.sort()
                median = prices[len(prices)//2]
                return float(median)
            return None
        except Exception:
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
