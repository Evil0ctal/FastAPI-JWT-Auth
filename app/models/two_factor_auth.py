from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base


class TwoFactorAuth(Base):
    __tablename__ = "two_factor_auth"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    secret = Column(String(255), nullable=False)  # Encrypted TOTP secret
    backup_codes = Column(String(1000), nullable=True)  # JSON encoded backup codes
    is_enabled = Column(Boolean, default=False, nullable=False)
    enabled_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="two_factor_auth")