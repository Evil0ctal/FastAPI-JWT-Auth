import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_get_oauth_providers(async_client: AsyncClient):
    """Test getting available OAuth providers"""
    response = await async_client.get("/api/v1/oauth/providers")
    assert response.status_code == 200
    
    data = response.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)


@pytest.mark.asyncio
async def test_oauth_authorize_redirect(async_client: AsyncClient):
    """Test OAuth authorization redirect"""
    # Mock the OAuth service
    from unittest.mock import AsyncMock
    with patch('app.api.oauth.oauth_service') as mock_oauth:
        mock_oauth.get_authorization_url = AsyncMock(return_value="https://accounts.google.com/oauth/authorize?client_id=test")
        
        response = await async_client.get("/api/v1/oauth/authorize/google", follow_redirects=False)
        assert response.status_code == 307  # Temporary Redirect
        assert response.headers["location"] == "https://accounts.google.com/oauth/authorize?client_id=test"


@pytest.mark.asyncio
async def test_oauth_authorize_invalid_provider(async_client: AsyncClient):
    """Test OAuth authorization with invalid provider"""
    response = await async_client.get("/api/v1/oauth/authorize/invalid_provider")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oauth_callback_success(async_client: AsyncClient):
    """Test successful OAuth callback"""
    # Mock the OAuth service
    from unittest.mock import AsyncMock
    with patch('app.api.oauth.oauth_service') as mock_oauth:
        mock_oauth.handle_callback = AsyncMock(return_value={
            "access_token": "test_token",
            "token_type": "bearer",
            "user": {"id": 1, "email": "oauth@example.com"}
        })
        
        response = await async_client.get(
            "/api/v1/oauth/callback/google",
            params={"code": "test_code", "state": "test_state"},
            follow_redirects=False
        )
        
        assert response.status_code == 307  # Redirect to dashboard
        assert "token=test_token" in response.headers["location"]


@pytest.mark.asyncio
async def test_oauth_callback_failure(async_client: AsyncClient):
    """Test failed OAuth callback"""
    # Mock the OAuth service
    from unittest.mock import AsyncMock
    with patch('app.api.oauth.oauth_service') as mock_oauth:
        mock_oauth.handle_callback = AsyncMock(return_value=None)
        
        response = await async_client.get(
            "/api/v1/oauth/callback/google",
            params={"code": "test_code", "state": "test_state"},
            follow_redirects=False
        )
        
        assert response.status_code == 307  # Redirect to login
        assert "oauth_error=authentication_failed" in response.headers["location"]


@pytest.mark.asyncio
async def test_oauth_user_creation(async_client: AsyncClient):
    """Test OAuth user creation flow"""
    from app.services.oauth import oauth_service
    from unittest.mock import AsyncMock
    from tests.conftest import override_get_db
    
    # Mock the OAuth provider responses
    with patch.object(oauth_service, 'get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.exchange_code_for_token = AsyncMock(return_value={
            "access_token": "oauth_access_token",
            "refresh_token": "oauth_refresh_token",
            "expires_in": 3600
        })
        mock_provider.get_user_info = AsyncMock(return_value={
            "provider_user_id": "12345",
            "email": "newuser@gmail.com",
            "full_name": "OAuth User",
            "avatar_url": "https://example.com/avatar.jpg",
            "is_verified": True
        })
        
        mock_get_provider.return_value = mock_provider
        
        # Get a database session from the test fixture
        async for db in override_get_db():
            result = await oauth_service.handle_callback(
                db=db,
                provider_name="google",
                code="test_code",
                state="test_state"
            )
            
            assert result is not None
            assert "access_token" in result
            assert result["user"].email == "newuser@gmail.com"
            assert result["user"].is_verified is True
            break


@pytest.mark.asyncio
async def test_oauth_link_existing_user(async_client: AsyncClient, test_user):
    """Test linking OAuth to existing user"""
    from app.services.oauth import oauth_service
    from unittest.mock import AsyncMock
    from tests.conftest import override_get_db
    
    # Mock the OAuth provider responses
    with patch.object(oauth_service, 'get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.exchange_code_for_token = AsyncMock(return_value={
            "access_token": "oauth_access_token",
            "refresh_token": "oauth_refresh_token",
            "expires_in": 3600
        })
        mock_provider.get_user_info = AsyncMock(return_value={
            "provider_user_id": "67890",
            "email": test_user["user"]["email"],  # Same email as existing user
            "full_name": "OAuth User",
            "avatar_url": "https://example.com/avatar.jpg",
            "is_verified": True
        })
        
        mock_get_provider.return_value = mock_provider
        
        # Get a database session
        async for db in override_get_db():
            result = await oauth_service.handle_callback(
                db=db,
                provider_name="github",
                code="test_code",
                state="test_state"
            )
            
            assert result is not None
            assert result["user"].id == test_user["user"]["id"]  # Same user
            break
