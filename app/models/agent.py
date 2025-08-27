from sqlalchemy import Column, String, DateTime, Enum, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from app.database import Base
import uuid
import enum


class AgentStatus(str, enum.Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    ON_BREAK = "on_break"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    location_id = Column(String(100))
    current_load = Column(Integer, default=0)
    max_load = Column(Integer, default=10)
    status = Column(Enum(AgentStatus), nullable=False, default=AgentStatus.AVAILABLE)
    location = Column(Geography(geometry_type='POINT', srid=4326))
    avatar_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="agent")
    assignments = relationship("MeterAssignment", back_populates="agent")
    readings = relationship("MeterReading", back_populates="agent")
    approval_requests = relationship("MeterApprovalRequest", back_populates="agent")

    def __repr__(self):
        return f"<Agent(id={self.id}, user_id={self.user_id}, status='{self.status}')>"
