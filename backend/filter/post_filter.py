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
    # нормализуем единицы измерения в must: 45mm → 45 mm оба варианта
    def _norm(s: str) -> str:
        return s.replace("мм", "mm").replace("см", "cm").replace("гб", "gb")
    must_norm = [_norm(w) for w in must]
    out = []
    for p in products:
        name_l = _norm(p.name.lower())
        # для 45mm → матчим и 45 мм (разнесённые)
        name_nospace = re.sub(r"[^a-z0-9]", "", name_l)
        if is_accessory(p.name):
            continue
        # storage опционален, модельные цифры (15,17) — обязательны
        required = [t for t in must_norm if t not in storage_sizes and not re.match(r"^\d+gb?$", t)]
        if "galaxy" in must_norm and "samsung" in required:
            required = [t for t in required if t != "samsung"]
        ok = True
        for t in required:
            if t in name_l or t in name_nospace:
                continue
            # 45mm в canonical, а в имени 45 мм → t=45mm, name_l=45 мм → проверяем число + mm
            if re.match(r"^\d+mm$", t):
                num = re.match(r"^(\d+)mm$", t).group(1)
                if num in name_l and "mm" in name_l:
                    continue
            if re.match(r"^\d+cm$", t):
                num = re.match(r"^(\d+)cm$", t).group(1)
                if num in name_l and "cm" in name_l:
                    continue
            ok = False
            break
        if not ok:
            continue
        out.append(p)
    return out
