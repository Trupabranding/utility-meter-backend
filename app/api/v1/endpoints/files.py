from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_manager_or_admin
from app.config import settings
from app.models.user import User
from app.schemas.common import ResponseModel

router = APIRouter()


@router.post("/upload/photo", response_model=ResponseModel)
async def upload_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a photo file."""
    # Validate file type
    if file.content_type not in settings.allowed_image_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed. Allowed types: {settings.allowed_image_types}"
        )
    
    # Validate file size
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {file.size} exceeds maximum allowed size of {settings.max_file_size}"
        )
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.upload_dir, unique_filename)
    
    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Return file URL
    file_url = f"/api/v1/files/{unique_filename}"
    
    return ResponseModel(
        data={"file_url": file_url, "filename": unique_filename},
        message="File uploaded successfully"
    )


@router.post("/upload/document", response_model=ResponseModel)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_manager_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Upload a document file (admin/manager only)."""
    # Validate file size
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {file.size} exceeds maximum allowed size of {settings.max_file_size}"
        )
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.upload_dir, unique_filename)
    
    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Return file URL
    file_url = f"/api/v1/files/{unique_filename}"
    
    return ResponseModel(
        data={"file_url": file_url, "filename": unique_filename},
        message="Document uploaded successfully"
    )


@router.get("/{filename}")
async def get_file(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """Serve a file by filename."""
    file_path = os.path.join(settings.upload_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileResponse(file_path)


@router.delete("/{filename}", response_model=ResponseModel)
async def delete_file(
    filename: str,
    current_user: User = Depends(require_manager_or_admin)
):
    """Delete a file (admin/manager only)."""
    file_path = os.path.join(settings.upload_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    try:
        os.remove(file_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )
    
    return ResponseModel(message="File deleted successfully")
