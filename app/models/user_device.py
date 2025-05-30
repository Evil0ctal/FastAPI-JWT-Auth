from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserDevice(Base):
    __tablename__ = "user_devices"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String(255), nullable=False)  # Unique device identifier
    device_name = Column(String(255), nullable=False)  # User-friendly device name
    device_type = Column(String(50), nullable=False)  # mobile, desktop, tablet, etc.
    browser = Column(String(100), nullable=True)  # Browser name
    browser_version = Column(String(50), nullable=True)
    os = Column(String(100), nullable=True)  # Operating system
    os_version = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    location = Column(String(255), nullable=True)  # City, Country
    is_trusted = Column(Boolean, default=False, nullable=False)
    last_active = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="devices")
    
    # Ensure unique device per user
    __table_args__ = (
        UniqueConstraint('user_id', 'device_id', name='_user_device_uc'),
    )