from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.database import get_db
from app.auth.dependencies import get_current_user, require_manager_or_admin
from app.models.user import User
from app.models.agent import Agent
from app.models.meter import Meter, MeterStatus
from app.models.meter_assignment import MeterAssignment, AssignmentStatus
from app.models.meter_reading import MeterReading
from app.models.meter_approval_request import MeterApprovalRequest, ApprovalStatus
from app.schemas.common import ResponseModel

router = APIRouter()


@router.get("/dashboard", response_model=ResponseModel[Dict[str, Any]])
async def get_dashboard_stats(
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics."""
    # Get total counts
    total_users = await db.execute(select(func.count(User.id)))
    total_agents = await db.execute(select(func.count(Agent.id)))
    total_meters = await db.execute(select(func.count(Meter.id)))
    total_assignments = await db.execute(select(func.count(MeterAssignment.id)))
    total_readings = await db.execute(select(func.count(MeterReading.id)))
    
    # Get active counts
    active_agents = await db.execute(
        select(func.count(Agent.id)).where(Agent.status == "available")
    )
    active_meters = await db.execute(
        select(func.count(Meter.id)).where(Meter.status == MeterStatus.ACTIVE)
    )
    pending_assignments = await db.execute(
        select(func.count(MeterAssignment.id)).where(
            MeterAssignment.status.in_([AssignmentStatus.PENDING, AssignmentStatus.IN_PROGRESS])
        )
    )
    completed_assignments = await db.execute(
        select(func.count(MeterAssignment.id)).where(MeterAssignment.status == AssignmentStatus.COMPLETED)
    )
    
    # Get pending approvals
    pending_approvals = await db.execute(
        select(func.count(MeterApprovalRequest.id)).where(MeterApprovalRequest.status == ApprovalStatus.PENDING)
    )
    
    # Calculate completion rate
    completion_rate = 0
    if total_assignments.scalar() > 0:
        completion_rate = (completed_assignments.scalar() / total_assignments.scalar()) * 100
    
    return ResponseModel(
        data={
            "total_users": total_users.scalar(),
            "total_agents": total_agents.scalar(),
            "total_meters": total_meters.scalar(),
            "total_assignments": total_assignments.scalar(),
            "total_readings": total_readings.scalar(),
            "active_agents": active_agents.scalar(),
            "active_meters": active_meters.scalar(),
            "pending_assignments": pending_assignments.scalar(),
            "completed_assignments": completed_assignments.scalar(),
            "pending_approvals": pending_approvals.scalar(),
            "completion_rate": round(completion_rate, 2)
        }
    )


@router.get("/agent-performance", response_model=ResponseModel[Dict[str, Any]])
async def get_agent_performance_report(
    start_date: Optional[datetime] = Query(None, description="Start date for report"),
    end_date: Optional[datetime] = Query(None, description="End date for report"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get agent performance report."""
    # Build date filter
    date_filter = None
    if start_date and end_date:
        date_filter = and_(
            MeterAssignment.assigned_at >= start_date,
            MeterAssignment.assigned_at <= end_date
        )
    elif start_date:
        date_filter = MeterAssignment.assigned_at >= start_date
    elif end_date:
        date_filter = MeterAssignment.assigned_at <= end_date
    
    # Get agent performance data
    query = select(
        Agent.id,
        Agent.user_id,
        func.count(MeterAssignment.id).label("total_assignments"),
        func.count(MeterReading.id).label("total_readings"),
        func.avg(
            func.extract('epoch', MeterAssignment.completed_at - MeterAssignment.assigned_at) / 60
        ).label("avg_completion_time")
    ).outerjoin(MeterAssignment, Agent.id == MeterAssignment.agent_id)
    
    if date_filter:
        query = query.where(date_filter)
    
    query = query.group_by(Agent.id, Agent.user_id)
    
    result = await db.execute(query)
    agent_stats = result.all()
    
    # Format the data
    performance_data = []
    for stat in agent_stats:
        performance_data.append({
            "agent_id": str(stat.id),
            "user_id": str(stat.user_id),
            "total_assignments": stat.total_assignments,
            "total_readings": stat.total_readings,
            "avg_completion_time": round(stat.avg_completion_time, 2) if stat.avg_completion_time else None
        })
    
    return ResponseModel(data={"agent_performance": performance_data})


@router.get("/meter-status", response_model=ResponseModel[Dict[str, Any]])
async def get_meter_status_report(
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get meter status report."""
    # Get meter counts by status
    status_counts = await db.execute(
        select(
            Meter.status,
            func.count(Meter.id).label("count")
        ).group_by(Meter.status)
    )
    
    # Get meter counts by type
    type_counts = await db.execute(
        select(
            Meter.meter_type,
            func.count(Meter.id).label("count")
        ).group_by(Meter.meter_type)
    )
    
    # Get assigned vs unassigned meters
    assigned_meters = await db.execute(
        select(func.count(Meter.id)).where(
            Meter.id.in_(
                select(MeterAssignment.meter_id).where(
                    MeterAssignment.status.in_([AssignmentStatus.PENDING, AssignmentStatus.IN_PROGRESS])
                )
            )
        )
    )
    
    total_meters = await db.execute(select(func.count(Meter.id)))
    unassigned_meters = total_meters.scalar() - assigned_meters.scalar()
    
    return ResponseModel(
        data={
            "status_counts": {row.status: row.count for row in status_counts},
            "type_counts": {row.meter_type: row.count for row in type_counts},
            "assignment_summary": {
                "assigned": assigned_meters.scalar(),
                "unassigned": unassigned_meters,
                "total": total_meters.scalar()
            }
        }
    )


@router.get("/readings-summary", response_model=ResponseModel[Dict[str, Any]])
async def get_readings_summary_report(
    start_date: Optional[datetime] = Query(None, description="Start date for report"),
    end_date: Optional[datetime] = Query(None, description="End date for report"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get meter readings summary report."""
    # Build date filter
    date_filter = None
    if start_date and end_date:
        date_filter = and_(
            MeterReading.created_at >= start_date,
            MeterReading.created_at <= end_date
        )
    elif start_date:
        date_filter = MeterReading.created_at >= start_date
    elif end_date:
        date_filter = MeterReading.created_at <= end_date
    
    # Get total readings
    query = select(func.count(MeterReading.id))
    if date_filter:
        query = query.where(date_filter)
    
    total_readings = await db.execute(query)
    
    # Get verified readings
    verified_query = select(func.count(MeterReading.id)).where(MeterReading.verified == True)
    if date_filter:
        verified_query = verified_query.where(date_filter)
    
    verified_readings = await db.execute(verified_query)
    
    # Get readings by meter type
    type_query = select(
        Meter.meter_type,
        func.count(MeterReading.id).label("count")
    ).join(MeterReading, Meter.id == MeterReading.meter_id)
    
    if date_filter:
        type_query = type_query.where(date_filter)
    
    type_query = type_query.group_by(Meter.meter_type)
    type_counts = await db.execute(type_query)
    
    # Calculate verification rate
    verification_rate = 0
    if total_readings.scalar() > 0:
        verification_rate = (verified_readings.scalar() / total_readings.scalar()) * 100
    
    return ResponseModel(
        data={
            "total_readings": total_readings.scalar(),
            "verified_readings": verified_readings.scalar(),
            "verification_rate": round(verification_rate, 2),
            "readings_by_type": {row.meter_type: row.count for row in type_counts}
        }
    )


@router.post("/export", response_model=ResponseModel)
async def export_report(
    report_type: str = Query(..., description="Type of report to export"),
    format: str = Query("json", description="Export format (json, csv)"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Export a report in the specified format."""
    # This is a placeholder for report export functionality
    # In a real implementation, you would generate the report and return a file
    
    if report_type not in ["agent-performance", "meter-status", "readings-summary", "dashboard"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type: {report_type}"
        )
    
    if format not in ["json", "csv"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format: {format}"
        )
    
    # For now, just return a success message
    # In a real implementation, you would generate and return the actual report file
    
    return ResponseModel(
        message=f"Report '{report_type}' exported successfully in {format} format"
    )
