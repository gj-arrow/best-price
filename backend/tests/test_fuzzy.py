from backend.normalizer.fuzzy_dict import fuzzy_match

def test_exact_match():
    m = fuzzy_match("iphone 15 pro max")
    assert m is not None and m[0] == "iphone 15 pro max" and m[1] >= 0.95

def test_typo_pra():
    m = fuzzy_match("iphone 15 pra max")  # pra vs pro dist1
    assert m is not None and m[0] == "iphone 15 pro max" and m[1] > 0.85

def test_cyrillic_typo_via_translit():
    from backend.normalizer.translit import transliterate
    q = transliterate("айфон 15 пра макс")
    m = fuzzy_match(q)
    assert m is not None and "iphone 15 pro max" in m[0]

def test_xiaomi_tv():
    m = fuzzy_match("xiaomi tv 55")
    assert m is not None and m[1] > 0.85

def test_no_match_low_conf():
    m = fuzzy_match("чехол для iphone 15 pro max")
    # аксессуар не в словаре, confidence низкий → None
    assert m is None or m[1] < 0.85

def test_storage_variant():
    m = fuzzy_match("iphone 15 pro max 256")
    assert m is not None and "256" in m[0]
