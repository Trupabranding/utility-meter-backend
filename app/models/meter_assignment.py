from sqlalchemy import Column, String, DateTime, Enum, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
import enum


class AssignmentStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class MeterAssignment(Base):
    __tablename__ = "meter_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meter_id = Column(UUID(as_uuid=True), ForeignKey("meters.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    status = Column(Enum(AssignmentStatus), nullable=False, default=AssignmentStatus.PENDING)
    estimated_time = Column(Integer)  # in minutes
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    completion_notes = Column(Text)

    # Relationships
    meter = relationship("Meter", back_populates="assignments")
    agent = relationship("Agent", back_populates="assignments")

    def __repr__(self):
        return f"<MeterAssignment(id={self.id}, meter_id={self.meter_id}, agent_id={self.agent_id}, status='{self.status}')>"
