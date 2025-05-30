"""
Device Management Service
"""
import hashlib
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from user_agents import parse

from app.models.user_device import UserDevice
from app.models.login_history import LoginHistory
from app.core.config import settings
from app.core.logging import app_logger as logger


class DeviceManagementService:
    """Service for managing user devices and login history"""
    
    def generate_device_id(self, user_agent: str, ip_address: str) -> str:
        """Generate a unique device ID based on user agent and IP"""
        # Parse user agent
        ua = parse(user_agent)
        
        # Create device fingerprint
        fingerprint = f"{ua.browser.family}:{ua.browser.version_string}:{ua.os.family}:{ua.os.version_string}"
        
        # Hash the fingerprint for consistency
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
    
    def parse_user_agent(self, user_agent: str) -> Dict[str, Any]:
        """Parse user agent string to extract device info"""
        ua = parse(user_agent)
        
        # Determine device type
        if ua.is_mobile:
            device_type = "mobile"
        elif ua.is_tablet:
            device_type = "tablet"
        else:
            device_type = "desktop"
        
        return {
            "device_type": device_type,
            "browser": ua.browser.family,
            "browser_version": ua.browser.version_string,
            "os": ua.os.family,
            "os_version": ua.os.version_string,
            "device_name": f"{ua.browser.family} on {ua.os.family}"
        }
    
    async def register_device(
        self,
        db: AsyncSession,
        user_id: int,
        user_agent: str,
        ip_address: str,
        location: Optional[str] = None
    ) -> UserDevice:
        """Register or update a user device"""
        device_id = self.generate_device_id(user_agent, ip_address)
        device_info = self.parse_user_agent(user_agent)
        
        # Check if device exists
        device = await self.get_device(db, user_id, device_id)
        
        if device:
            # Update last active
            device.last_active = datetime.utcnow()
            device.ip_address = ip_address
            if location:
                device.location = location
        else:
            # Create new device
            device = UserDevice(
                user_id=user_id,
                device_id=device_id,
                device_name=device_info["device_name"],
                device_type=device_info["device_type"],
                browser=device_info["browser"],
                browser_version=device_info["browser_version"],
                os=device_info["os"],
                os_version=device_info["os_version"],
                ip_address=ip_address,
                location=location
            )
            db.add(device)
        
        await db.commit()
        await db.refresh(device)
        
        logger.info(f"Device registered/updated for user {user_id}: {device_id}")
        return device
    
    async def get_device(
        self,
        db: AsyncSession,
        user_id: int,
        device_id: str
    ) -> Optional[UserDevice]:
        """Get a specific device"""
        query = select(UserDevice).where(
            and_(
                UserDevice.user_id == user_id,
                UserDevice.device_id == device_id
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_devices(
        self,
        db: AsyncSession,
        user_id: int
    ) -> List[UserDevice]:
        """Get all devices for a user"""
        query = select(UserDevice).where(
            UserDevice.user_id == user_id
        ).order_by(UserDevice.last_active.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def trust_device(
        self,
        db: AsyncSession,
        user_id: int,
        device_id: str
    ) -> bool:
        """Mark a device as trusted"""
        device = await self.get_device(db, user_id, device_id)
        if not device:
            return False
        
        device.is_trusted = True
        await db.commit()
        
        logger.info(f"Device {device_id} marked as trusted for user {user_id}")
        return True
    
    async def remove_device(
        self,
        db: AsyncSession,
        user_id: int,
        device_id: str
    ) -> bool:
        """Remove a device"""
        device = await self.get_device(db, user_id, device_id)
        if not device:
            return False
        
        await db.delete(device)
        await db.commit()
        
        logger.info(f"Device {device_id} removed for user {user_id}")
        return True
    
    async def record_login_attempt(
        self,
        db: AsyncSession,
        user_id: int,
        ip_address: str,
        user_agent: str,
        login_method: str,
        status: str,
        device_id: Optional[str] = None,
        location: Optional[str] = None,
        failure_reason: Optional[str] = None
    ) -> LoginHistory:
        """Record a login attempt"""
        login_record = LoginHistory(
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent[:500],  # Limit to 500 chars
            location=location,
            login_method=login_method,
            status=status,
            failure_reason=failure_reason
        )
        
        db.add(login_record)
        await db.commit()
        await db.refresh(login_record)
        
        logger.info(f"Login attempt recorded for user {user_id}: {status}")
        return login_record
    
    async def get_login_history(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[LoginHistory]:
        """Get login history for a user"""
        query = select(LoginHistory).where(
            LoginHistory.user_id == user_id
        ).order_by(
            LoginHistory.created_at.desc()
        ).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_recent_failed_attempts(
        self,
        db: AsyncSession,
        user_id: int,
        minutes: int = 30
    ) -> int:
        """Get count of recent failed login attempts"""
        since = datetime.utcnow() - timedelta(minutes=minutes)
        
        query = select(LoginHistory).where(
            and_(
                LoginHistory.user_id == user_id,
                LoginHistory.status == "failed",
                LoginHistory.created_at > since
            )
        )
        
        result = await db.execute(query)
        return len(result.scalars().all())
    
    async def is_device_trusted(
        self,
        db: AsyncSession,
        user_id: int,
        device_id: str
    ) -> bool:
        """Check if a device is trusted"""
        device = await self.get_device(db, user_id, device_id)
        return device is not None and device.is_trusted
    
    async def cleanup_inactive_devices(
        self,
        db: AsyncSession,
        days: int = 90
    ) -> int:
        """Remove devices inactive for specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(UserDevice).where(
            UserDevice.last_active < cutoff_date
        )
        
        result = await db.execute(query)
        devices = result.scalars().all()
        
        count = len(devices)
        for device in devices:
            await db.delete(device)
        
        await db.commit()
        
        if count > 0:
            logger.info(f"Cleaned up {count} inactive devices")
        
        return count


# Create global instance
device_management_service = DeviceManagementService()


__all__ = ["device_management_service", "DeviceManagementService"]