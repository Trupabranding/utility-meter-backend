from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_manager_or_admin
from app.models.meter import Meter, MeterType, MeterPriority, MeterStatus
from app.models.meter_assignment import MeterAssignment
from app.models.user import User
from app.schemas.meter import MeterCreate, MeterUpdate, MeterResponse, MeterListResponse, MeterSearchParams, MeterNearbyParams
from app.schemas.common import ResponseModel, PaginationParams, PaginationResponse, Location

router = APIRouter()


@router.get("/", response_model=ResponseModel[PaginationResponse[MeterListResponse]])
async def get_meters(
    pagination: PaginationParams = Depends(),
    status: Optional[MeterStatus] = Query(None, description="Filter by status"),
    meter_type: Optional[MeterType] = Query(None, description="Filter by meter type"),
    priority: Optional[MeterPriority] = Query(None, description="Filter by priority"),
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    assigned: Optional[bool] = Query(None, description="Filter by assignment status"),
    search: Optional[str] = Query(None, description="Search by serial number or address"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of meters with optional filtering."""
    query = select(Meter)
    
    # Apply filters
    if status:
        query = query.where(Meter.status == status)
    
    if meter_type:
        query = query.where(Meter.meter_type == meter_type)
    
    if priority:
        query = query.where(Meter.priority == priority)
    
    if location_id:
        query = query.where(Meter.location_id == location_id)
    
    if search:
        query = query.where(
            or_(
                Meter.serial_number.ilike(f"%{search}%"),
                Meter.address.ilike(f"%{search}%")
            )
        )
    
    if assigned is not None:
        # Subquery to check if meter has active assignments
        assignment_subquery = select(MeterAssignment.meter_id).where(
            MeterAssignment.status.in_(["pending", "in_progress"])
        ).distinct()
        
        if assigned:
            query = query.where(Meter.id.in_(assignment_subquery))
        else:
            query = query.where(~Meter.id.in_(assignment_subquery))
    
    # Get total count
    count_query = select(Meter).where(query.whereclause) if query.whereclause else select(Meter)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    query = query.offset((pagination.page - 1) * pagination.limit).limit(pagination.limit)
    
    result = await db.execute(query)
    meters = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return ResponseModel(
        data=PaginationResponse(
            items=[
                MeterListResponse(
                    id=meter.id,
                    serial_number=meter.serial_number,
                    address=meter.address,
                    meter_type=meter.meter_type,
                    priority=meter.priority,
                    status=meter.status,
                    location=Location(
                        latitude=float(meter.coordinates.x) if meter.coordinates else None,
                        longitude=float(meter.coordinates.y) if meter.coordinates else None
                    ) if meter.coordinates else None,
                    created_at=meter.created_at
                ) for meter in meters
            ],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@router.post("/", response_model=ResponseModel[MeterResponse])
async def create_meter(
    meter_data: MeterCreate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new meter using nested payload structure."""
    # Extract key fields from nested payload
    serial_number = meter_data.meterDetails.serialNumber
    meter_type = meter_data.meterDetails.meterType
    full_address = meter_data.locationAndAddress.fullAddress
    owner_name = meter_data.ownerInformation.ownerName
    initial_reading = meter_data.meterDetails.initialReading

    # Check if serial number already exists
    existing_meter = await db.execute(
        select(Meter).where(Meter.serial_number == serial_number)
    )
    if existing_meter.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meter with this serial number already exists"
        )

    # Compose metadata from the nested fields
    metadata = {
        "ownerInformation": meter_data.ownerInformation.model_dump(),
        "administrativeLocation": meter_data.locationAndAddress.administrativeLocation.model_dump(),
        "detailedLocationInformation": meter_data.detailedLocationInformation.model_dump(),
        "gpsCoordinates": meter_data.gpsCoordinates,
        "meterPhoto": meter_data.meterDetails.meterPhoto,
        "additionalNotes": meter_data.meterDetails.additionalNotes,
    }

    # Create meter
    new_meter = Meter(
        serial_number=serial_number,
        address=full_address,
        meter_type=meter_type,
        # Keep defaults for priority/status/estimated_time unless later extended
        owner=owner_name,
        last_reading=initial_reading,
        meter_metadata=metadata,
    )

    # Set coordinates if gpsCoordinates provided (expects "lat,lon")
    if meter_data.gpsCoordinates:
        try:
            lat_str, lon_str = [s.strip() for s in meter_data.gpsCoordinates.split(",", 1)]
            lat = float(lat_str)
            lon = float(lon_str)
            new_meter.coordinates = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        except Exception:
            # Ignore coordinate parsing errors but keep payload otherwise
            pass

    db.add(new_meter)
    await db.commit()
    await db.refresh(new_meter)

    return ResponseModel(
        data=MeterResponse(
            id=new_meter.id,
            serial_number=new_meter.serial_number,
            address=new_meter.address,
            location_id=new_meter.location_id,
            meter_type=new_meter.meter_type,
            priority=new_meter.priority,
            status=new_meter.status,
            last_reading=new_meter.last_reading,
            estimated_time=new_meter.estimated_time,
            location=Location(
                latitude=float(new_meter.coordinates.x) if new_meter.coordinates else None,
                longitude=float(new_meter.coordinates.y) if new_meter.coordinates else None,
            ) if new_meter.coordinates else None,
            owner=new_meter.owner,
            meter_metadata=new_meter.meter_metadata,
            created_at=new_meter.created_at,
            updated_at=new_meter.updated_at,
        ),
        message="Meter created successfully",
    )


@router.get("/{meter_id}", response_model=ResponseModel[MeterResponse])
async def get_meter(
    meter_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific meter by ID."""
    result = await db.execute(select(Meter).where(Meter.id == meter_id))
    meter = result.scalar_one_or_none()
    
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meter not found"
        )
    
    return ResponseModel(
        data=MeterResponse(
            id=meter.id,
            serial_number=meter.serial_number,
            address=meter.address,
            location_id=meter.location_id,
            meter_type=meter.meter_type,
            priority=meter.priority,
            status=meter.status,
            last_reading=meter.last_reading,
            estimated_time=meter.estimated_time,
            location=Location(
                latitude=float(meter.coordinates.x) if meter.coordinates else None,
                longitude=float(meter.coordinates.y) if meter.coordinates else None
            ) if meter.coordinates else None,
            owner=meter.owner,
            meter_metadata=meter.meter_metadata,
            created_at=meter.created_at,
            updated_at=meter.updated_at
        )
    )


@router.put("/{meter_id}", response_model=ResponseModel[MeterResponse])
async def update_meter(
    meter_id: str,
    meter_update: MeterUpdate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a meter."""
    result = await db.execute(select(Meter).where(Meter.id == meter_id))
    meter = result.scalar_one_or_none()
    
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meter not found"
        )
    
    # Update fields
    update_data = meter_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "location" and value:
            # Update location
            meter.coordinates = func.ST_SetSRID(
                func.ST_MakePoint(value.longitude, value.latitude), 4326
            )
        else:
            setattr(meter, field, value)
    
    await db.commit()
    await db.refresh(meter)
    
    return ResponseModel(
        data=MeterResponse(
            id=meter.id,
            serial_number=meter.serial_number,
            address=meter.address,
            location_id=meter.location_id,
            meter_type=meter.meter_type,
            priority=meter.priority,
            status=meter.status,
            last_reading=meter.last_reading,
            estimated_time=meter.estimated_time,
            location=Location(
                latitude=float(meter.coordinates.x) if meter.coordinates else None,
                longitude=float(meter.coordinates.y) if meter.coordinates else None
            ) if meter.coordinates else None,
            owner=meter.owner,
            meter_metadata=meter.meter_metadata,
            created_at=meter.created_at,
            updated_at=meter.updated_at
        ),
        message="Meter updated successfully"
    )


@router.delete("/{meter_id}", response_model=ResponseModel)
async def delete_meter(
    meter_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a meter."""
    result = await db.execute(select(Meter).where(Meter.id == meter_id))
    meter = result.scalar_one_or_none()
    
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meter not found"
        )
    
    # Check if meter has active assignments
    active_assignments = await db.execute(
        select(MeterAssignment).where(
            and_(
                MeterAssignment.meter_id == meter_id,
                MeterAssignment.status.in_(["pending", "in_progress"])
            )
        )
    )
    if active_assignments.scalars().all():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete meter with active assignments"
        )
    
    await db.delete(meter)
    await db.commit()
    
    return ResponseModel(message="Meter deleted successfully")


@router.get("/nearby", response_model=ResponseModel[list[MeterListResponse]])
async def get_nearby_meters(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius: float = Query(1000, ge=0, description="Radius in meters"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get meters within a specified radius of given coordinates."""
    # Create a point from the given coordinates
    point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
    
    # Query meters within radius
    query = select(Meter).where(
        and_(
            Meter.coordinates.isnot(None),
            func.ST_DWithin(Meter.coordinates, point, radius)
        )
    ).limit(limit)
    
    result = await db.execute(query)
    meters = result.scalars().all()
    
    return ResponseModel(
        data=[
            MeterListResponse(
                id=meter.id,
                serial_number=meter.serial_number,
                address=meter.address,
                meter_type=meter.meter_type,
                priority=meter.priority,
                status=meter.status,
                location=Location(
                    latitude=float(meter.coordinates.x) if meter.coordinates else None,
                    longitude=float(meter.coordinates.y) if meter.coordinates else None
                ) if meter.coordinates else None,
                created_at=meter.created_at
            ) for meter in meters
        ]
    )


@router.get("/unassigned", response_model=ResponseModel[list[MeterListResponse]])
async def get_unassigned_meters(
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get meters that are not currently assigned."""
    # Subquery to get meters with active assignments
    assigned_meters = select(MeterAssignment.meter_id).where(
        MeterAssignment.status.in_(["pending", "in_progress"])
    ).distinct()
    
    # Get unassigned meters
    query = select(Meter).where(
        and_(
            ~Meter.id.in_(assigned_meters),
            Meter.status == MeterStatus.ACTIVE
        )
    )
    
    result = await db.execute(query)
    meters = result.scalars().all()
    
    return ResponseModel(
        data=[
            MeterListResponse(
                id=meter.id,
                serial_number=meter.serial_number,
                address=meter.address,
                meter_type=meter.meter_type,
                priority=meter.priority,
                status=meter.status,
                location=Location(
                    latitude=float(meter.coordinates.x) if meter.coordinates else None,
                    longitude=float(meter.coordinates.y) if meter.coordinates else None
                ) if meter.coordinates else None,
                created_at=meter.created_at
            ) for meter in meters
        ]
    )
