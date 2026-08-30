from dataclasses import dataclass
import os

try:
    from backend.normalizer.translit import transliterate
except ModuleNotFoundError:
    from normalizer.translit import transliterate
try:
    from backend.normalizer.fuzzy_dict import fuzzy_match
except ModuleNotFoundError:
    from normalizer.fuzzy_dict import fuzzy_match
try:
    from backend.normalizer.llm_normalizer import llm_normalize
except ModuleNotFoundError:
    from normalizer.llm_normalizer import llm_normalize
try:
    from backend.normalizer.cache import get_cached, set_cached
except ModuleNotFoundError:
    from normalizer.cache import get_cached, set_cached

@dataclass
class NormalizeResult:
    original: str
    canonical: str
    confidence: float
    category: str
    corrected: bool

def _infer_category(canonical: str) -> str:
    c = canonical.lower()
    if "iphone" in c or "galaxy" in c or "redmi" in c or "xiaomi" in c and "tv" not in c:
        return "smartphone"
    if "tv" in c:
        return "tv"
    if "vacuum" in c or "пылесос" in c:
        return "vacuum"
    return "other"

class QueryNormalizer:
    def __init__(self, db=None):
        self.db = db
        self.enabled = os.getenv("NORMALIZER_ENABLED", "true").lower() != "false"

    async def normalize(self, q: str, no_correct: bool = False) -> NormalizeResult:
        original = q.strip()
        if not self.enabled or no_correct or len(original) < 2:
            return NormalizeResult(original, original, 1.0, _infer_category(original), False)
        # cache
        if self.db is not None:
            cached = await get_cached(self.db, original)
            if cached:
                return NormalizeResult(original, cached.canonical, cached.confidence, cached.category or _infer_category(cached.canonical), cached.canonical != original)
        # translit — лёгкая предобработка перед AI (опц)
        latin = transliterate(original)
        # 1) Free AI (Pollinations) — основной путь, без словаря, generic для любого товара
        llm = await llm_normalize(latin)
        if llm:
            canonical, conf, cat = llm
            cat = cat or _infer_category(canonical)
            if conf >= 0.65:
                if self.db is not None:
                    await set_cached(self.db, original, canonical, conf, cat)
                return NormalizeResult(original, canonical, conf, cat, canonical.lower() != original.lower())
        # 2) Fuzzy словарь — оффлайн fallback если AI недоступен (host без интернета)
        m = fuzzy_match(latin)
        if m:
            canonical, conf = m
            cat = _infer_category(canonical)
            if self.db is not None:
                await set_cached(self.db, original, canonical, conf, cat)
            return NormalizeResult(original, canonical, conf, cat, canonical != original)
        # 3) fallback — транслит как canonical
        if latin != original:
            return NormalizeResult(original, latin, 0.8, _infer_category(latin), True)
        return NormalizeResult(original, original, 1.0, _infer_category(original), False)
