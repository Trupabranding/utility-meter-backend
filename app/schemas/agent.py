from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.agent import AgentStatus
from app.schemas.common import Location


class AgentBase(BaseModel):
    location_id: Optional[str] = None
    max_load: int = Field(10, ge=1, le=50)
    status: AgentStatus = AgentStatus.AVAILABLE


class AgentCreate(AgentBase):
    user_id: UUID
    location: Optional[Location] = None


class AgentUpdate(BaseModel):
    location_id: Optional[str] = None
    current_load: Optional[int] = Field(None, ge=0, le=50)
    max_load: Optional[int] = Field(None, ge=1, le=50)
    status: Optional[AgentStatus] = None
    location: Optional[Location] = None
    avatar_url: Optional[str] = None


class AgentResponse(AgentBase):
    id: UUID
    user_id: UUID
    current_load: int
    location: Optional[Location] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    user: Optional[dict] = None


class AgentStats(BaseModel):
    total_assignments: int
    completed_assignments: int
    pending_assignments: int
    total_readings: int
    average_completion_time: Optional[float] = None
    success_rate: float


class AgentListResponse(BaseModel):
    id: UUID
    user_id: UUID
    current_load: int
    max_load: int
    status: AgentStatus
    location: Optional[Location] = None
    created_at: datetime
    user: Optional[dict] = None
