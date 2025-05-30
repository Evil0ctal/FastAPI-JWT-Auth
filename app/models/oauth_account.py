from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base import Base


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False)  # google, github, wechat
    provider_user_id = Column(String(255), nullable=False)
    access_token = Column(String(512), nullable=True)
    refresh_token = Column(String(512), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="oauth_accounts")
    
    # Ensure unique provider+provider_user_id combination
    __table_args__ = (
        UniqueConstraint('provider', 'provider_user_id', name='_provider_user_uc'),
    )