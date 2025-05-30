from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.core.logging import app_logger as logger
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    result = await db.execute(select(User).filter(User.phone == phone))
    return result.scalar_one_or_none()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        phone=user.phone,
        avatar_url=user.avatar_url,
        hashed_password=hashed_password,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    logger.info(f"Created new user: {user.email} (ID: {db_user.id})")
    return db_user


async def update_user(db: AsyncSession, user: User, user_update: UserUpdate) -> User:
    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user:
        logger.warning(f"Authentication failed: User not found for email {email}")
        return None
    if not verify_password(password, user.hashed_password):
        logger.warning(f"Authentication failed: Invalid password for user {email}")
        return None
    
    # Update last login
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login=datetime.utcnow())
    )
    await db.commit()
    
    logger.info(f"User authenticated successfully: {email}")
    return user


async def update_last_login(db: AsyncSession, user_id: int) -> None:
    """Update user's last login timestamp"""
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(last_login=datetime.utcnow())
    )
    await db.commit()


async def create_user_oauth(
    db: AsyncSession,
    email: str,
    full_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    is_verified: bool = False
) -> User:
    """Create user from OAuth provider data"""
    import secrets
    import string
    
    # Generate username from email
    username_base = email.split('@')[0]
    username = username_base
    counter = 1
    while await get_user_by_username(db, username):
        username = f"{username_base}{counter}"
        counter += 1
    
    # Generate random password (user won't use it for OAuth login)
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    db_user = User(
        email=email,
        username=username,
        full_name=full_name,
        avatar_url=avatar_url,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_superuser=False,
        is_verified=is_verified
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    logger.info(f"Created new OAuth user: {email} (ID: {db_user.id})")
    return db_user
