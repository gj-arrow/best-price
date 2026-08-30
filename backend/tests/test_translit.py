from backend.normalizer.translit import transliterate

def test_cyrillic_brand():
    assert transliterate("айфон 15 про макс") == "iphone 15 pro max"

def test_yo_normalization():
    assert transliterate("ёж") == "ezh"

def test_mixed():
    assert transliterate("Самсунг ТВ 55") == "samsung tv 55"

def test_phrase_with_storage():
    assert transliterate("айфон 15 про макс 256") == "iphone 15 pro max 256"

def test_already_latin_unchanged():
    assert transliterate("iphone 15 pro max") == "iphone 15 pro max"

def test_pylesos():
    assert transliterate("пылесос") == "vacuum"
