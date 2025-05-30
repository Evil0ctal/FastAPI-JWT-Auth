from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.core.security import generate_token
from app.core.config import settings


class RefreshTokenService:
    @staticmethod
    async def create_refresh_token(
        db: AsyncSession,
        user_id: int,
        token: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> RefreshToken:
        """Create a new refresh token for a user"""
        # Calculate expiry
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Create refresh token record
        refresh_token = RefreshToken(
            token=token,
            user_id=user_id,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at
        )
        
        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)
        
        return refresh_token
    
    @staticmethod
    async def get_refresh_token(db: AsyncSession, token: str) -> Optional[RefreshToken]:
        """Get a refresh token by token string"""
        query = select(RefreshToken).where(
            and_(
                RefreshToken.token == token,
                RefreshToken.is_active == True,
                RefreshToken.expires_at > datetime.utcnow()
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_last_used(db: AsyncSession, refresh_token: RefreshToken) -> None:
        """Update the last used timestamp of a refresh token"""
        refresh_token.last_used_at = datetime.utcnow()
        await db.commit()
    
    @staticmethod
    async def revoke_token(db: AsyncSession, token: str) -> bool:
        """Revoke a specific refresh token"""
        refresh_token = await RefreshTokenService.get_refresh_token(db, token)
        if refresh_token:
            refresh_token.is_active = False
            await db.commit()
            return True
        return False
    
    @staticmethod
    async def revoke_all_user_tokens(db: AsyncSession, user_id: int) -> int:
        """Revoke all refresh tokens for a user"""
        query = (
            RefreshToken.__table__.update()
            .where(RefreshToken.user_id == user_id)
            .values(is_active=False)
        )
        result = await db.execute(query)
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def revoke_user_token_by_id(db: AsyncSession, user_id: int, token_id: int) -> bool:
        """Revoke a specific refresh token by ID for a user"""
        query = select(RefreshToken).where(
            and_(
                RefreshToken.id == token_id,
                RefreshToken.user_id == user_id
            )
        )
        result = await db.execute(query)
        refresh_token = result.scalar_one_or_none()
        
        if refresh_token:
            refresh_token.is_active = False
            await db.commit()
            return True
        return False
    
    @staticmethod
    async def get_user_active_tokens(db: AsyncSession, user_id: int) -> List[RefreshToken]:
        """Get all active refresh tokens for a user"""
        query = select(RefreshToken).where(
            and_(
                RefreshToken.user_id == user_id,
                RefreshToken.is_active == True,
                RefreshToken.expires_at > datetime.utcnow()
            )
        ).order_by(RefreshToken.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def cleanup_expired_tokens(db: AsyncSession) -> int:
        """Delete expired refresh tokens from the database"""
        query = delete(RefreshToken).where(
            RefreshToken.expires_at <= datetime.utcnow()
        )
        result = await db.execute(query)
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def validate_and_get_user(
        db: AsyncSession, 
        token: str
    ) -> Optional[User]:
        """Validate refresh token and return associated user"""
        refresh_token = await RefreshTokenService.get_refresh_token(db, token)
        
        if not refresh_token:
            return None
        
        # Update last used timestamp
        await RefreshTokenService.update_last_used(db, refresh_token)
        
        # Get user
        query = select(User).where(User.id == refresh_token.user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if user and user.is_active:
            return user
        
        return None


refresh_token_service = RefreshTokenService()