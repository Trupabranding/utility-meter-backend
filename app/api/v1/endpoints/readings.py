from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, get_current_agent, require_manager_or_admin
from app.models.meter_reading import MeterReading
from app.models.meter import Meter
from app.models.agent import Agent
from app.models.user import User, UserRole
from app.schemas.meter_reading import MeterReadingCreate, MeterReadingUpdate, MeterReadingResponse, MeterReadingListResponse
from app.schemas.common import ResponseModel, PaginationParams, PaginationResponse, Location

router = APIRouter()


@router.get("/", response_model=ResponseModel[PaginationResponse[MeterReadingListResponse]])
async def get_readings(
    pagination: PaginationParams = Depends(),
    meter_id: Optional[str] = Query(None, description="Filter by meter ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    verified: Optional[bool] = Query(None, description="Filter by verification status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of meter readings with optional filtering."""
    query = select(MeterReading).options(
        selectinload(MeterReading.meter),
        selectinload(MeterReading.agent).selectinload(Agent.user)
    )
    
    # Apply filters
    if meter_id:
        query = query.where(MeterReading.meter_id == meter_id)
    
    if agent_id:
        query = query.where(MeterReading.agent_id == agent_id)
    
    if verified is not None:
        query = query.where(MeterReading.verified == verified)
    
    # Get total count
    count_query = select(MeterReading).where(query.whereclause) if query.whereclause else select(MeterReading)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination and ordering
    query = query.order_by(MeterReading.created_at.desc()).offset(
        (pagination.page - 1) * pagination.limit
    ).limit(pagination.limit)
    
    result = await db.execute(query)
    readings = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return ResponseModel(
        data=PaginationResponse(
            items=[
                MeterReadingListResponse(
                    id=reading.id,
                    meter_id=reading.meter_id,
                    agent_id=reading.agent_id,
                    reading_value=reading.reading_value,
                    verified=reading.verified,
                    reading_timestamp=reading.reading_timestamp,
                    created_at=reading.created_at,
                    meter={
                        "id": reading.meter.id,
                        "serial_number": reading.meter.serial_number,
                        "address": reading.meter.address
                    } if reading.meter else None,
                    agent={
                        "id": reading.agent.id,
                        "user": {
                            "id": reading.agent.user.id,
                            "name": reading.agent.user.name
                        } if reading.agent.user else None
                    } if reading.agent else None
                ) for reading in readings
            ],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@router.post("/", response_model=ResponseModel[MeterReadingResponse])
async def create_reading(
    reading_data: MeterReadingCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """Submit a new meter reading."""
    # Verify meter exists
    meter_result = await db.execute(select(Meter).where(Meter.id == reading_data.meter_id))
    meter = meter_result.scalar_one_or_none()
    
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meter not found"
        )
    
    # Create reading
    new_reading = MeterReading(
        meter_id=reading_data.meter_id,
        agent_id=current_agent.id,
        reading_value=reading_data.reading_value,
        photo_url=reading_data.photo_url,
        notes=reading_data.notes,
        reading_timestamp=reading_data.reading_timestamp
    )
    
    # Set location if provided
    if reading_data.location:
        new_reading.location = func.ST_SetSRID(
            func.ST_MakePoint(reading_data.location.longitude, reading_data.location.latitude), 4326
        )
    
    db.add(new_reading)
    await db.commit()
    await db.refresh(new_reading)
    
    # Update meter's last reading
    meter.last_reading = str(reading_data.reading_value)
    await db.commit()
    
    return ResponseModel(
        data=MeterReadingResponse(
            id=new_reading.id,
            meter_id=new_reading.meter_id,
            agent_id=new_reading.agent_id,
            reading_value=new_reading.reading_value,
            photo_url=new_reading.photo_url,
            notes=new_reading.notes,
            location=reading_data.location,
            verified=new_reading.verified,
            reading_timestamp=new_reading.reading_timestamp,
            created_at=new_reading.created_at
        ),
        message="Reading submitted successfully"
    )


@router.get("/{reading_id}", response_model=ResponseModel[MeterReadingResponse])
async def get_reading(
    reading_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific meter reading by ID."""
    result = await db.execute(
        select(MeterReading).options(
            selectinload(MeterReading.meter),
            selectinload(MeterReading.agent)
        ).where(MeterReading.id == reading_id)
    )
    reading = result.scalar_one_or_none()
    
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading not found"
        )
    
    # All authenticated users can access
    
    return ResponseModel(
        data=MeterReadingResponse(
            id=reading.id,
            meter_id=reading.meter_id,
            agent_id=reading.agent_id,
            reading_value=reading.reading_value,
            photo_url=reading.photo_url,
            notes=reading.notes,
            location=Location(
                latitude=float(reading.location.x) if reading.location else None,
                longitude=float(reading.location.y) if reading.location else None
            ) if reading.location else None,
            verified=reading.verified,
            reading_timestamp=reading.reading_timestamp,
            created_at=reading.created_at
        )
    )


@router.put("/{reading_id}", response_model=ResponseModel[MeterReadingResponse])
async def update_reading(
    reading_id: str,
    reading_update: MeterReadingUpdate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a meter reading (admin/manager only)."""
    result = await db.execute(select(MeterReading).where(MeterReading.id == reading_id))
    reading = result.scalar_one_or_none()
    
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading not found"
        )
    
    # Update fields
    update_data = reading_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "location" and value:
            # Update location
            reading.location = func.ST_SetSRID(
                func.ST_MakePoint(value.longitude, value.latitude), 4326
            )
        else:
            setattr(reading, field, value)
    
    await db.commit()
    await db.refresh(reading)
    
    return ResponseModel(
        data=MeterReadingResponse(
            id=reading.id,
            meter_id=reading.meter_id,
            agent_id=reading.agent_id,
            reading_value=reading.reading_value,
            photo_url=reading.photo_url,
            notes=reading.notes,
            location=Location(
                latitude=float(reading.location.x) if reading.location else None,
                longitude=float(reading.location.y) if reading.location else None
            ) if reading.location else None,
            verified=reading.verified,
            reading_timestamp=reading.reading_timestamp,
            created_at=reading.created_at
        ),
        message="Reading updated successfully"
    )


@router.get("/meter/{meter_id}", response_model=ResponseModel[list[MeterReadingListResponse]])
async def get_meter_readings(
    meter_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all readings for a specific meter."""
    # Verify meter exists
    meter_result = await db.execute(select(Meter).where(Meter.id == meter_id))
    if not meter_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meter not found"
        )
    
    base_query = (
        select(MeterReading)
        .options(selectinload(MeterReading.meter), selectinload(MeterReading.agent))
        .where(MeterReading.meter_id == meter_id)
        .order_by(MeterReading.created_at.desc())
    )
    
    result = await db.execute(base_query)
    readings = result.scalars().all()
    
    return ResponseModel(
        data=[
            MeterReadingListResponse(
                id=reading.id,
                meter_id=reading.meter_id,
                agent_id=reading.agent_id,
                reading_value=reading.reading_value,
                verified=reading.verified,
                reading_timestamp=reading.reading_timestamp,
                created_at=reading.created_at,
                meter={
                    "id": reading.meter.id,
                    "serial_number": reading.meter.serial_number,
                    "address": reading.meter.address
                } if reading.meter else None,
                agent={
                    "id": reading.agent.id,
                    "user": {
                        "id": reading.agent.user.id,
                        "name": reading.agent.user.name
                    } if reading.agent.user else None
                } if reading.agent else None
            ) for reading in readings
        ]
    )


@router.post("/{reading_id}/verify", response_model=ResponseModel)
async def verify_reading(
    reading_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Verify a meter reading (admin/manager only)."""
    result = await db.execute(select(MeterReading).where(MeterReading.id == reading_id))
    reading = result.scalar_one_or_none()
    
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading not found"
        )
    
    reading.verified = True
    await db.commit()
    
    return ResponseModel(message="Reading verified successfully")
