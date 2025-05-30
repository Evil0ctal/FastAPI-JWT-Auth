import asyncio
from datetime import datetime
from app.db.database import db_manager
from app.services.refresh_token import refresh_token_service
from app.services.password_reset import password_reset_service
from app.services.device_management import device_management_service
import logging

logger = logging.getLogger(__name__)


async def cleanup_expired_tokens():
    """Background task to cleanup expired tokens"""
    while True:
        try:
            async with db_manager.async_session_maker() as db:
                # Cleanup refresh tokens
                refresh_count = await refresh_token_service.cleanup_expired_tokens(db)
                if refresh_count > 0:
                    logger.info(f"Cleaned up {refresh_count} expired refresh tokens")
                
                # Cleanup password reset tokens
                reset_count = await password_reset_service.cleanup_expired_tokens(db)
                if reset_count > 0:
                    logger.info(f"Cleaned up {reset_count} expired password reset tokens")
                
                # Cleanup inactive devices (older than 90 days)
                device_count = await device_management_service.cleanup_inactive_devices(db, days=90)
                if device_count > 0:
                    logger.info(f"Cleaned up {device_count} inactive devices")
        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
        
        # Run every hour
        await asyncio.sleep(3600)


def start_background_tasks():
    """Start all background tasks"""
    asyncio.create_task(cleanup_expired_tokens())
    logger.info("Background tasks started")

