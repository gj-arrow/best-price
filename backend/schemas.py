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


class SearchResult(BaseModel):
    query: str
    products: list[ProductResponse] = []
    min_price: float = 0
    max_price: float = 0
    total_results: int = 0

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
