"""
Two-Factor Authentication Service
"""
import pyotp
import qrcode
import io
import base64
import json
import secrets
from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.two_factor_auth import TwoFactorAuth
from app.models.user import User
from app.core.config import settings
from app.core.security import encrypt_data, decrypt_data
from app.core.logging import app_logger as logger


class TwoFactorAuthService:
    """Service for managing 2FA"""
    
    def __init__(self):
        self.issuer_name = settings.PROJECT_NAME
    
    async def setup_2fa(self, db: AsyncSession, user_id: int) -> Tuple[str, str, List[str]]:
        """
        Setup 2FA for a user
        Returns: (secret, qr_code_data_url, backup_codes)
        """
        # Check if 2FA already exists
        existing_2fa = await self.get_2fa_by_user_id(db, user_id)
        if existing_2fa and existing_2fa.is_enabled:
            raise ValueError("2FA is already enabled for this user")
        
        # Get user for email
        user = await db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        
        # Generate secret
        secret = pyotp.random_base32()
        
        # Generate backup codes
        backup_codes = [
            f"{secrets.token_hex(3)}-{secrets.token_hex(3)}"
            for _ in range(8)
        ]
        
        # Create or update 2FA record
        if existing_2fa:
            existing_2fa.secret = encrypt_data(secret)
            existing_2fa.backup_codes = encrypt_data(json.dumps(backup_codes))
            existing_2fa.is_enabled = False
            existing_2fa.updated_at = datetime.utcnow()
        else:
            two_fa = TwoFactorAuth(
                user_id=user_id,
                secret=encrypt_data(secret),
                backup_codes=encrypt_data(json.dumps(backup_codes)),
                is_enabled=False
            )
            db.add(two_fa)
        
        await db.commit()
        
        # Generate QR code
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name=self.issuer_name
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        
        # Convert to data URL
        qr_code_data = base64.b64encode(buf.getvalue()).decode()
        qr_code_data_url = f"data:image/png;base64,{qr_code_data}"
        
        logger.info(f"2FA setup initiated for user {user_id}")
        
        return secret, qr_code_data_url, backup_codes
    
    async def enable_2fa(self, db: AsyncSession, user_id: int, code: str) -> bool:
        """Enable 2FA after verifying the code"""
        two_fa = await self.get_2fa_by_user_id(db, user_id)
        if not two_fa:
            raise ValueError("2FA not set up for this user")
        
        if two_fa.is_enabled:
            raise ValueError("2FA is already enabled")
        
        # Verify code
        secret = decrypt_data(two_fa.secret)
        if not self.verify_totp(secret, code):
            return False
        
        # Enable 2FA
        two_fa.is_enabled = True
        two_fa.enabled_at = datetime.utcnow()
        two_fa.updated_at = datetime.utcnow()
        
        await db.commit()
        logger.info(f"2FA enabled for user {user_id}")
        
        return True
    
    async def disable_2fa(self, db: AsyncSession, user_id: int) -> bool:
        """Disable 2FA for a user"""
        two_fa = await self.get_2fa_by_user_id(db, user_id)
        if not two_fa or not two_fa.is_enabled:
            return False
        
        # Delete 2FA record
        await db.delete(two_fa)
        await db.commit()
        
        logger.info(f"2FA disabled for user {user_id}")
        return True
    
    async def verify_2fa(
        self, 
        db: AsyncSession, 
        user_id: int, 
        code: str
    ) -> bool:
        """Verify 2FA code"""
        two_fa = await self.get_2fa_by_user_id(db, user_id)
        if not two_fa or not two_fa.is_enabled:
            return False
        
        # Try TOTP code first
        secret = decrypt_data(two_fa.secret)
        if self.verify_totp(secret, code):
            # Update last used
            two_fa.last_used_at = datetime.utcnow()
            await db.commit()
            return True
        
        # Try backup codes
        if two_fa.backup_codes:
            backup_codes = json.loads(decrypt_data(two_fa.backup_codes))
            if code in backup_codes:
                # Remove used backup code
                backup_codes.remove(code)
                two_fa.backup_codes = encrypt_data(json.dumps(backup_codes))
                two_fa.last_used_at = datetime.utcnow()
                await db.commit()
                
                logger.info(f"Backup code used for user {user_id}")
                return True
        
        return False
    
    async def regenerate_backup_codes(
        self, 
        db: AsyncSession, 
        user_id: int
    ) -> List[str]:
        """Regenerate backup codes"""
        two_fa = await self.get_2fa_by_user_id(db, user_id)
        if not two_fa or not two_fa.is_enabled:
            raise ValueError("2FA not enabled for this user")
        
        # Generate new backup codes
        backup_codes = [
            f"{secrets.token_hex(3)}-{secrets.token_hex(3)}"
            for _ in range(8)
        ]
        
        two_fa.backup_codes = encrypt_data(json.dumps(backup_codes))
        two_fa.updated_at = datetime.utcnow()
        
        await db.commit()
        logger.info(f"Backup codes regenerated for user {user_id}")
        
        return backup_codes
    
    async def get_2fa_by_user_id(
        self, 
        db: AsyncSession, 
        user_id: int
    ) -> Optional[TwoFactorAuth]:
        """Get 2FA record by user ID"""
        query = select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def is_2fa_enabled(self, db: AsyncSession, user_id: int) -> bool:
        """Check if 2FA is enabled for a user"""
        two_fa = await self.get_2fa_by_user_id(db, user_id)
        return two_fa is not None and two_fa.is_enabled
    
    def verify_totp(self, secret: str, code: str) -> bool:
        """Verify TOTP code"""
        totp = pyotp.TOTP(secret)
        # Allow for time drift
        return totp.verify(code, valid_window=1)
    
    def generate_totp(self, secret: str) -> str:
        """Generate current TOTP code (for testing)"""
        totp = pyotp.TOTP(secret)
        return totp.now()


# Create global instance
two_factor_auth_service = TwoFactorAuthService()


__all__ = ["two_factor_auth_service", "TwoFactorAuthService"]