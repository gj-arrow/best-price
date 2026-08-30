from rapidfuzz import fuzz, process

CANONICAL_MODELS = [
    "iphone 15 pro max", "iphone 15 pro max 256", "iphone 15 pro max 512",
    "iphone 15 pro", "iphone 15", "iphone 14 pro max", "iphone 14",
    "samsung galaxy s24 ultra", "samsung galaxy s24", "samsung galaxy a55",
    "xiaomi tv a pro 55", "xiaomi tv 55", "xiaomi redmi note 12", "xiaomi 13",
    "vacuum dyson v15", "laptop macbook air m2",
    # минимум 20 для MVP, расширяется до 500-800 из БД
]

THRESHOLD = 85  # confidence 0.85

def fuzzy_match(q: str) -> tuple[str, float] | None:
    s = q.lower().strip()
    if not s:
        return None
    # process.extractOne возвращает (choice, score, idx)
    best = process.extractOne(s, CANONICAL_MODELS, scorer=fuzz.ratio)
    if not best:
        return None
    canonical, score, _ = best
    conf = score / 100.0
    if conf < THRESHOLD / 100:
        return None
    return canonical, conf
