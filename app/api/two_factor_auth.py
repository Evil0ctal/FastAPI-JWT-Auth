"""
Two-Factor Authentication API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.db.database import get_db
from app.models.user import User as UserModel
from app.services.two_factor_auth import two_factor_auth_service


router = APIRouter()


class Enable2FARequest(BaseModel):
    code: str


class Verify2FARequest(BaseModel):
    code: str


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: list[str]


class TwoFactorStatusResponse(BaseModel):
    enabled: bool
    enabled_at: str | None = None


@router.get("/status", response_model=TwoFactorStatusResponse)
async def get_2fa_status(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get 2FA status for current user"""
    two_fa = await two_factor_auth_service.get_2fa_by_user_id(db, current_user.id)
    
    return TwoFactorStatusResponse(
        enabled=two_fa.is_enabled if two_fa else False,
        enabled_at=two_fa.enabled_at.isoformat() if two_fa and two_fa.enabled_at else None
    )


@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Setup 2FA for current user"""
    try:
        secret, qr_code, backup_codes = await two_factor_auth_service.setup_2fa(
            db, current_user.id
        )
        
        return TwoFactorSetupResponse(
            secret=secret,
            qr_code=qr_code,
            backup_codes=backup_codes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/enable")
async def enable_2fa(
    request: Enable2FARequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable 2FA after verifying setup code"""
    try:
        success = await two_factor_auth_service.enable_2fa(
            db, current_user.id, request.code
        )
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Invalid verification code"
            )
        
        return {"message": "2FA enabled successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disable")
async def disable_2fa(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Disable 2FA for current user"""
    success = await two_factor_auth_service.disable_2fa(db, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="2FA is not enabled for this user"
        )
    
    return {"message": "2FA disabled successfully"}


@router.post("/verify")
async def verify_2fa(
    request: Verify2FARequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify 2FA code"""
    is_valid = await two_factor_auth_service.verify_2fa(
        db, current_user.id, request.code
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid 2FA code"
        )
    
    return {"message": "2FA code verified successfully"}


@router.post("/backup-codes/regenerate")
async def regenerate_backup_codes(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate backup codes"""
    try:
        backup_codes = await two_factor_auth_service.regenerate_backup_codes(
            db, current_user.id
        )
        
        return {
            "message": "Backup codes regenerated successfully",
            "backup_codes": backup_codes
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))