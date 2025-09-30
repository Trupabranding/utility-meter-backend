from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, get_current_agent, require_manager_or_admin
from app.models.meter_assignment import MeterAssignment, AssignmentStatus
from app.models.meter import Meter
from app.models.agent import Agent
from app.models.user import User
from app.schemas.meter_assignment import MeterAssignmentCreate, MeterAssignmentUpdate, MeterAssignmentResponse, MeterAssignmentListResponse, BulkAssignmentRequest
from app.schemas.common import ResponseModel, PaginationParams, PaginationResponse

router = APIRouter()


@router.get("/", response_model=ResponseModel[PaginationResponse[MeterAssignmentListResponse]])
async def get_assignments(
    pagination: PaginationParams = Depends(),
    status: Optional[AssignmentStatus] = Query(None, description="Filter by status"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    meter_id: Optional[str] = Query(None, description="Filter by meter ID"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of assignments with optional filtering."""
    query = select(MeterAssignment).options(
        selectinload(MeterAssignment.meter),
        selectinload(MeterAssignment.agent).selectinload(Agent.user)
    )
    
    # Apply filters
    if status:
        query = query.where(MeterAssignment.status == status)
    
    if agent_id:
        query = query.where(MeterAssignment.agent_id == agent_id)
    
    if meter_id:
        query = query.where(MeterAssignment.meter_id == meter_id)
    
    # Get total count
    count_query = select(MeterAssignment).where(query.whereclause) if query.whereclause else select(MeterAssignment)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination and ordering
    query = query.order_by(MeterAssignment.assigned_at.desc()).offset(
        (pagination.page - 1) * pagination.limit
    ).limit(pagination.limit)
    
    result = await db.execute(query)
    assignments = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return ResponseModel(
        data=PaginationResponse(
            items=[
                MeterAssignmentListResponse(
                    id=assignment.id,
                    meter_id=assignment.meter_id,
                    agent_id=assignment.agent_id,
                    status=assignment.status,
                    estimated_time=assignment.estimated_time,
                    assigned_at=assignment.assigned_at,
                    completed_at=assignment.completed_at,
                    meter={
                        "id": assignment.meter.id,
                        "serial_number": assignment.meter.serial_number,
                        "address": assignment.meter.address
                    } if assignment.meter else None,
                    agent={
                        "id": assignment.agent.id,
                        "user": {
                            "id": assignment.agent.user.id,
                            "name": assignment.agent.user.name
                        } if assignment.agent.user else None
                    } if assignment.agent else None
                ) for assignment in assignments
            ],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@router.get("/me", response_model=ResponseModel[PaginationResponse[MeterAssignmentListResponse]])
async def get_my_assignments(
    pagination: PaginationParams = Depends(),
    status: Optional[AssignmentStatus] = Query(None, description="Filter by status"),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of the current agent's assignments with optional status filtering."""
    query = select(MeterAssignment).options(
        selectinload(MeterAssignment.meter),
        selectinload(MeterAssignment.agent).selectinload(Agent.user)
    ).where(MeterAssignment.agent_id == current_agent.id)

    if status:
        query = query.where(MeterAssignment.status == status)

    # Total count
    count_query = select(MeterAssignment).where(query.whereclause) if query.whereclause else select(MeterAssignment)
    total_result = await db.execute(count_query)
    # Only count those matching the agent filter; the whereclause already includes it
    total = len(total_result.scalars().all())

    # Pagination and ordering
    query = query.order_by(MeterAssignment.assigned_at.desc()).offset(
        (pagination.page - 1) * pagination.limit
    ).limit(pagination.limit)

    result = await db.execute(query)
    assignments = result.scalars().all()

    # Pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    has_next = pagination.page < pages
    has_prev = pagination.page > 1

    return ResponseModel(
        data=PaginationResponse(
            items=[
                MeterAssignmentListResponse(
                    id=assignment.id,
                    meter_id=assignment.meter_id,
                    agent_id=assignment.agent_id,
                    status=assignment.status,
                    estimated_time=assignment.estimated_time,
                    assigned_at=assignment.assigned_at,
                    completed_at=assignment.completed_at,
                    meter={
                        "id": assignment.meter.id,
                        "serial_number": assignment.meter.serial_number,
                        "address": assignment.meter.address
                    } if assignment.meter else None,
                    agent={
                        "id": assignment.agent.id,
                        "user": {
                            "id": assignment.agent.user.id,
                            "name": assignment.agent.user.name
                        } if assignment.agent.user else None
                    } if assignment.agent else None
                ) for assignment in assignments
            ],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@router.post("/", response_model=ResponseModel[MeterAssignmentResponse])
async def create_assignment(
    assignment_data: MeterAssignmentCreate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new meter assignment."""
    # Verify meter exists
    meter_result = await db.execute(select(Meter).where(Meter.id == assignment_data.meter_id))
    meter = meter_result.scalar_one_or_none()
    
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meter not found"
        )
    
    # Verify agent exists
    agent_result = await db.execute(select(Agent).where(Agent.id == assignment_data.agent_id))
    agent = agent_result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Check if meter is already assigned
    existing_assignment = await db.execute(
        select(MeterAssignment).where(
            and_(
                MeterAssignment.meter_id == assignment_data.meter_id,
                MeterAssignment.status.in_([AssignmentStatus.PENDING, AssignmentStatus.IN_PROGRESS])
            )
        )
    )
    if existing_assignment.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meter is already assigned"
        )
    
    # Create assignment
    new_assignment = MeterAssignment(
        meter_id=assignment_data.meter_id,
        agent_id=assignment_data.agent_id,
        status=AssignmentStatus.PENDING,
        estimated_time=assignment_data.estimated_time
    )
    
    db.add(new_assignment)
    
    # Update agent's current load
    agent.current_load += 1
    
    await db.commit()
    await db.refresh(new_assignment)
    
    return ResponseModel(
        data=MeterAssignmentResponse(
            id=new_assignment.id,
            meter_id=new_assignment.meter_id,
            agent_id=new_assignment.agent_id,
            status=new_assignment.status,
            estimated_time=new_assignment.estimated_time,
            assigned_at=new_assignment.assigned_at,
            completed_at=new_assignment.completed_at,
            completion_notes=new_assignment.completion_notes
        ),
        message="Assignment created successfully"
    )


@router.post("/bulk", response_model=ResponseModel)
async def bulk_assign(
    bulk_data: BulkAssignmentRequest,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Bulk assign meters to agents."""
    # Verify all meters exist
    for meter_id in bulk_data.meter_ids:
        meter_result = await db.execute(select(Meter).where(Meter.id == meter_id))
        if not meter_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meter {meter_id} not found"
            )
    
    # If specific agent is provided, verify they exist
    if bulk_data.agent_id:
        agent_result = await db.execute(select(Agent).where(Agent.id == bulk_data.agent_id))
        if not agent_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
    
    # Get available agents if no specific agent provided
    if not bulk_data.agent_id:
        available_agents = await db.execute(
            select(Agent).where(
                and_(
                    Agent.status == "available",
                    Agent.current_load < Agent.max_load
                )
            )
        )
        agents = available_agents.scalars().all()
        if not agents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No available agents found"
            )
    
    assignments_created = 0
    
    for meter_id in bulk_data.meter_ids:
        # Check if meter is already assigned
        existing_assignment = await db.execute(
            select(MeterAssignment).where(
                and_(
                    MeterAssignment.meter_id == meter_id,
                    MeterAssignment.status.in_([AssignmentStatus.PENDING, AssignmentStatus.IN_PROGRESS])
                )
            )
        )
        if existing_assignment.scalar_one_or_none():
            continue  # Skip already assigned meters
        
        # Select agent (round-robin if no specific agent)
        if bulk_data.agent_id:
            agent_id = bulk_data.agent_id
        else:
            # Simple round-robin assignment
            agent_id = agents[assignments_created % len(agents)].id
        
        # Create assignment
        new_assignment = MeterAssignment(
            meter_id=meter_id,
            agent_id=agent_id,
            status=AssignmentStatus.PENDING,
            estimated_time=bulk_data.estimated_time
        )
        
        db.add(new_assignment)
        assignments_created += 1
    
    await db.commit()
    
    return ResponseModel(
        message=f"Successfully created {assignments_created} assignments"
    )


@router.put("/{assignment_id}", response_model=ResponseModel[MeterAssignmentResponse])
async def update_assignment(
    assignment_id: str,
    assignment_update: MeterAssignmentUpdate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update an assignment."""
    result = await db.execute(select(MeterAssignment).where(MeterAssignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    # Update fields
    update_data = assignment_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assignment, field, value)
    
    # If status is being updated to completed, set completion time
    if assignment_update.status == AssignmentStatus.COMPLETED and not assignment.completed_at:
        assignment.completed_at = func.now()
        
        # Update agent's current load
        agent_result = await db.execute(select(Agent).where(Agent.id == assignment.agent_id))
        agent = agent_result.scalar_one_or_none()
        if agent and agent.current_load > 0:
            agent.current_load -= 1
    
    await db.commit()
    await db.refresh(assignment)
    
    return ResponseModel(
        data=MeterAssignmentResponse(
            id=assignment.id,
            meter_id=assignment.meter_id,
            agent_id=assignment.agent_id,
            status=assignment.status,
            estimated_time=assignment.estimated_time,
            assigned_at=assignment.assigned_at,
            completed_at=assignment.completed_at,
            completion_notes=assignment.completion_notes
        ),
        message="Assignment updated successfully"
    )


@router.get("/agent/{agent_id}", response_model=ResponseModel[list[MeterAssignmentListResponse]])
async def get_agent_assignments(
    agent_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all assignments for a specific agent."""
    # Verify agent exists
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if not agent_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    result = await db.execute(
        select(MeterAssignment)
        .options(selectinload(MeterAssignment.meter), selectinload(MeterAssignment.agent))
        .where(MeterAssignment.agent_id == agent_id)
        .order_by(MeterAssignment.assigned_at.desc())
    )
    assignments = result.scalars().all()
    
    return ResponseModel(
        data=[
            MeterAssignmentListResponse(
                id=assignment.id,
                meter_id=assignment.meter_id,
                agent_id=assignment.agent_id,
                status=assignment.status,
                estimated_time=assignment.estimated_time,
                assigned_at=assignment.assigned_at,
                completed_at=assignment.completed_at,
                meter={
                    "id": assignment.meter.id,
                    "serial_number": assignment.meter.serial_number,
                    "address": assignment.meter.address
                } if assignment.meter else None,
                agent={
                    "id": assignment.agent.id,
                    "user": {
                        "id": assignment.agent.user.id,
                        "name": assignment.agent.user.name
                    } if assignment.agent.user else None
                } if assignment.agent else None
            ) for assignment in assignments
        ]
    )


@router.put("/me/{assignment_id}/status", response_model=ResponseModel)
async def update_my_assignment_status(
    assignment_id: str,
    status: AssignmentStatus,
    completion_notes: Optional[str] = None,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """Update status of current agent's assignment."""
    result = await db.execute(
        select(MeterAssignment).where(
            and_(
                MeterAssignment.id == assignment_id,
                MeterAssignment.agent_id == current_agent.id
            )
        )
    )
    assignment = result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    assignment.status = status
    
    if status == AssignmentStatus.COMPLETED:
        assignment.completed_at = func.now()
        assignment.completion_notes = completion_notes
        
        # Update agent's current load
        if current_agent.current_load > 0:
            current_agent.current_load -= 1
    
    await db.commit()
    
    return ResponseModel(message="Assignment status updated successfully")
