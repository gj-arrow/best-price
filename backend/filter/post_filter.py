import re
try:
    from backend.scrapers.aggregator import ScraperAggregator
except ModuleNotFoundError:
    from scrapers.aggregator import ScraperAggregator  # type: ignore

def is_accessory(name: str) -> bool:
    # делегируем к aggregator._is_accessory для консистентности
    try:
        from backend.scrapers.base import ProductData
    except ModuleNotFoundError:
        from scrapers.base import ProductData  # type: ignore
    return ScraperAggregator._is_accessory(ProductData(name=name, price=1, store="x", url="x"))

def filter_products(canonical: str, products: list) -> list:
    if not canonical or not products:
        return [p for p in products if not is_accessory(p.name)] if products else []
    # must_tokens — все слова canonical без стопслов
    stopwords = {"для","на","от","с","и","в","по","gb","гб"}
    must = [w.lower() for w in re.split(r"[\s\-]+", canonical.lower()) if w.lower() not in stopwords and len(w) >= 2]
    out = []
    for p in products:
        name_l = p.name.lower()
        # аксессуар — всегда отсев при фильтре B
        if is_accessory(p.name):
            continue
        # must_tokens ALL required — но storage опционален (256/512 не обязателен)
        # storage токены — только цифры+gb → не требуем строго
        required = [t for t in must if not re.match(r"^\d+gb?$", t) and not t.isdigit()]
        if not all(t in name_l for t in required):
            continue
        out.append(p)
    return out
