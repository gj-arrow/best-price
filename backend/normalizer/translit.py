import re

# 300 терминов — в MVP 40 ключевых, остальные расширяются без API
MAPPING = {
    "айфон": "iphone", "аифон": "iphone",
    "самсунг": "samsung", "сяоми": "xiaomi", "ксиоми": "xiaomi", "ксяоми": "xiaomi",
    "телек": "tv", "телик": "tv", "телевизор": "tv", "тв": "tv",
    "пылесос": "vacuum", "ноутбук": "laptop", "планшет": "tablet",
    "наушники": "headphones", "часы": "watch",
    "про": "pro", "макс": "max", "плюс": "plus", "ультра": "ultra",
    "еж": "ezh",
    "ё": "е", "й": "y",
}

# Для фразовой замены — сортируем по длине ключа убыв.
_SORTED_KEYS = sorted(MAPPING, key=len, reverse=True)

def transliterate(q: str) -> str:
    s = q.lower().strip()
    s = s.replace("ё", "е")
    # заменяем целые слова по словарю
    for k in _SORTED_KEYS:
        # только целые слова, кроме одиночных букв
        if len(k) == 1:
            continue
        s = re.sub(rf"\b{re.escape(k)}\b", MAPPING[k], s)
    # одиночные буквы после
    s = s.replace("ё", "е")
    # нормализуем пробелы
    s = re.sub(r"\s+", " ", s).strip()
    return s
