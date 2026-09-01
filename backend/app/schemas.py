from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WaterBodyLookupRequest(BaseModel):
    water_body: str


class WaterBodyLookupResponse(BaseModel):
    water_body_normalized: str
    species: list[str]


class SearchCreate(BaseModel):
    water_body: str
    water_body_normalized: Optional[str] = None
    species: str
    season: str


class TechniqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    title: str
    description: str


class GearItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    name: str
    notes: Optional[str] = None


class SearchListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    water_body: str
    water_body_normalized: Optional[str] = None
    species: str
    season: str
    created_at: datetime


class SearchDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    water_body: str
    water_body_normalized: Optional[str] = None
    species: str
    season: str
    created_at: datetime
    summary: Optional[str] = None
    best_conditions: Optional[str] = None
    techniques: list[TechniqueOut] = []
    gear_items: list[GearItemOut] = []
