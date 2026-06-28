"""Scraper modules and interfaces."""

from .base import IScraper, ProductData
from .onliner import OnlinerScraper
from .shopby import ShopByScraper
from .home1k import Home1kScraper
from .shop360 import Shop360Scraper
from .aggregator import ScraperAggregator

__all__ = [
    "IScraper",
    "ProductData",
    "OnlinerScraper",
    "ShopByScraper",
    "Home1kScraper",
    "Shop360Scraper",
    "ScraperAggregator",
]
