import secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.password_reset import PasswordReset
from app.models.user import User
from app.services.email import email_service
from app.core.config import settings
from app.core.security import get_password_hash


class PasswordResetService:
    @staticmethod
    async def create_reset_token(
        db: AsyncSession,
        email: str
    ) -> Optional[str]:
        """Create a password reset token for user"""
        # Get user by email
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            return None
        
        # Generate unique token
        token = secrets.token_urlsafe(32)
        
        # Set expiry (1 hour)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Create reset token
        password_reset = PasswordReset(
            user_id=user.id,
            token=token,
            expires_at=expires_at
        )
        
        db.add(password_reset)
        await db.commit()
        
        # Send reset email if enabled
        if settings.EMAIL_ENABLED:
            await email_service.send_password_reset_email(
                to_email=user.email,
                username=user.username,
                reset_token=token
            )
        else:
            # In demo mode, log the token
            print(f"Password reset token for {user.email}: {token}")
        
        return token
    
    @staticmethod
    async def reset_password(
        db: AsyncSession,
        token: str,
        new_password: str
    ) -> bool:
        """Reset password with token"""
        # Find valid reset token
        query = select(PasswordReset).where(
            and_(
                PasswordReset.token == token,
                PasswordReset.expires_at > datetime.utcnow(),
                PasswordReset.used_at.is_(None)
            )
        )
        result = await db.execute(query)
        reset_token = result.scalar_one_or_none()
        
        if not reset_token:
            return False
        
        # Get user
        query = select(User).where(User.id == reset_token.user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            return False
        
        # Update password
        user.hashed_password = get_password_hash(new_password)
        
        # Mark token as used
        reset_token.used_at = datetime.utcnow()
        
        # Invalidate all other reset tokens for this user
        await db.execute(
            PasswordReset.__table__.update()
            .where(
                and_(
                    PasswordReset.user_id == user.id,
                    PasswordReset.id != reset_token.id,
                    PasswordReset.used_at.is_(None)
                )
            )
            .values(used_at=datetime.utcnow())
        )
        
        await db.commit()
        return True
    
    @staticmethod
    async def validate_reset_token(
        db: AsyncSession,
        token: str
    ) -> bool:
        """Validate if reset token is valid"""
        query = select(PasswordReset).where(
            and_(
                PasswordReset.token == token,
                PasswordReset.expires_at > datetime.utcnow(),
                PasswordReset.used_at.is_(None)
            )
        )
        result = await db.execute(query)
        reset_token = result.scalar_one_or_none()
        
        return reset_token is not None
    
    @staticmethod
    async def cleanup_expired_tokens(db: AsyncSession) -> int:
        """Clean up expired reset tokens"""
        cutoff = datetime.utcnow() - timedelta(days=7)
        
        query = PasswordReset.__table__.delete().where(
            PasswordReset.created_at < cutoff
        )
        
        result = await db.execute(query)
        await db.commit()
        
        return result.rowcount


password_reset_service = PasswordResetService()