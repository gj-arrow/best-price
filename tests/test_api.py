import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_search_products_valid_query(client):
    response = await client.get("/api/search?q=laptop")
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert data["query"] == "laptop"
    assert "products" in data
    assert "min_price" in data
    assert "max_price" in data
    assert "total_results" in data


@pytest.mark.asyncio
async def test_search_products_empty_query(client):
    response = await client.get("/api/search?q=")
    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_search_products_short_query(client):
    response = await client.get("/api/search?q=a")
    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_search_products_no_query(client):
    response = await client.get("/api/search")
    assert response.status_code == 422
