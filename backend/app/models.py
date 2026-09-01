from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Search(Base):
    __tablename__ = "searches"

    id = Column(Integer, primary_key=True, index=True)
    water_body = Column(String, nullable=False)
    water_body_normalized = Column(String, nullable=True)
    species = Column(String, nullable=False)
    season = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    summary = Column(Text, nullable=True)
    best_conditions = Column(Text, nullable=True)

    techniques = relationship(
        "Technique", back_populates="search", cascade="all, delete-orphan",
        order_by="Technique.order_index",
    )
    gear_items = relationship(
        "GearItem", back_populates="search", cascade="all, delete-orphan"
    )


class Technique(Base):
    __tablename__ = "techniques"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    search = relationship("Search", back_populates="techniques")


class GearItem(Base):
    __tablename__ = "gear_items"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False)
    category = Column(String, nullable=False)
    name = Column(String, nullable=False)
    notes = Column(Text, nullable=True)

    search = relationship("Search", back_populates="gear_items")
