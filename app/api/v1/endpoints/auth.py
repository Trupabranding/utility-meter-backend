from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from app.database import get_db
from app.auth.jwt import verify_password, get_password_hash, create_access_token, create_refresh_token, verify_refresh_token
from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserLogin, UserCreate, Token, UserResponse
from app.schemas.common import ResponseModel

router = APIRouter()


@router.post("/login", response_model=ResponseModel[Token])
async def login(
    user_credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return access/refresh tokens."""
    # Find user by email
    result = await db.execute(select(User).where(User.email == user_credentials.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create tokens
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return ResponseModel(
        data=Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=15 * 60  # 15 minutes in seconds
        ),
        message="Login successful"
    )


@router.post("/register", response_model=ResponseModel[UserResponse])
async def register(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Register a new user (admin only)."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        name=user_data.name,
        role=user_data.role,
        phone=user_data.phone,
        department=user_data.department,
        region=user_data.region
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return ResponseModel(
        data=UserResponse(
            id=new_user.id,
            email=new_user.email,
            name=new_user.name,
            role=new_user.role,
            status=new_user.status,
            phone=new_user.phone,
            department=new_user.department,
            region=new_user.region,
            permissions=new_user.permissions,
            created_at=new_user.created_at,
            updated_at=new_user.updated_at,
            last_login=new_user.last_login
        ),
        message="User registered successfully"
    )


@router.post("/refresh", response_model=ResponseModel[Token])
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    token_data = verify_refresh_token(refresh_token)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user from database
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    token_data_dict = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value
    }
    
    new_access_token = create_access_token(token_data_dict)
    new_refresh_token = create_refresh_token(token_data_dict)
    
    return ResponseModel(
        data=Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=15 * 60  # 15 minutes in seconds
        ),
        message="Token refreshed successfully"
    )


@router.post("/logout", response_model=ResponseModel)
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user (client should discard tokens)."""
    # In a more sophisticated implementation, you might want to blacklist the token
    # For now, we'll just return a success message
    return ResponseModel(message="Logout successful")


@router.get("/me", response_model=ResponseModel[UserResponse])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return ResponseModel(
        data=UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            role=current_user.role,
            status=current_user.status,
            phone=current_user.phone,
            department=current_user.department,
            region=current_user.region,
            permissions=current_user.permissions,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            last_login=current_user.last_login
        )
    )
