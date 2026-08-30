from backend.scrapers.base import ProductData
from backend.filter.post_filter import filter_products, is_accessory

def _p(name): return ProductData(name=name, price=100, store="Onliner", url="http://x")

def test_accessory_flag():
    assert is_accessory("Чехол для iPhone 15 Pro Max") is True
    assert is_accessory("Смартфон Apple iPhone 15 Pro Max 256GB") is False
    assert is_accessory("Для iPhone 15 чехол") is True

def test_must_tokens_pro_max():
    products = [
        _p("Смартфон Apple iPhone 15 Pro Max 256GB"),
        _p("Смартфон Apple iPhone 15 128GB"),  # без pro max → отсев
        _p("Смартфон Apple iPhone 15 Pro Max 512GB"),  # другой объём → pass
        _p("Чехол для iPhone 15 Pro Max"),  # аксессуар → отсев
    ]
    out = filter_products("iphone 15 pro max", products)
    names = [p.name for p in out]
    assert "Смартфон Apple iPhone 15 Pro Max 256GB" in names
    assert "Смартфон Apple iPhone 15 Pro Max 512GB" in names
    assert "Смартфон Apple iPhone 15 128GB" not in names
    assert "Чехол для iPhone 15 Pro Max" not in names

def test_empty():
    assert filter_products("iphone 15 pro max", []) == []
