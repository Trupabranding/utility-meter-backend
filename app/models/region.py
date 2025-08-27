from sqlalchemy import Column, String, DateTime, Enum, Integer, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from app.database import Base
import uuid
import enum


class RegionStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class Region(Base):
    __tablename__ = "regions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    coordinates = Column(Geography(geometry_type='POINT', srid=4326))
    radius = Column(Float)  # in meters
    agent_count = Column(Integer, default=0)
    meter_count = Column(Integer, default=0)
    status = Column(Enum(RegionStatus), nullable=False, default=RegionStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Region(id={self.id}, name='{self.name}', status='{self.status}')>"
