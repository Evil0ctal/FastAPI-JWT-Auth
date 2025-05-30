from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.core.rate_limit import rate_limit
from app.db.database import get_db
from app.schemas.token import Token, RefreshTokenRequest, TokenRevoke
from app.schemas.user import UserLogin, UserCreate, User
from app.schemas.password_reset import PasswordResetRequest, PasswordReset
from app.services import user as user_service
from app.models.user import User as UserModel
from app.services.refresh_token import refresh_token_service
from app.services.email_verification import email_verification_service
from app.services.password_reset import password_reset_service
from app.services.two_factor_auth import two_factor_auth_service
from app.services.device_management import device_management_service
from app.api.deps import get_current_user

router = APIRouter()


@router.post("/register", response_model=User, dependencies=[Depends(rate_limit(max_requests=3, window_seconds=300))])
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    # Check email
    user = await user_service.get_user_by_email(db, email=str(user_in.email))
    if user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Check username
    user = await user_service.get_user_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    # Check phone if provided
    if user_in.phone:
        user = await user_service.get_user_by_phone(db, phone=user_in.phone)
        if user:
            raise HTTPException(
                status_code=400,
                detail="Phone number already registered"
            )
    
    user = await user_service.create_user(db=db, user=user_in)
    
    # Send verification email
    await email_verification_service.send_verification_email(db, user.id)
    
    return user


@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))])
async def login(
    user_credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Get device info
    client_host = request.client.host if request.client else "Unknown"
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    user = await user_service.authenticate_user(
        db, email=str(user_credentials.email), password=user_credentials.password
    )
    
    if not user:
        # Record failed login attempt
        user_by_email = await user_service.get_user_by_email(db, str(user_credentials.email))
        if user_by_email:
            await device_management_service.record_login_attempt(
                db=db,
                user_id=user_by_email.id,
                ip_address=client_host,
                user_agent=user_agent,
                login_method="password",
                status="failed",
                failure_reason="wrong_password"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Register device
    device = await device_management_service.register_device(
        db=db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=client_host
    )
    
    # Check if 2FA is enabled
    is_2fa_enabled = await two_factor_auth_service.is_2fa_enabled(db, user.id)
    if is_2fa_enabled:
        # Return a partial token that requires 2FA verification
        partial_token = create_access_token(
            data={"sub": str(user.id), "requires_2fa": True},
            expires_delta=timedelta(minutes=5)  # Short expiry for 2FA verification
        )
        
        # Record login attempt (pending 2FA)
        await device_management_service.record_login_attempt(
            db=db,
            user_id=user.id,
            ip_address=client_host,
            user_agent=user_agent,
            login_method="password",
            status="pending_2fa",
            device_id=device.device_id
        )
        
        return {
            "access_token": partial_token,
            "token_type": "bearer",
            "requires_2fa": True,
            "device_id": device.device_id
        }
    
    # Update last login
    await user_service.update_last_login(db, user.id)
    
    # Record successful login
    await device_management_service.record_login_attempt(
        db=db,
        user_id=user.id,
        ip_address=client_host,
        user_agent=user_agent,
        login_method="password",
        status="success",
        device_id=device.device_id
    )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.email)}, expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_jwt = create_refresh_token(
        data={"sub": str(user.email)}, expires_delta=refresh_token_expires
    )
    
    # Store refresh token in database
    await refresh_token_service.create_refresh_token(
        db=db,
        user_id=user.id,
        token=refresh_token_jwt,
        device_info=user_agent[:255],  # Limit to 255 chars
        ip_address=client_host
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_jwt,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_request: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    # Validate refresh token in database
    user = await refresh_token_service.validate_and_get_user(db, token_request.refresh_token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.email)}, expires_delta=access_token_expires
    )
    
    # Create new refresh token
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.email)}, expires_delta=refresh_token_expires
    )
    
    # Revoke old refresh token
    await refresh_token_service.revoke_token(db, token_request.refresh_token)
    
    # Store new refresh token
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    await refresh_token_service.create_refresh_token(
        db=db,
        user_id=user.id,
        token=new_refresh_token,
        device_info=user_agent[:255],
        ip_address=client_host
    )
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.post("/logout")
async def logout(
    token_revoke: TokenRevoke,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user)  # Ensures user is authenticated
):
    """Logout user by revoking refresh token"""
    # Revoke the specific refresh token
    revoked = await refresh_token_service.revoke_token(db, token_revoke.refresh_token)
    
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    
    return {"message": "Successfully logged out"}


@router.post("/logout/all")
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout user from all devices by revoking all refresh tokens"""
    count = await refresh_token_service.revoke_all_user_tokens(db, current_user.id)
    
    return {
        "message": f"Successfully logged out from {count} device(s)"
    }


@router.post("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify email address with token"""
    user = await email_verification_service.verify_email(db, token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """Resend verification email"""
    sent = await email_verification_service.resend_verification_email(db, email)
    
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to send verification email. User may not exist or is already verified."
        )
    
    return {"message": "Verification email sent"}


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset email"""
    # Always return success to prevent email enumeration
    await password_reset_service.create_reset_token(db, request.email)
    
    return {
        "message": "If an account exists with this email, a password reset link has been sent."
    }


@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    """Reset password with token"""
    success = await password_reset_service.reset_password(
        db,
        token=reset_data.token,
        new_password=reset_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {"message": "Password reset successfully"}


@router.get("/validate-reset-token")
async def validate_reset_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Validate if password reset token is valid"""
    is_valid = await password_reset_service.validate_reset_token(db, token)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {"valid": True}


@router.post("/verify-2fa", response_model=Token)
async def verify_2fa(
    code: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify 2FA code and complete login"""
    # Check if the token requires 2FA
    # This will be handled by the dependency that checks the token
    
    # Verify 2FA code
    is_valid = await two_factor_auth_service.verify_2fa(
        db, current_user.id, code
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )
    
    # Update last login
    await user_service.update_last_login(db, current_user.id)
    
    # Create full access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user.email)}, expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_jwt = create_refresh_token(
        data={"sub": str(current_user.email)}, expires_delta=refresh_token_expires
    )
    
    # Store refresh token in database
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    await refresh_token_service.create_refresh_token(
        db=db,
        user_id=current_user.id,
        token=refresh_token_jwt,
        device_info=user_agent[:255],
        ip_address=client_host
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_jwt,
        "token_type": "bearer"
    }
