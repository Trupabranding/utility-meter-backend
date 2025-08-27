from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from app.models.user import UserRole, UserStatus


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = None
    department: Optional[str] = None
    region: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.AGENT


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = None
    department: Optional[str] = None
    region: Optional[str] = None
    status: Optional[UserStatus] = None
    permissions: Optional[Dict[str, Any]] = None


class UserResponse(UserBase):
    id: UUID
    role: UserRole
    status: UserStatus
    permissions: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: Optional[UUID] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserListResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    status: UserStatus
    department: Optional[str] = None
    region: Optional[str] = None
    created_at: datetime
