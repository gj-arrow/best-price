import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock


def _get_mock_db():
    """Create a mock AsyncSession that supports QueryNormalizer + routes DB ops."""
    mock_db = AsyncMock()
    # get_cached uses db.execute -> needs scalar_one_or_none returning None (no cache)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    # routes: db.add / db.add_all / commit / refresh
    def _add(obj):
        # simulate autoincrement id for Search
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = 1
    mock_db.add = MagicMock(side_effect=_add)
    mock_db.add_all = MagicMock(side_effect=lambda objs: [setattr(o, "id", i+1) for i, o in enumerate(objs)])
    mock_db.commit = AsyncMock(return_value=None)
    mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", getattr(obj, "id", 1)))
    return mock_db


def _override_dependency(mock_db):
    async def _override():
        yield mock_db
    return _override


def test_search_cyrillic_returns_query_meta():
    from backend.main import app
    try:
        from backend.database import get_db
    except ModuleNotFoundError:
        from database import get_db  # type: ignore

    mock_products = [
        type("P", (), {"name": "Смартфон Apple iPhone 15 Pro Max 256GB", "price": 3000, "store": "Onliner", "url": "http://x"})(),
    ]
    mock_db = _get_mock_db()
    app.dependency_overrides[get_db] = _override_dependency(mock_db)
    try:
        with patch("backend.api.routes.ScraperAggregator") as MockAgg:
            MockAgg.return_value.search_all = AsyncMock(return_value=mock_products)
            MockAgg.return_value.close = AsyncMock(return_value=None)
            c = TestClient(app)
            r = c.get("/api/search?q=айфон 15 про макс")
            assert r.status_code == 200, r.text
            data = r.json()
            assert "query_meta" in data, f"query_meta missing in {data}"
            assert data["query_meta"]["corrected"] is True
            assert "iphone" in data["query_meta"]["canonical"].lower()
    finally:
        app.dependency_overrides.clear()


def test_no_correct_flag():
    from backend.main import app
    try:
        from backend.database import get_db
    except ModuleNotFoundError:
        from database import get_db  # type: ignore

    mock_db = _get_mock_db()
    app.dependency_overrides[get_db] = _override_dependency(mock_db)
    try:
        with patch("backend.api.routes.ScraperAggregator") as MockAgg:
            MockAgg.return_value.search_all = AsyncMock(return_value=[])
            MockAgg.return_value.close = AsyncMock(return_value=None)
            c = TestClient(app)
            r = c.get("/api/search?q=айфон 15 про макс&no_correct=1")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["query_meta"]["corrected"] is False
    finally:
        app.dependency_overrides.clear()
