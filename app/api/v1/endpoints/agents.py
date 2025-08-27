from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_manager_or_admin, get_current_agent
from app.models.agent import Agent, AgentStatus
from app.models.user import User
from app.models.meter_assignment import MeterAssignment, AssignmentStatus
from app.models.meter_reading import MeterReading
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentListResponse, AgentStats
from app.schemas.common import ResponseModel, PaginationParams, PaginationResponse, Location
from app.schemas.common import ResponseModel, PaginationParams, PaginationResponse

router = APIRouter()


@router.get("/", response_model=ResponseModel[PaginationResponse[AgentListResponse]])
async def get_agents(
    pagination: PaginationParams = Depends(),
    status: Optional[AgentStatus] = Query(None, description="Filter by status"),
    location_id: Optional[str] = Query(None, description="Filter by location ID"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of agents with optional filtering."""
    query = select(Agent).options(selectinload(Agent.user))
    
    # Apply filters
    if status:
        query = query.where(Agent.status == status)
    
    if location_id:
        query = query.where(Agent.location_id == location_id)
    
    # Get total count
    count_query = select(Agent).where(query.whereclause) if query.whereclause else select(Agent)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    query = query.offset((pagination.page - 1) * pagination.limit).limit(pagination.limit)
    
    result = await db.execute(query)
    agents = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return ResponseModel(
        data=PaginationResponse(
            items=[
                AgentListResponse(
                    id=agent.id,
                    user_id=agent.user_id,
                    current_load=agent.current_load,
                    max_load=agent.max_load,
                    status=agent.status,
                    location=Location(
                        latitude=float(agent.location.x) if agent.location else None,
                        longitude=float(agent.location.y) if agent.location else None
                    ) if agent.location else None,
                    created_at=agent.created_at,
                    user={
                        "id": agent.user.id,
                        "name": agent.user.name,
                        "email": agent.user.email
                    } if agent.user else None
                ) for agent in agents
            ],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@router.post("/", response_model=ResponseModel[AgentResponse])
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new agent."""
    # Check if user already has an agent profile
    existing_agent = await db.execute(
        select(Agent).where(Agent.user_id == agent_data.user_id)
    )
    if existing_agent.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has an agent profile"
        )
    
    # Create agent
    new_agent = Agent(
        user_id=agent_data.user_id,
        location_id=agent_data.location_id,
        max_load=agent_data.max_load,
        status=agent_data.status
    )
    
    # Set location if provided
    if agent_data.location:
        new_agent.location = func.ST_SetSRID(
            func.ST_MakePoint(agent_data.location.longitude, agent_data.location.latitude), 4326
        )
    
    db.add(new_agent)
    await db.commit()
    await db.refresh(new_agent)
    
    return ResponseModel(
        data=AgentResponse(
            id=new_agent.id,
            user_id=new_agent.user_id,
            location_id=new_agent.location_id,
            current_load=new_agent.current_load,
            max_load=new_agent.max_load,
            status=new_agent.status,
            location=agent_data.location,
            avatar_url=new_agent.avatar_url,
            created_at=new_agent.created_at,
            updated_at=new_agent.updated_at
        ),
        message="Agent created successfully"
    )


@router.get("/{agent_id}", response_model=ResponseModel[AgentResponse])
async def get_agent(
    agent_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific agent by ID."""
    result = await db.execute(
        select(Agent).options(selectinload(Agent.user)).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return ResponseModel(
        data=AgentResponse(
            id=agent.id,
            user_id=agent.user_id,
            location_id=agent.location_id,
            current_load=agent.current_load,
            max_load=agent.max_load,
            status=agent.status,
            location=Location(
                latitude=float(agent.location.x) if agent.location else None,
                longitude=float(agent.location.y) if agent.location else None
            ) if agent.location else None,
            avatar_url=agent.avatar_url,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            user={
                "id": agent.user.id,
                "name": agent.user.name,
                "email": agent.user.email
            } if agent.user else None
        )
    )


@router.put("/{agent_id}", response_model=ResponseModel[AgentResponse])
async def update_agent(
    agent_id: str,
    agent_update: AgentUpdate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update an agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Update fields
    update_data = agent_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "location" and value:
            # Update location
            agent.location = func.ST_SetSRID(
                func.ST_MakePoint(value.longitude, value.latitude), 4326
            )
        else:
            setattr(agent, field, value)
    
    await db.commit()
    await db.refresh(agent)
    
    return ResponseModel(
        data=AgentResponse(
            id=agent.id,
            user_id=agent.user_id,
            location_id=agent.location_id,
            current_load=agent.current_load,
            max_load=agent.max_load,
            status=agent.status,
            location=Location(
                latitude=float(agent.location.x) if agent.location else None,
                longitude=float(agent.location.y) if agent.location else None
            ) if agent.location else None,
            avatar_url=agent.avatar_url,
            created_at=agent.created_at,
            updated_at=agent.updated_at
        ),
        message="Agent updated successfully"
    )


@router.get("/{agent_id}/stats", response_model=ResponseModel[AgentStats])
async def get_agent_stats(
    agent_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get agent performance statistics."""
    # Get agent
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Get assignment stats
    assignments_result = await db.execute(
        select(MeterAssignment).where(MeterAssignment.agent_id == agent_id)
    )
    assignments = assignments_result.scalars().all()
    
    total_assignments = len(assignments)
    completed_assignments = len([a for a in assignments if a.status == AssignmentStatus.COMPLETED])
    pending_assignments = len([a for a in assignments if a.status in [AssignmentStatus.PENDING, AssignmentStatus.IN_PROGRESS]])
    
    # Get reading stats
    readings_result = await db.execute(
        select(MeterReading).where(MeterReading.agent_id == agent_id)
    )
    total_readings = len(readings_result.scalars().all())
    
    # Calculate success rate
    success_rate = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
    
    # Calculate average completion time (simplified)
    completed_with_time = [a for a in assignments if a.status == AssignmentStatus.COMPLETED and a.completed_at and a.assigned_at]
    if completed_with_time:
        total_time = sum((a.completed_at - a.assigned_at).total_seconds() / 60 for a in completed_with_time)
        average_completion_time = total_time / len(completed_with_time)
    else:
        average_completion_time = None
    
    return ResponseModel(
        data=AgentStats(
            total_assignments=total_assignments,
            completed_assignments=completed_assignments,
            pending_assignments=pending_assignments,
            total_readings=total_readings,
            average_completion_time=average_completion_time,
            success_rate=success_rate
        )
    )


@router.get("/available", response_model=ResponseModel[list[AgentListResponse]])
async def get_available_agents(
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get list of available agents for assignment."""
    result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.user))
        .where(
            and_(
                Agent.status == AgentStatus.AVAILABLE,
                Agent.current_load < Agent.max_load
            )
        )
    )
    agents = result.scalars().all()
    
    return ResponseModel(
        data=[
            AgentListResponse(
                id=agent.id,
                user_id=agent.user_id,
                current_load=agent.current_load,
                max_load=agent.max_load,
                status=agent.status,
                location=Location(
                    latitude=float(agent.location.x) if agent.location else None,
                    longitude=float(agent.location.y) if agent.location else None
                ) if agent.location else None,
                created_at=agent.created_at,
                user={
                    "id": agent.user.id,
                    "name": agent.user.name,
                    "email": agent.user.email
                } if agent.user else None
            ) for agent in agents
        ]
    )


@router.put("/me/location", response_model=ResponseModel)
async def update_my_location(
    location: Location,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """Update current agent's location."""
    current_agent.location = func.ST_SetSRID(
        func.ST_MakePoint(location.longitude, location.latitude), 4326
    )
    await db.commit()
    
    return ResponseModel(message="Location updated successfully")


@router.put("/me/status", response_model=ResponseModel)
async def update_my_status(
    status: AgentStatus,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """Update current agent's status."""
    current_agent.status = status
    await db.commit()
    
    return ResponseModel(message="Status updated successfully")
