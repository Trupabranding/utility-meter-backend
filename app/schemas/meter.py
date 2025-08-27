from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from app.models.meter import MeterType, MeterPriority, MeterStatus
from app.schemas.common import Location


class MeterBase(BaseModel):
    serial_number: str = Field(..., min_length=1, max_length=255)
    address: str = Field(..., min_length=1)
    location_id: Optional[str] = None
    meter_type: MeterType
    priority: MeterPriority = MeterPriority.MEDIUM
    status: MeterStatus = MeterStatus.ACTIVE
    estimated_time: Optional[int] = Field(None, ge=1)  # in minutes
    owner: Optional[str] = None
    meter_metadata: Optional[Dict[str, Any]] = None


class MeterCreate(MeterBase):
    location: Optional[Location] = None


class MeterUpdate(BaseModel):
    address: Optional[str] = Field(None, min_length=1)
    location_id: Optional[str] = None
    priority: Optional[MeterPriority] = None
    status: Optional[MeterStatus] = None
    last_reading: Optional[str] = None
    estimated_time: Optional[int] = Field(None, ge=1)
    location: Optional[Location] = None
    owner: Optional[str] = None
    meter_metadata: Optional[Dict[str, Any]] = None


class MeterResponse(MeterBase):
    id: UUID
    last_reading: Optional[str] = None
    location: Optional[Location] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class MeterListResponse(BaseModel):
    id: UUID
    serial_number: str
    address: str
    meter_type: MeterType
    priority: MeterPriority
    status: MeterStatus
    location: Optional[Location] = None
    created_at: datetime


class MeterSearchParams(BaseModel):
    status: Optional[MeterStatus] = None
    meter_type: Optional[MeterType] = None
    priority: Optional[MeterPriority] = None
    location_id: Optional[str] = None
    assigned: Optional[bool] = None
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    radius: Optional[float] = Field(None, ge=0)  # in meters
    search: Optional[str] = None


class MeterNearbyParams(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius: float = Field(1000, ge=0)  # in meters
    limit: int = Field(20, ge=1, le=100)
