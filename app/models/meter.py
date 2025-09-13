from sqlalchemy import Column, String, DateTime, Enum, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from app.database import Base
import uuid
import enum


class MeterType(str, enum.Enum):
    DIGITAL = "digital"
    ANALOG = "analog"


class MeterPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MeterStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"


class Meter(Base):
    __tablename__ = "meters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial_number = Column(String(255), unique=True, nullable=False, index=True)
    address = Column(Text, nullable=False)
    location_id = Column(String(100))
    meter_type = Column(Enum(MeterType), nullable=False)
    priority = Column(Enum(MeterPriority), nullable=False, default=MeterPriority.MEDIUM)
    status = Column(Enum(MeterStatus), nullable=False, default=MeterStatus.ACTIVE)
    last_reading = Column(String(100))
    estimated_time = Column(Integer)  # in minutes
    coordinates = Column(Geography(geometry_type='POINT', srid=4326))
    owner = Column(String(255))
    meter_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    readings = relationship("MeterReading", back_populates="meter")
    assignments = relationship("MeterAssignment", back_populates="meter")
    approval_requests = relationship("MeterApprovalRequest", back_populates="meter")

    def __repr__(self):
        return f"<Meter(id={self.id}, serial_number='{self.serial_number}', type='{self.meter_type}')>"
