from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base


class DatabaseManager:
    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.async_session_maker: async_sessionmaker | None = None

    async def initialize(self):
        if settings.DATABASE_TYPE == "sqlite":
            # SQLite specific settings
            connect_args = {"check_same_thread": False}
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.ENVIRONMENT == "development",
                connect_args=connect_args
            )
        else:
            # MySQL specific settings
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.ENVIRONMENT == "development",
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20
            )
        
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def create_tables(self):
        from app.models import user  # Import models to register them
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        if self.engine:
            await self.engine.dispose()


db_manager = DatabaseManager()

# For backward compatibility with cleanup tasks
AsyncSessionLocal = None  # Will be set after initialization


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
