from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin, require_manager_or_admin
from app.auth.jwt import get_password_hash, verify_password
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse, PasswordChange
from app.schemas.common import ResponseModel, PaginationParams, PaginationResponse

router = APIRouter()


@router.get("/", response_model=ResponseModel[PaginationResponse[UserListResponse]])
async def get_users(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    status_filter: Optional[UserStatus] = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of users with optional filtering."""
    query = select(User)
    
    # Apply filters
    if search:
        query = query.where(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    
    if role:
        query = query.where(User.role == role)
    
    if status_filter:
        query = query.where(User.status == status_filter)
    
    # Get total count
    count_query = select(User).where(query.whereclause) if query.whereclause else select(User)
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    query = query.offset((pagination.page - 1) * pagination.limit).limit(pagination.limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    has_next = pagination.page < pages
    has_prev = pagination.page > 1
    
    return ResponseModel(
        data=PaginationResponse(
            items=[
                UserListResponse(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    role=user.role,
                    status=user.status,
                    department=user.department,
                    region=user.region,
                    created_at=user.created_at
                ) for user in users
            ],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@router.get("/{user_id}", response_model=ResponseModel[UserResponse])
async def get_user(
    user_id: str,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return ResponseModel(
        data=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            status=user.status,
            phone=user.phone,
            department=user.department,
            region=user.region,
            permissions=user.permissions,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login
        )
    )


@router.put("/{user_id}", response_model=ResponseModel[UserResponse])
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a user (admin/manager only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    return ResponseModel(
        data=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            status=user.status,
            phone=user.phone,
            department=user.department,
            region=user.region,
            permissions=user.permissions,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login
        ),
        message="User updated successfully"
    )


@router.delete("/{user_id}", response_model=ResponseModel)
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a user (admin only)."""
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Soft delete by setting status to inactive
    user.status = UserStatus.INACTIVE
    await db.commit()
    
    return ResponseModel(message="User deleted successfully")


@router.post("/{user_id}/change-password", response_model=ResponseModel)
async def change_password(
    user_id: str,
    password_change: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password (own account or admin for others)."""
    # Check if user can change this password
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only change your own password"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password (only for own account)
    if current_user.id == user_id:
        if not verify_password(password_change.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
    
    # Update password
    user.password_hash = get_password_hash(password_change.new_password)
    await db.commit()
    
    return ResponseModel(message="Password changed successfully")
