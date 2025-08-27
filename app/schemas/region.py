from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.region import RegionStatus
from app.schemas.common import Location


class RegionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    radius: Optional[float] = Field(None, ge=0)  # in meters


class RegionCreate(RegionBase):
    location: Optional[Location] = None


class RegionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[Location] = None
    radius: Optional[float] = Field(None, ge=0)
    status: Optional[RegionStatus] = None


class RegionResponse(RegionBase):
    id: UUID
    location: Optional[Location] = None
    agent_count: int
    meter_count: int
    status: RegionStatus
    created_at: datetime
    updated_at: Optional[datetime] = None


class RegionListResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    location: Optional[Location] = None
    radius: Optional[float] = None
    agent_count: int
    meter_count: int
    status: RegionStatus
    created_at: datetime


class RegionStats(BaseModel):
    total_agents: int
    total_meters: int
    active_assignments: int
    completed_assignments: int
    average_completion_time: Optional[float] = None
