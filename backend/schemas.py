from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    name: str
    price: float
    store: Optional[str] = None
    url: Optional[str] = None


class ProductCreate(ProductBase):
    search_id: int


class ProductResponse(ProductBase):
    id: int
    is_best_price: bool = False

    class Config:
        from_attributes = True


class QueryMeta(BaseModel):
    original: str
    canonical: str
    corrected: bool
    confidence: float
    category: Optional[str] = None


class SearchResult(BaseModel):
    query: str
    products: list[ProductResponse] = []
    min_price: float = 0
    max_price: float = 0
    total_results: int = 0
    query_meta: Optional[QueryMeta] = None

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
