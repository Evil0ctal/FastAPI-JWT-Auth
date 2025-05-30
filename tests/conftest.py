import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator

# Override settings BEFORE importing the app
from app.core.config import settings
settings.DATABASE_TYPE = "sqlite"
settings.SQLITE_URL = "sqlite+aiosqlite:///:memory:"
settings.EMAIL_ENABLED = False
settings.RATE_LIMIT_ENABLED = False

# Now import the app and database modules
from app.db.database import Base, get_db
from app.main import app

# Create test engine
test_engine = create_async_engine(
    settings.SQLITE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

# Create test session maker
TestingSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def async_client():
    """Create an async test client"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await test_engine.dispose()


@pytest_asyncio.fixture
async def test_user(async_client: AsyncClient):
    """Create a test user"""
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpassword123",
        "full_name": "Test User"
    }
    
    response = await async_client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 200
    
    return {
        "user": response.json(),
        "password": user_data["password"]
    }


@pytest_asyncio.fixture
async def authenticated_client(async_client: AsyncClient, test_user):
    """Create an authenticated test client"""
    login_data = {
        "email": test_user["user"]["email"],
        "password": test_user["password"]
    }
    
    response = await async_client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    
    token_data = response.json()
    access_token = token_data["access_token"]
    
    async_client.headers = {"Authorization": f"Bearer {access_token}"}
    return async_client


@pytest_asyncio.fixture
async def admin_user(async_client: AsyncClient):
    """Create an admin user"""
    from app.services.user import create_user
    from app.schemas.user import UserCreate
    
    admin_data = UserCreate(
        email="admin@example.com",
        username="adminuser",
        password="adminpassword123",
        full_name="Admin User",
        is_superuser=True,
        is_verified=True
    )
    
    async with TestingSessionLocal() as db:
        admin = await create_user(db, admin_data)
    
    return {
        "user": admin,
        "password": admin_data.password
    }
