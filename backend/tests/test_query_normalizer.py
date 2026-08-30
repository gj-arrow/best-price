import pytest
from backend.normalizer.query_normalizer import QueryNormalizer

@pytest.mark.asyncio
async def test_normalize_cyrillic():
    n = QueryNormalizer(db=None)  # db None → без кэша
    r = await n.normalize("айфон 15 про макс 256")
    assert "iphone" in r.canonical
    assert r.corrected is True
    assert r.confidence > 0.85

@pytest.mark.asyncio
async def test_no_correct_flag():
    n = QueryNormalizer(db=None)
    r = await n.normalize("айфон 15 про макс", no_correct=True)
    assert r.canonical == "айфон 15 про макс"
    assert r.corrected is False

@pytest.mark.asyncio
async def test_latin_no_correction():
    n = QueryNormalizer(db=None)
    r = await n.normalize("iphone 15 pro max")
    assert r.canonical == "iphone 15 pro max"
