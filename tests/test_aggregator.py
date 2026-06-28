"""Tests for ScraperAggregator."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.scrapers.aggregator import ScraperAggregator
from backend.scrapers.base import ProductData


class TestScraperAggregator:
    """Test cases for ScraperAggregator."""

    def test_init_creates_all_six_scrapers(self):
        """Verify aggregator initializes all 6 scrapers."""
        aggregator = ScraperAggregator()
        
        assert len(aggregator.scrapers) == 6
        
        # Check scraper types
        scraper_types = [type(s).__name__ for s in aggregator.scrapers]
        assert "OnlinerScraper" in scraper_types
        assert "WildberriesScraper" in scraper_types
        assert "OzonScraper" in scraper_types
        assert "ShopByScraper" in scraper_types
        assert "Home1kScraper" in scraper_types
        assert "Shop360Scraper" in scraper_types

    @pytest.mark.asyncio
    async def test_search_all_returns_sorted_by_price(self):
        """Verify search_all returns results sorted by price ascending."""
        aggregator = ScraperAggregator()
        
        # Create mock products with different prices
        mock_products = [
            ProductData(name="Expensive", price=999.0, store="Store1", url="http://s1.com"),
            ProductData(name="Cheap", price=10.0, store="Store2", url="http://s2.com"),
            ProductData(name="Medium", price=100.0, store="Store3", url="http://s3.com"),
        ]
        
        # Mock all scrapers to return subsets of products
        with patch.object(aggregator.scrapers[0], 'search', new_callable=AsyncMock) as mock1:
            with patch.object(aggregator.scrapers[1], 'search', new_callable=AsyncMock) as mock2:
                with patch.object(aggregator.scrapers[2], 'search', new_callable=AsyncMock) as mock3:
                    with patch.object(aggregator.scrapers[3], 'search', new_callable=AsyncMock) as mock4:
                        with patch.object(aggregator.scrapers[4], 'search', new_callable=AsyncMock) as mock5:
                            with patch.object(aggregator.scrapers[5], 'search', new_callable=AsyncMock) as mock6:
                                mock1.return_value = [mock_products[0]]
                                mock2.return_value = [mock_products[1]]
                                mock3.return_value = [mock_products[2]]
                                mock4.return_value = []
                                mock5.return_value = []
                                mock6.return_value = []
                                
                                result = await aggregator.search_all("test")
        
        assert len(result) == 3
        # Verify sorted by price ascending
        assert result[0].price == 10.0
        assert result[1].price == 100.0
        assert result[2].price == 999.0

    @pytest.mark.asyncio
    async def test_search_all_concurrent_execution(self):
        """Verify search_all executes all scrapers concurrently using asyncio.gather."""
        aggregator = ScraperAggregator()
        
        # Track which scrapers were called
        called_scrapers = []
        call_lock = asyncio.Lock()
        
        async def track_call(scraper_idx, delay=0.01):
            async with call_lock:
                called_scrapers.append(scraper_idx)
            await asyncio.sleep(delay)
            return []
        
        # Patch all scrapers with tracking functions
        from unittest.mock import patch
        from contextlib import ExitStack
        
        async def make_mock(idx):
            async def mock_impl(query):
                return await track_call(idx)
            return mock_impl
        
        patches = []
        for i in range(6):
            mock_func = await make_mock(i)
            patches.append(patch.object(aggregator.scrapers[i], 'search', mock_func))
        
        # Apply all patches at once
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            result = await aggregator.search_all("test")
        
        # All 6 scrapers should have been called
        assert len(called_scrapers) == 6
        assert set(called_scrapers) == {0, 1, 2, 3, 4, 5}

    @pytest.mark.asyncio
    async def test_search_all_graceful_degradation_on_exception(self):
        """Verify search_all handles scraper exceptions gracefully."""
        aggregator = ScraperAggregator()
        
        mock_product = ProductData(name="Working", price=50.0, store="Store", url="http://store.com")
        
        # Mock some scrapers to fail, others to succeed
        with patch.object(aggregator.scrapers[0], 'search', new_callable=AsyncMock) as mock1:
            with patch.object(aggregator.scrapers[1], 'search', new_callable=AsyncMock) as mock2:
                with patch.object(aggregator.scrapers[2], 'search', new_callable=AsyncMock) as mock3:
                    with patch.object(aggregator.scrapers[3], 'search', new_callable=AsyncMock) as mock4:
                        with patch.object(aggregator.scrapers[4], 'search', new_callable=AsyncMock) as mock5:
                            with patch.object(aggregator.scrapers[5], 'search', new_callable=AsyncMock) as mock6:
                                mock1.side_effect = Exception("Connection error")
                                mock2.return_value = [mock_product]
                                mock3.side_effect = TimeoutError("Timeout")
                                mock4.return_value = []
                                mock5.side_effect = RuntimeError("Runtime error")
                                mock6.return_value = [mock_product]
                                
                                result = await aggregator.search_all("test")
        
        # Should get results from working scrapers only
        assert len(result) == 2
        assert all(p.name == "Working" for p in result)

    @pytest.mark.asyncio
    async def test_search_all_empty_results(self):
        """Verify search_all handles all scrapers returning empty results."""
        aggregator = ScraperAggregator()
        
        # Mock all scrapers to return empty lists
        for scraper in aggregator.scrapers:
            with patch.object(scraper, 'search', new_callable=AsyncMock) as mock:
                mock.return_value = []
        
        # Need to patch all at once
        with patch.object(aggregator.scrapers[0], 'search', new_callable=AsyncMock) as m1:
            with patch.object(aggregator.scrapers[1], 'search', new_callable=AsyncMock) as m2:
                with patch.object(aggregator.scrapers[2], 'search', new_callable=AsyncMock) as m3:
                    with patch.object(aggregator.scrapers[3], 'search', new_callable=AsyncMock) as m4:
                        with patch.object(aggregator.scrapers[4], 'search', new_callable=AsyncMock) as m5:
                            with patch.object(aggregator.scrapers[5], 'search', new_callable=AsyncMock) as m6:
                                m1.return_value = []
                                m2.return_value = []
                                m3.return_value = []
                                m4.return_value = []
                                m5.return_value = []
                                m6.return_value = []
                                
                                result = await aggregator.search_all("test")
        
        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_all_all_scrapers_fail(self):
        """Verify search_all returns empty list when all scrapers fail."""
        aggregator = ScraperAggregator()
        
        # Mock all scrapers to raise exceptions
        with patch.object(aggregator.scrapers[0], 'search', new_callable=AsyncMock) as m1:
            with patch.object(aggregator.scrapers[1], 'search', new_callable=AsyncMock) as m2:
                with patch.object(aggregator.scrapers[2], 'search', new_callable=AsyncMock) as m3:
                    with patch.object(aggregator.scrapers[3], 'search', new_callable=AsyncMock) as m4:
                        with patch.object(aggregator.scrapers[4], 'search', new_callable=AsyncMock) as m5:
                            with patch.object(aggregator.scrapers[5], 'search', new_callable=AsyncMock) as m6:
                                m1.side_effect = Exception("Error 1")
                                m2.side_effect = Exception("Error 2")
                                m3.side_effect = Exception("Error 3")
                                m4.side_effect = Exception("Error 4")
                                m5.side_effect = Exception("Error 5")
                                m6.side_effect = Exception("Error 6")
                                
                                result = await aggregator.search_all("test")
        
        assert result == []

    @pytest.mark.asyncio
    async def test_close_calls_all_scrapers(self):
        """Verify close cleans up all scrapers."""
        aggregator = ScraperAggregator()
        
        # Mock close methods
        close_mocks = []
        for scraper in aggregator.scrapers:
            mock = AsyncMock()
            close_mocks.append(mock)
            scraper.close = mock
        
        await aggregator.close()
        
        # All scrapers should have been closed
        for mock in close_mocks:
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_all_mixed_results(self):
        """Verify search_all handles mix of results, empty lists, and exceptions."""
        aggregator = ScraperAggregator()
        
        products = [
            ProductData(name="P1", price=25.0, store="S1", url="http://s1.com/1"),
            ProductData(name="P2", price=75.0, store="S2", url="http://s2.com/2"),
            ProductData(name="P3", price=50.0, store="S3", url="http://s3.com/3"),
        ]
        
        with patch.object(aggregator.scrapers[0], 'search', new_callable=AsyncMock) as m1:
            with patch.object(aggregator.scrapers[1], 'search', new_callable=AsyncMock) as m2:
                with patch.object(aggregator.scrapers[2], 'search', new_callable=AsyncMock) as m3:
                    with patch.object(aggregator.scrapers[3], 'search', new_callable=AsyncMock) as m4:
                        with patch.object(aggregator.scrapers[4], 'search', new_callable=AsyncMock) as m5:
                            with patch.object(aggregator.scrapers[5], 'search', new_callable=AsyncMock) as m6:
                                m1.return_value = [products[0]]  # Success
                                m2.side_effect = Exception("Fail")  # Exception
                                m3.return_value = []  # Empty
                                m4.return_value = [products[1]]  # Success
                                m5.side_effect = TimeoutError("Timeout")  # Exception
                                m6.return_value = [products[2]]  # Success
                                
                                result = await aggregator.search_all("test")
        
        # Should get 3 products from successful scrapers
        assert len(result) == 3
        # Should be sorted by price
        assert result[0].price == 25.0
        assert result[1].price == 50.0
        assert result[2].price == 75.0


import asyncio
