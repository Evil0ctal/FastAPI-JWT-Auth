"""
Device Management API endpoints
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from app.api.deps import get_current_active_user
from app.db.database import get_db
from app.models.user import User as UserModel
from app.services.device_management import device_management_service


router = APIRouter()


class DeviceResponse(BaseModel):
    device_id: str
    device_name: str
    device_type: str
    browser: str | None
    os: str | None
    last_active: datetime
    is_trusted: bool
    created_at: datetime


class LoginHistoryResponse(BaseModel):
    id: int
    device_id: str | None
    ip_address: str
    location: str | None
    login_method: str
    status: str
    failure_reason: str | None
    created_at: datetime


@router.get("/devices", response_model=List[DeviceResponse])
async def get_user_devices(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all devices for current user"""
    devices = await device_management_service.get_user_devices(db, current_user.id)
    
    return [
        DeviceResponse(
            device_id=device.device_id,
            device_name=device.device_name,
            device_type=device.device_type,
            browser=device.browser,
            os=device.os,
            last_active=device.last_active,
            is_trusted=device.is_trusted,
            created_at=device.created_at
        )
        for device in devices
    ]


@router.post("/devices/{device_id}/trust")
async def trust_device(
    device_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a device as trusted"""
    success = await device_management_service.trust_device(
        db, current_user.id, device_id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return {"message": "Device marked as trusted"}


@router.delete("/devices/{device_id}")
async def remove_device(
    device_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a device"""
    success = await device_management_service.remove_device(
        db, current_user.id, device_id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return {"message": "Device removed successfully"}


@router.get("/login-history", response_model=List[LoginHistoryResponse])
async def get_login_history(
    limit: int = 50,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get login history for current user"""
    history = await device_management_service.get_login_history(
        db, current_user.id, limit=limit, offset=offset
    )
    
    return [
        LoginHistoryResponse(
            id=record.id,
            device_id=record.device_id,
            ip_address=record.ip_address,
            location=record.location,
            login_method=record.login_method,
            status=record.status,
            failure_reason=record.failure_reason,
            created_at=record.created_at
        )
        for record in history
    ]