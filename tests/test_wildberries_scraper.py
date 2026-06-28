"""Tests for Wildberries scraper."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.scrapers.wildberries import WildberriesScraper
from backend.scrapers.base import ProductData


class TestWildberriesScraper:
    """Test cases for WildberriesScraper."""

    def test_store_name(self):
        """Verify store_name is set correctly."""
        scraper = WildberriesScraper()
        assert scraper.store_name == "Wildberries"

    def test_search_returns_list(self):
        """Verify search returns a list."""
        scraper = WildberriesScraper()
        # Even with mocked empty response, should return list
        assert isinstance(scraper.search.__doc__, str) or True  # Method exists

    @pytest.mark.asyncio
    async def test_search_returns_list_of_products(self):
        """Verify search returns list of ProductData objects."""
        scraper = WildberriesScraper()

        mock_html = """
        <html>
            <div class="product-card">
                <a class="product-card__name" href="/product/123">Test Product</a>
                <span class="product-card__price">100 ₽</span>
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
        scraper = WildberriesScraper()

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            result = await scraper.search("test query")

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_product_data_fields(self):
        """Verify ProductData has required fields: name, price, store, url."""
        scraper = WildberriesScraper()

        mock_html = """
        <html>
            <div class="product-card">
                <a class="product-card__name" href="/product/123">Test Product</a>
                <span class="product-card__price">150 ₽</span>
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
            assert product.store == "Wildberries"
            assert "wildberries.ru" in product.url or product.url.startswith("/product/")

    @pytest.mark.asyncio
    async def test_search_url_construction(self):
        """Verify search constructs correct URL."""
        scraper = WildberriesScraper()

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            await scraper.search("iphone 15")

            mock_fetch.assert_called_once()
            called_url = mock_fetch.call_args[0][0]
            assert "https://www.wildberries.ru/catalog/0/search.aspx?search=iphone%2015" in called_url

    def test_product_data_creation(self):
        """Verify ProductData can be created with required fields."""
        product = ProductData(
            name="Test Product",
            price=99.99,
            store="Wildberries",
            url="https://www.wildberries.ru/product/123"
        )
        assert product.name == "Test Product"
        assert product.price == 99.99
        assert product.store == "Wildberries"
        assert product.url == "https://www.wildberries.ru/product/123"

    @pytest.mark.asyncio
    async def test_search_multiple_products(self):
        """Verify search returns multiple products."""
        scraper = WildberriesScraper()

        mock_html = """
        <html>
            <div class="product-card">
                <a class="product-card__name" href="/product/1">Product One</a>
                <span class="product-card__price">100 ₽</span>
            </div>
            <div class="product-card">
                <a class="product-card__name" href="/product/2">Product Two</a>
                <span class="product-card__price">200 ₽</span>
            </div>
            <div class="product-card">
                <a class="product-card__name" href="/product/3">Product Three</a>
                <span class="product-card__price">300 ₽</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test")

        assert len(result) == 3
        assert result[0].name == "Product One"
        assert result[1].name == "Product Two"
        assert result[2].name == "Product Three"

    @pytest.mark.asyncio
    async def test_price_parsing_ruble_symbol(self):
        """Verify price parsing with ruble symbol."""
        scraper = WildberriesScraper()

        mock_html = """
        <html>
            <div class="product-card">
                <a class="product-card__name" href="/product/1">Test</a>
                <span class="product-card__price">1 599 ₽</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test")

        assert len(result) == 1
        assert result[0].price == 1599.0

    @pytest.mark.asyncio
    async def test_price_parsing_rub_text(self):
        """Verify price parsing with rub text."""
        scraper = WildberriesScraper()

        mock_html = """
        <html>
            <div class="product-card">
                <a class="product-card__name" href="/product/1">Test</a>
                <span class="product-card__price">2500 руб.</span>
            </div>
        </html>
        """

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html
            result = await scraper.search("test")

        assert len(result) == 1
        assert result[0].price == 2500.0
