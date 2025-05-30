from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base


class LoginHistory(Base):
    __tablename__ = "login_history"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String(255), nullable=True)  # Link to user device
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)  # City, Country
    login_method = Column(String(50), nullable=False)  # password, oauth, 2fa
    status = Column(String(20), nullable=False)  # success, failed, blocked
    failure_reason = Column(String(255), nullable=True)  # wrong_password, 2fa_failed, etc.
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="login_history")