"""Tests for Ozon.ru scraper."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.scrapers.ozon import OzonScraper
from backend.scrapers.base import ProductData


class TestOzonScraper:
    """Test cases for OzonScraper."""

    def test_store_name(self):
        """Verify store_name is set correctly."""
        scraper = OzonScraper()
        assert scraper.store_name == "Ozon"

    def test_search_method_exists(self):
        """Verify search method exists and is callable."""
        scraper = OzonScraper()
        assert callable(scraper.search)

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        """Verify search returns a list."""
        scraper = OzonScraper()

        mock_html = """
        <html>
            <div data-widget="searchResult">
                <a data-widget="searchResult" href="/product/123">Test Product</a>
                <span data-widget="searchResultPrice">100 ₽</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test query")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_returns_list_of_products(self):
        """Verify search returns list of ProductData objects."""
        scraper = OzonScraper()

        mock_html = """
        <html>
            <div data-widget="searchResult">
                <a data-widget="searchResult" href="/product/123">Test Product</a>
                <span data-widget="searchResultPrice">100 ₽</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test query")

        assert isinstance(result, list)
        if result:
            assert all(isinstance(p, ProductData) for p in result)

    @pytest.mark.asyncio
    async def test_search_empty_response(self):
        """Verify search handles empty response."""
        scraper = OzonScraper()

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            result = await scraper.search("test query")

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_product_data_fields(self):
        """Verify ProductData has required fields: name, price, store, url."""
        scraper = OzonScraper()

        mock_html = """
        <html>
            <div data-widget="searchResult">
                <a data-widget="searchResult" href="/product/123">Test Product</a>
                <span data-widget="searchResultPrice">150 ₽</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test")

        if result:
            product = result[0]
            assert hasattr(product, 'name')
            assert hasattr(product, 'price')
            assert hasattr(product, 'store')
            assert hasattr(product, 'url')
            assert product.name == "Test Product"
            assert product.price == 150.0
            assert product.store == "Ozon"
            assert "ozon.ru" in product.url or product.url.startswith("/product/")

    @pytest.mark.asyncio
    async def test_search_url_construction(self):
        """Verify search constructs correct URL."""
        scraper = OzonScraper()

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            await scraper.search("iphone 15")

            mock_fetch.assert_called_once()
            called_url = mock_fetch.call_args[0][0]
            assert "https://www.ozon.ru/search/" in called_url
            assert "text=iphone%2015" in called_url

    def test_product_data_creation(self):
        """Verify ProductData can be created with required fields."""
        product = ProductData(
            name="Test Product",
            price=99.99,
            store="Ozon",
            url="https://www.ozon.ru/product/123"
        )
        assert product.name == "Test Product"
        assert product.price == 99.99
        assert product.store == "Ozon"
        assert product.url == "https://www.ozon.ru/product/123"

    @pytest.mark.asyncio
    async def test_search_multiple_products(self):
        """Verify search can return multiple products."""
        scraper = OzonScraper()

        mock_html = """
        <html>
            <div data-widget="searchResult">
                <a data-widget="searchResult" href="/product/1">Product One</a>
                <span data-widget="searchResultPrice">100 ₽</span>
            </div>
            <div data-widget="searchResult">
                <a data-widget="searchResult" href="/product/2">Product Two</a>
                <span data-widget="searchResultPrice">200 ₽</span>
            </div>
            <div data-widget="searchResult">
                <a data-widget="searchResult" href="/product/3">Product Three</a>
                <span data-widget="searchResultPrice">300 ₽</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test")

        assert len(result) == 3
        assert all(isinstance(p, ProductData) for p in result)
        assert result[0].name == "Product One"
        assert result[1].name == "Product Two"
        assert result[2].name == "Product Three"

    @pytest.mark.asyncio
    async def test_price_parsing_ruble_symbol(self):
        """Verify price parsing with ruble symbol."""
        scraper = OzonScraper()

        mock_html = """
        <html>
            <div data-widget="searchResult">
                <a data-widget="searchResult" href="/product/1">Test</a>
                <span data-widget="searchResultPrice">1 500 ₽</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test")

        assert len(result) == 1
        assert result[0].price == 1500.0

    @pytest.mark.asyncio
    async def test_price_parsing_rub_text(self):
        """Verify price parsing with 'руб' text."""
        scraper = OzonScraper()

        mock_html = """
        <html>
            <div data-widget="searchResult">
                <a data-widget="searchResult" href="/product/1">Test</a>
                <span class="price">2500 руб.</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test")

        assert len(result) == 1
        assert result[0].price == 2500.0
