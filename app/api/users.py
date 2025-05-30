from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_superuser
from app.db.database import get_db
from app.models.user import User as UserModel
from app.schemas.user import User, UserUpdate, UserProfile
from app.services import user as user_service
from app.services.file_upload import file_upload_service

router = APIRouter()


@router.get("/me", response_model=UserProfile)
async def read_users_me(
    current_user: UserModel = Depends(get_current_active_user)
):
    return current_user


@router.put("/me", response_model=User)
async def update_user_me(
    user_update: UserUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    updated_user = await user_service.update_user(db, current_user, user_update)
    return updated_user


@router.get("/", response_model=List[User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    users = await user_service.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=User)
async def read_user(
    user_id: int,
    current_user: UserModel = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db)
):
    user = await user_service.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload user avatar"""
    # Delete old avatar if exists
    if current_user.avatar_url:
        await file_upload_service.delete_avatar(current_user.avatar_url)
    
    # Save new avatar
    avatar_url = await file_upload_service.save_avatar(file, current_user.id)
    
    # Update user
    user_update = UserUpdate(avatar_url=avatar_url)
    updated_user = await user_service.update_user(db, current_user, user_update)
    
    return {
        "message": "Avatar uploaded successfully",
        "avatar_url": avatar_url
    }


@router.delete("/me/avatar")
async def delete_avatar(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user avatar"""
    if current_user.avatar_url:
        await file_upload_service.delete_avatar(current_user.avatar_url)
        
        # Update user
        user_update = UserUpdate(avatar_url=None)
        await user_service.update_user(db, current_user, user_update)
    
    return {"message": "Avatar deleted successfully"}
