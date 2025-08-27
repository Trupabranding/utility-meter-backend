from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_manager_or_admin
from app.models.region import Region, RegionStatus
from app.models.user import User
from app.schemas.region import RegionCreate, RegionUpdate, RegionResponse, RegionListResponse, RegionStats
from app.schemas.common import ResponseModel, PaginationParams, PaginationResponse, Location

router = APIRouter()


@router.get("/", response_model=ResponseModel[PaginationResponse[RegionListResponse]])
async def get_regions(
    pagination: PaginationParams = Depends(),
    status: Optional[RegionStatus] = Query(None, description="Filter by status"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of regions with optional filtering."""
    query = select(Region)
    
    # Apply filters
    if status:
        query = query.where(Region.status == status)
    
    # Get total count
    count_query = select(Region).where(query.whereclause) if query.whereclause else select(Region)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    query = query.offset((pagination.page - 1) * pagination.limit).limit(pagination.limit)
    
    result = await db.execute(query)
    regions = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return ResponseModel(
        data=PaginationResponse(
            items=[
                RegionListResponse(
                    id=region.id,
                    name=region.name,
                    description=region.description,
                    location=Location(
                        latitude=float(region.coordinates.x) if region.coordinates else None,
                        longitude=float(region.coordinates.y) if region.coordinates else None
                    ) if region.coordinates else None,
                    radius=region.radius,
                    agent_count=region.agent_count,
                    meter_count=region.meter_count,
                    status=region.status,
                    created_at=region.created_at
                ) for region in regions
            ],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@router.post("/", response_model=ResponseModel[RegionResponse])
async def create_region(
    region_data: RegionCreate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new region."""
    # Check if name already exists
    existing_region = await db.execute(
        select(Region).where(Region.name == region_data.name)
    )
    if existing_region.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Region with this name already exists"
        )
    
    # Create region
    new_region = Region(
        name=region_data.name,
        description=region_data.description,
        radius=region_data.radius
    )
    
    # Set location if provided
    if region_data.location:
        new_region.coordinates = func.ST_SetSRID(
            func.ST_MakePoint(region_data.location.longitude, region_data.location.latitude), 4326
        )
    
    db.add(new_region)
    await db.commit()
    await db.refresh(new_region)
    
    return ResponseModel(
        data=RegionResponse(
            id=new_region.id,
            name=new_region.name,
            description=new_region.description,
            location=region_data.location,
            radius=new_region.radius,
            agent_count=new_region.agent_count,
            meter_count=new_region.meter_count,
            status=new_region.status,
            created_at=new_region.created_at,
            updated_at=new_region.updated_at
        ),
        message="Region created successfully"
    )


@router.get("/{region_id}", response_model=ResponseModel[RegionResponse])
async def get_region(
    region_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific region by ID."""
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()
    
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found"
        )
    
    return ResponseModel(
        data=RegionResponse(
            id=region.id,
            name=region.name,
            description=region.description,
            location=Location(
                latitude=float(region.coordinates.x) if region.coordinates else None,
                longitude=float(region.coordinates.y) if region.coordinates else None
            ) if region.coordinates else None,
            radius=region.radius,
            agent_count=region.agent_count,
            meter_count=region.meter_count,
            status=region.status,
            created_at=region.created_at,
            updated_at=region.updated_at
        )
    )


@router.put("/{region_id}", response_model=ResponseModel[RegionResponse])
async def update_region(
    region_id: str,
    region_update: RegionUpdate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a region."""
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()
    
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found"
        )
    
    # Update fields
    update_data = region_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "location" and value:
            # Update location
            region.coordinates = func.ST_SetSRID(
                func.ST_MakePoint(value.longitude, value.latitude), 4326
            )
        else:
            setattr(region, field, value)
    
    await db.commit()
    await db.refresh(region)
    
    return ResponseModel(
        data=RegionResponse(
            id=region.id,
            name=region.name,
            description=region.description,
            location=Location(
                latitude=float(region.coordinates.x) if region.coordinates else None,
                longitude=float(region.coordinates.y) if region.coordinates else None
            ) if region.coordinates else None,
            radius=region.radius,
            agent_count=region.agent_count,
            meter_count=region.meter_count,
            status=region.status,
            created_at=region.created_at,
            updated_at=region.updated_at
        ),
        message="Region updated successfully"
    )


@router.delete("/{region_id}", response_model=ResponseModel)
async def delete_region(
    region_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a region."""
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()
    
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found"
        )
    
    await db.delete(region)
    await db.commit()
    
    return ResponseModel(message="Region deleted successfully")


@router.get("/{region_id}/stats", response_model=ResponseModel[RegionStats])
async def get_region_stats(
    region_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for a specific region."""
    # Verify region exists
    region_result = await db.execute(select(Region).where(Region.id == region_id))
    region = region_result.scalar_one_or_none()
    
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found"
        )
    
    # For now, return basic stats from the region model
    # In a real implementation, you would calculate these from related data
    return ResponseModel(
        data=RegionStats(
            total_agents=region.agent_count,
            total_meters=region.meter_count,
            active_assignments=0,  # Would need to calculate from assignments
            completed_assignments=0,  # Would need to calculate from assignments
            average_completion_time=None  # Would need to calculate from assignments
        )
    )
