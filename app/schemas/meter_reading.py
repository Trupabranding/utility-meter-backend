from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.common import Location


class MeterReadingBase(BaseModel):
    reading_value: float = Field(..., ge=0)
    notes: Optional[str] = None
    location: Optional[Location] = None


class MeterReadingCreate(MeterReadingBase):
    meter_id: UUID
    photo_url: Optional[str] = None
    reading_timestamp: datetime


class MeterReadingUpdate(BaseModel):
    reading_value: Optional[float] = Field(None, ge=0)
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    location: Optional[Location] = None
    verified: Optional[bool] = None


class MeterReadingResponse(MeterReadingBase):
    id: UUID
    meter_id: UUID
    agent_id: UUID
    photo_url: Optional[str] = None
    verified: bool
    reading_timestamp: datetime
    created_at: datetime
    meter: Optional[dict] = None
    agent: Optional[dict] = None


class MeterReadingListResponse(BaseModel):
    id: UUID
    meter_id: UUID
    agent_id: UUID
    reading_value: float
    verified: bool
    reading_timestamp: datetime
    created_at: datetime
    meter: Optional[dict] = None
    agent: Optional[dict] = None
