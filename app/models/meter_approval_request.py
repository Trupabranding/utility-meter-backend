from sqlalchemy import Column, String, DateTime, Enum, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
import enum


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_REVIEW = "under_review"


class MeterApprovalRequest(Base):
    __tablename__ = "meter_approval_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meter_id = Column(UUID(as_uuid=True), ForeignKey("meters.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    meter_data = Column(JSON, nullable=False)
    status = Column(Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING)
    submission_notes = Column(Text)
    review_notes = Column(Text)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True))

    # Relationships
    meter = relationship("Meter", back_populates="approval_requests")
    agent = relationship("Agent", back_populates="approval_requests")
    reviewer = relationship("User")

    def __repr__(self):
        return f"<MeterApprovalRequest(id={self.id}, meter_id={self.meter_id}, status='{self.status}')>"
