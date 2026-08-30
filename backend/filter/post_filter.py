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
    # must_tokens — все слова canonical без стопслов; apple/samsung опциональны если есть модель (iphone/galaxy)
    stopwords = {"для","на","от","с","и","в","по","gb","гб","apple"}
    # storage sizes optional (не требуем точный объём)
    storage_sizes = {"32","64","128","256","512","1024","2048","256gb","512gb","128gb","64gb"}
    must = [w.lower() for w in re.split(r"[\s\-]+", canonical.lower()) if w.lower() not in stopwords and len(w) >= 2]
    out = []
    for p in products:
        name_l = p.name.lower()
        if is_accessory(p.name):
            continue
        # storage опционален, модельные цифры (15,17) — обязательны
        required = [t for t in must if t not in storage_sizes and not re.match(r"^\d+gb?$", t)]
        # но если t isdigit и в storage_sizes — пропускаем, иначе требуем
        # фактически выше уже исключает storage, оставляем 15, 17 и т.д.
        # костыль: если required содержит iphone, apple уже убран; если galaxy — samsung опционален (уже стоп? нет, samsung остаётся, но galaxy уже уникален)
        # для galaxy делаем samsung опциональным если есть galaxy
        if "galaxy" in must and "samsung" in required:
            required = [t for t in required if t != "samsung"]
        if not all(t in name_l for t in required):
            continue
        out.append(p)
    return out
