from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


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
