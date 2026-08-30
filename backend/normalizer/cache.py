from sqlalchemy import select
# lazy import to avoid circular
async def get_cached(db, original: str):
    if db is None: return None
    try:
        from backend.models import QueryNormalization
    except ModuleNotFoundError:
        from models import QueryNormalization  # type: ignore
    res = await db.execute(select(QueryNormalization).where(QueryNormalization.original == original))
    return res.scalar_one_or_none()

async def set_cached(db, original: str, canonical: str, confidence: float, category: str | None):
    if db is None: return
    try:
        from backend.models import QueryNormalization
    except ModuleNotFoundError:
        from models import QueryNormalization  # type: ignore
    from datetime import datetime
    obj = QueryNormalization(original=original, canonical=canonical, confidence=confidence, category=category, hits=1, updated_at=datetime.utcnow())
    # upsert
    existing = await get_cached(db, original)
    if existing:
        existing.canonical = canonical
        existing.confidence = confidence
        existing.category = category
        existing.hits += 1
    else:
        db.add(obj)
    await db.commit()
