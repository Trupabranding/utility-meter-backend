from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.meter_assignment import AssignmentStatus


class MeterAssignmentBase(BaseModel):
    estimated_time: Optional[int] = Field(None, ge=1)  # in minutes


class MeterAssignmentCreate(MeterAssignmentBase):
    meter_id: UUID
    agent_id: UUID


class MeterAssignmentUpdate(BaseModel):
    status: Optional[AssignmentStatus] = None
    estimated_time: Optional[int] = Field(None, ge=1)
    completion_notes: Optional[str] = None


class MeterAssignmentResponse(MeterAssignmentBase):
    id: UUID
    meter_id: UUID
    agent_id: UUID
    status: AssignmentStatus
    assigned_at: datetime
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    meter: Optional[dict] = None
    agent: Optional[dict] = None


class MeterAssignmentListResponse(BaseModel):
    id: UUID
    meter_id: UUID
    agent_id: UUID
    status: AssignmentStatus
    estimated_time: Optional[int] = None
    assigned_at: datetime
    completed_at: Optional[datetime] = None
    meter: Optional[dict] = None
    agent: Optional[dict] = None


class BulkAssignmentRequest(BaseModel):
    meter_ids: list[UUID] = Field(..., min_items=1)
    agent_id: Optional[UUID] = None  # If None, auto-assign
    estimated_time: Optional[int] = Field(None, ge=1)
