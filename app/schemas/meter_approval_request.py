from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from app.models.meter_approval_request import ApprovalStatus


class MeterApprovalRequestBase(BaseModel):
    submission_notes: Optional[str] = None


class MeterApprovalRequestCreate(MeterApprovalRequestBase):
    meter_id: UUID
    meter_data: Dict[str, Any] = Field(..., description="Meter data to be approved")


class MeterApprovalRequestUpdate(BaseModel):
    status: Optional[ApprovalStatus] = None
    review_notes: Optional[str] = None


class MeterApprovalRequestResponse(MeterApprovalRequestBase):
    id: UUID
    meter_id: UUID
    agent_id: UUID
    reviewer_id: Optional[UUID] = None
    meter_data: Dict[str, Any]
    status: ApprovalStatus
    review_notes: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    meter: Optional[dict] = None
    agent: Optional[dict] = None
    reviewer: Optional[dict] = None


class MeterApprovalRequestListResponse(BaseModel):
    id: UUID
    meter_id: UUID
    agent_id: UUID
    status: ApprovalStatus
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    meter: Optional[dict] = None
    agent: Optional[dict] = None
