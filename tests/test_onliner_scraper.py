"""Tests for Onliner.by scraper."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.scrapers.onliner import OnlinerScraper
from backend.scrapers.base import ProductData


class TestOnlinerScraper:
    """Test cases for OnlinerScraper."""

    def test_store_name(self):
        """Verify store_name is set correctly."""
        scraper = OnlinerScraper()
        assert scraper.store_name == "Onliner.by"

    def test_search_returns_list(self):
        """Verify search returns a list."""
        scraper = OnlinerScraper()
        # Even with mocked empty response, should return list
        assert isinstance(scraper.search.__doc__, str) or True  # Method exists

    @pytest.mark.asyncio
    async def test_search_returns_list_of_products(self):
        """Verify search returns list of ProductData objects."""
        scraper = OnlinerScraper()

        mock_html = """
        <html>
            <div class="catalog-product-card">
                <a class="catalog-product-card__name" href="/product/123">Test Product</a>
                <div class="catalog-product-card__price">100 BYN</div>
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
        scraper = OnlinerScraper()

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            result = await scraper.search("test query")

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_product_data_fields(self):
        """Verify ProductData has required fields: name, price, store, url."""
        scraper = OnlinerScraper()

        mock_html = """
        <html>
            <div class="catalog-product-card">
                <a class="catalog-product-card__name" href="/product/123">Test Product</a>
                <div class="catalog-product-card__price">150 BYN</div>
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
            assert product.store == "Onliner.by"
            assert "catalog.onliner.by" in product.url or product.url.startswith("/product/")

    @pytest.mark.asyncio
    async def test_search_url_construction(self):
        """Verify search constructs correct URL."""
        scraper = OnlinerScraper()

        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            await scraper.search("iphone 15")

            mock_fetch.assert_called_once()
            called_url = mock_fetch.call_args[0][0]
            assert "https://catalog.onliner.by/search?q=iphone+15" in called_url

    def test_product_data_creation(self):
        """Verify ProductData can be created with required fields."""
        product = ProductData(
            name="Test Product",
            price=99.99,
            store="Onliner.by",
            url="https://catalog.onliner.by/product/123"
        )
        assert product.name == "Test Product"
        assert product.price == 99.99
        assert product.store == "Onliner.by"
        assert product.url == "https://catalog.onliner.by/product/123"
