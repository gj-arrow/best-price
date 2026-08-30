from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

try:
    from database import Base
except ModuleNotFoundError:
    from backend.database import Base


class Search(Base):
    __tablename__ = "searches"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String, nullable=True)

    products = relationship("Product", back_populates="search", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    store = Column(String, nullable=True)
    url = Column(String, nullable=True)
    cached_at = Column(DateTime, default=datetime.utcnow)

    search = relationship("Search", back_populates="products")


class QueryNormalization(Base):
    __tablename__ = "query_normalizations"
    original = Column(String, primary_key=True)
    canonical = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    hits = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow)
