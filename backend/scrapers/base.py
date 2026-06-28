"""Base scraper interface and common data structures."""

import os
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


@dataclass
class ProductData:
    """Represents a scraped product."""

    name: str
    price: float
    store: str
    url: str


class IScraper(ABC):
    """Abstract base class for all store scrapers."""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a reusable aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=BROWSER_HEADERS,
                connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
            )
        return self._session

    @property
    @abstractmethod
    def store_name(self) -> str:
        """Return the name of the store this scraper targets."""
        pass

    @abstractmethod
    async def search(self, query: str) -> list[ProductData]:
        """
        Search for products matching the query.

        Args:
            query: Search term/product name

        Returns:
            List of ProductData objects matching the query
        """
        pass

    async def _fetch(self, url: str, timeout: int = 15) -> Optional[str]:
        """
        Fetch HTML content from a URL with browser-like headers.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            HTML content as string, or None if request failed
        """
        session = await self._get_session()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status in (403, 498, 429, 500):
                    return None  # Blocked or server error
                response.raise_for_status()
                return await response.text()
        except (aiohttp.ClientError, TimeoutError, ssl.SSLError) as e:
            print(f"Failed to fetch {url}: {e}")
            return None

    def _parse_html(self, html: str) -> BeautifulSoup:
        """
        Parse HTML content using BeautifulSoup.

        Args:
            html: Raw HTML string

        Returns:
            BeautifulSoup object for parsing
        """
        return BeautifulSoup(html, "html.parser")

    async def close(self) -> None:
        """Clean up resources (sessions, connections, etc.)."""
        if self._session and not self._session.closed:
            await self._session.close()


# ─── Playwright browser singleton ──────────────────────────────

_browser = None
_browser_playwright = None
_browser_refcount = 0


async def _get_browser():
    """Get or create the shared Playwright browser instance."""
    global _browser, _browser_playwright, _browser_refcount
    if _browser is None:
        _browser_playwright = await async_playwright().start()
        _browser = await _browser_playwright.chromium.launch(headless=True)
    _browser_refcount += 1
    return _browser


async def _release_browser():
    """Decrease browser refcount and close when last user is done."""
    global _browser, _browser_playwright, _browser_refcount
    _browser_refcount -= 1
    if _browser_refcount <= 0 and _browser:
        await _browser.close()
        await _browser_playwright.stop()
        _browser = None
        _browser_playwright = None


class BrowserScraper(IScraper):
    """
    Base class for scrapers that need a real browser (Playwright).

    These sites (Wildberries, Ozon) block plain HTTP requests
    with anti-bot protection. A real headless browser bypasses this.
    """

    async def _fetch_browser(self, url: str, timeout: int = 20) -> Optional[str]:
        """
        Fetch HTML using a real headless Chromium browser.

        Args:
            url: URL to navigate to
            timeout: Maximum wait time in seconds

        Returns:
            Full page HTML, or None on failure
        """
        browser = await _get_browser()
        page = None
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            # Give JS a moment to render products
            await page.wait_for_timeout(3000)
            html = await page.content()
            return html
        except Exception as e:
            print(f"Browser fetch failed for {url}: {e}")
            return None
        finally:
            if page:
                await page.close()
            await _release_browser()

    async def close(self) -> None:
        """Browser resources are managed globally; nothing extra to close."""
        pass
