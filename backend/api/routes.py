from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
try:
    from backend.database import get_db
    from backend.models import Search, Product
    from backend.schemas import SearchResult, ProductResponse, QueryMeta
    from backend.scrapers.aggregator import ScraperAggregator
    from backend.normalizer.query_normalizer import QueryNormalizer
    from backend.filter.post_filter import filter_products
except ModuleNotFoundError:
    from database import get_db  # type: ignore
    from models import Search, Product  # type: ignore
    from schemas import SearchResult, ProductResponse, QueryMeta  # type: ignore
    from scrapers.aggregator import ScraperAggregator  # type: ignore
    from normalizer.query_normalizer import QueryNormalizer  # type: ignore
    from filter.post_filter import filter_products  # type: ignore

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResult)
async def search_products(
    q: str,
    include_kufar: bool = False,
    no_correct: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    normalizer = QueryNormalizer(db=db)
    norm = await normalizer.normalize(q, no_correct=no_correct)
    canonical = norm.canonical

    search = Search(query=q)  # храним original
    db.add(search)
    await db.commit()
    await db.refresh(search)

    aggregator = ScraperAggregator(include_kufar=include_kufar)
    try:
        products_data = await aggregator.search_all(canonical, include_kufar=include_kufar)
    finally:
        await aggregator.close()

    # post_filter по canonical
    filtered = filter_products(canonical, products_data)
    # fallback: если canonical 0 но original дал бы результаты — ретрай original (опционально, пока возвращаем 0)
    # для MVP: если filtered пусто и canonical != original, можно показать пусто с query_meta
    db_products = [Product(search_id=search.id, name=p.name, price=p.price, store=p.store, url=p.url) for p in filtered]
    db.add_all(db_products)
    await db.commit()

    response_products = [ProductResponse(id=0, name=p.name, price=p.price, store=p.store, url=p.url, is_best_price=(i==0)) for i, p in enumerate(filtered)]
    prices = [p.price for p in filtered]
    query_meta = QueryMeta(original=norm.original, canonical=norm.canonical, corrected=norm.corrected, confidence=norm.confidence, category=norm.category)
    if not filtered:
        return SearchResult(query=q, products=[], min_price=0, max_price=0, total_results=0, query_meta=query_meta)
    return SearchResult(query=q, products=response_products[:30], min_price=min(prices), max_price=max(prices), total_results=len(filtered), query_meta=query_meta)
