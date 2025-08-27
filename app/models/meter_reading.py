from sqlalchemy import Column, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from app.database import Base
import uuid


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meter_id = Column(UUID(as_uuid=True), ForeignKey("meters.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    reading_value = Column(Float, nullable=False)
    photo_url = Column(String(500))
    notes = Column(Text)
    location = Column(Geography(geometry_type='POINT', srid=4326))
    verified = Column(Boolean, default=False)
    reading_timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    meter = relationship("Meter", back_populates="readings")
    agent = relationship("Agent", back_populates="readings")

    def __repr__(self):
        return f"<MeterReading(id={self.id}, meter_id={self.meter_id}, value={self.reading_value})>"
