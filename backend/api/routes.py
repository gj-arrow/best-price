from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Search, Product
from schemas import SearchResult, ProductResponse
from scrapers.aggregator import ScraperAggregator

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResult)
async def search_products(q: str, db: AsyncSession = Depends(get_db)):
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    
    search = Search(query=q)
    db.add(search)
    await db.commit()
    await db.refresh(search)
    
    aggregator = ScraperAggregator()
    try:
        products_data = await aggregator.search_all(q)
    finally:
        await aggregator.close()
    
    if not products_data:
        return SearchResult(query=q, products=[], min_price=0, max_price=0, total_results=0)
    
    db_products = [Product(search_id=search.id, name=p.name, price=p.price, store=p.store, url=p.url) for p in products_data]
    db.add_all(db_products)
    await db.commit()
    
    response_products = [ProductResponse(id=0, name=p.name, price=p.price, store=p.store, url=p.url, is_best_price=(i==0)) for i, p in enumerate(products_data)]
    prices = [p.price for p in products_data]
    
    return SearchResult(query=q, products=response_products[:30], min_price=min(prices), max_price=max(prices), total_results=len(products_data))
