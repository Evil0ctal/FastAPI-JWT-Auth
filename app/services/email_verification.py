import secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.email_verification import EmailVerification
from app.models.user import User
from app.services.email import email_service
from app.core.config import settings


class EmailVerificationService:
    @staticmethod
    async def create_verification_token(
        db: AsyncSession,
        user_id: int
    ) -> EmailVerification:
        """Create a new email verification token"""
        # Generate unique token
        token = secrets.token_urlsafe(32)
        
        # Set expiry (24 hours)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Check if verification already exists
        query = select(EmailVerification).where(EmailVerification.user_id == user_id)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing token
            existing.token = token
            existing.expires_at = expires_at
            existing.verified_at = None
            await db.commit()
            return existing
        else:
            # Create new verification
            verification = EmailVerification(
                user_id=user_id,
                token=token,
                expires_at=expires_at
            )
            db.add(verification)
            await db.commit()
            await db.refresh(verification)
            return verification
    
    @staticmethod
    async def verify_email(
        db: AsyncSession,
        token: str
    ) -> Optional[User]:
        """Verify email with token"""
        query = select(EmailVerification).where(
            EmailVerification.token == token,
            EmailVerification.expires_at > datetime.utcnow(),
            EmailVerification.verified_at.is_(None)
        )
        result = await db.execute(query)
        verification = result.scalar_one_or_none()
        
        if not verification:
            return None
        
        # Mark as verified
        verification.verified_at = datetime.utcnow()
        
        # Update user
        query = select(User).where(User.id == verification.user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if user:
            user.is_verified = True
            await db.commit()
            return user
        
        return None
    
    @staticmethod
    async def send_verification_email(
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """Send verification email to user"""
        # Get user
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or user.is_verified:
            return False
        
        # Create or update verification token
        verification = await EmailVerificationService.create_verification_token(db, user_id)
        
        # Send email if enabled
        if settings.EMAIL_ENABLED:
            return await email_service.send_verification_email(
                to_email=user.email,
                username=user.username,
                verification_token=verification.token
            )
        
        # In demo mode, just log the token
        print(f"Verification token for {user.email}: {verification.token}")
        return True
    
    @staticmethod
    async def resend_verification_email(
        db: AsyncSession,
        email: str
    ) -> bool:
        """Resend verification email"""
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or user.is_verified:
            return False
        
        return await EmailVerificationService.send_verification_email(db, user.id)


email_verification_service = EmailVerificationService()