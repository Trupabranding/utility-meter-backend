from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, get_current_agent, require_manager_or_admin
from app.models.meter_approval_request import MeterApprovalRequest, ApprovalStatus
from app.models.meter import Meter
from app.models.agent import Agent
from app.models.user import User
from app.schemas.meter_approval_request import MeterApprovalRequestCreate, MeterApprovalRequestUpdate, MeterApprovalRequestResponse, MeterApprovalRequestListResponse
from app.schemas.common import ResponseModel, PaginationParams, PaginationResponse

router = APIRouter()


@router.get("/", response_model=ResponseModel[PaginationResponse[MeterApprovalRequestListResponse]])
async def get_approval_requests(
    pagination: PaginationParams = Depends(),
    status: Optional[ApprovalStatus] = Query(None, description="Filter by status"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    meter_id: Optional[str] = Query(None, description="Filter by meter ID"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of approval requests with optional filtering."""
    query = select(MeterApprovalRequest).options(
        selectinload(MeterApprovalRequest.meter),
        selectinload(MeterApprovalRequest.agent).selectinload(Agent.user),
        selectinload(MeterApprovalRequest.reviewer)
    )
    
    # Apply filters
    if status:
        query = query.where(MeterApprovalRequest.status == status)
    
    if agent_id:
        query = query.where(MeterApprovalRequest.agent_id == agent_id)
    
    if meter_id:
        query = query.where(MeterApprovalRequest.meter_id == meter_id)
    
    # Get total count
    count_query = select(MeterApprovalRequest).where(query.whereclause) if query.whereclause else select(MeterApprovalRequest)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination and ordering
    query = query.order_by(MeterApprovalRequest.submitted_at.desc()).offset(
        (pagination.page - 1) * pagination.limit
    ).limit(pagination.limit)
    
    result = await db.execute(query)
    requests = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return ResponseModel(
        data=PaginationResponse(
            items=[
                MeterApprovalRequestListResponse(
                    id=req.id,
                    meter_id=req.meter_id,
                    agent_id=req.agent_id,
                    status=req.status,
                    submitted_at=req.submitted_at,
                    reviewed_at=req.reviewed_at,
                    meter={
                        "id": req.meter.id,
                        "serial_number": req.meter.serial_number,
                        "address": req.meter.address
                    } if req.meter else None,
                    agent={
                        "id": req.agent.id,
                        "user": {
                            "id": req.agent.user.id,
                            "name": req.agent.user.name
                        } if req.agent.user else None
                    } if req.agent else None
                ) for req in requests
            ],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@router.post("/", response_model=ResponseModel[MeterApprovalRequestResponse])
async def create_approval_request(
    request_data: MeterApprovalRequestCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """Submit a new approval request."""
    # Verify meter exists
    meter_result = await db.execute(select(Meter).where(Meter.id == request_data.meter_id))
    meter = meter_result.scalar_one_or_none()
    
    if not meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meter not found"
        )
    
    # Create approval request
    new_request = MeterApprovalRequest(
        meter_id=request_data.meter_id,
        agent_id=current_agent.id,
        meter_data=request_data.meter_data,
        submission_notes=request_data.submission_notes,
        status=ApprovalStatus.PENDING
    )
    
    db.add(new_request)
    await db.commit()
    await db.refresh(new_request)
    
    return ResponseModel(
        data=MeterApprovalRequestResponse(
            id=new_request.id,
            meter_id=new_request.meter_id,
            agent_id=new_request.agent_id,
            reviewer_id=new_request.reviewer_id,
            meter_data=new_request.meter_data,
            status=new_request.status,
            submission_notes=new_request.submission_notes,
            review_notes=new_request.review_notes,
            submitted_at=new_request.submitted_at,
            reviewed_at=new_request.reviewed_at
        ),
        message="Approval request submitted successfully"
    )


@router.get("/{request_id}", response_model=ResponseModel[MeterApprovalRequestResponse])
async def get_approval_request(
    request_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific approval request by ID."""
    result = await db.execute(
        select(MeterApprovalRequest).options(
            selectinload(MeterApprovalRequest.meter),
            selectinload(MeterApprovalRequest.agent),
            selectinload(MeterApprovalRequest.reviewer)
        ).where(MeterApprovalRequest.id == request_id)
    )
    approval_request = result.scalar_one_or_none()
    
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found"
        )
    
    return ResponseModel(
        data=MeterApprovalRequestResponse(
            id=approval_request.id,
            meter_id=approval_request.meter_id,
            agent_id=approval_request.agent_id,
            reviewer_id=approval_request.reviewer_id,
            meter_data=approval_request.meter_data,
            status=approval_request.status,
            submission_notes=approval_request.submission_notes,
            review_notes=approval_request.review_notes,
            submitted_at=approval_request.submitted_at,
            reviewed_at=approval_request.reviewed_at
        )
    )


@router.put("/{request_id}/approve", response_model=ResponseModel)
async def approve_request(
    request_id: str,
    review_notes: Optional[str] = None,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve an approval request."""
    result = await db.execute(select(MeterApprovalRequest).where(MeterApprovalRequest.id == request_id))
    approval_request = result.scalar_one_or_none()
    
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found"
        )
    
    if approval_request.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request is not pending approval"
        )
    
    # Update request
    approval_request.status = ApprovalStatus.APPROVED
    approval_request.reviewer_id = current_user.id
    approval_request.review_notes = review_notes
    approval_request.reviewed_at = func.now()
    
    await db.commit()
    
    return ResponseModel(message="Request approved successfully")


@router.put("/{request_id}/reject", response_model=ResponseModel)
async def reject_request(
    request_id: str,
    review_notes: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject an approval request."""
    result = await db.execute(select(MeterApprovalRequest).where(MeterApprovalRequest.id == request_id))
    approval_request = result.scalar_one_or_none()
    
    if not approval_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found"
        )
    
    if approval_request.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request is not pending approval"
        )
    
    # Update request
    approval_request.status = ApprovalStatus.REJECTED
    approval_request.reviewer_id = current_user.id
    approval_request.review_notes = review_notes
    approval_request.reviewed_at = func.now()
    
    await db.commit()
    
    return ResponseModel(message="Request rejected successfully")


@router.get("/pending", response_model=ResponseModel[list[MeterApprovalRequestListResponse]])
async def get_pending_requests(
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all pending approval requests."""
    result = await db.execute(
        select(MeterApprovalRequest)
        .options(selectinload(MeterApprovalRequest.meter), selectinload(MeterApprovalRequest.agent))
        .where(MeterApprovalRequest.status == ApprovalStatus.PENDING)
        .order_by(MeterApprovalRequest.submitted_at.asc())
    )
    requests = result.scalars().all()
    
    return ResponseModel(
        data=[
            MeterApprovalRequestListResponse(
                id=req.id,
                meter_id=req.meter_id,
                agent_id=req.agent_id,
                status=req.status,
                submitted_at=req.submitted_at,
                reviewed_at=req.reviewed_at,
                meter={
                    "id": req.meter.id,
                    "serial_number": req.meter.serial_number,
                    "address": req.meter.address
                } if req.meter else None,
                agent={
                    "id": req.agent.id,
                    "user": {
                        "id": req.agent.user.id,
                        "name": req.agent.user.name
                    } if req.agent.user else None
                } if req.agent else None
            ) for req in requests
        ]
    )
