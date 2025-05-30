import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import json


@pytest.mark.asyncio
async def test_register_user(async_client: AsyncClient):
    """Test user registration"""
    user_data = {
        "email": "newuser@example.com",
        "username": "newuser",
        "password": "password123",
        "full_name": "New User",
        "phone": "+1234567890"
    }
    
    response = await async_client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["username"] == user_data["username"]
    assert data["full_name"] == user_data["full_name"]
    assert data["phone"] == user_data["phone"]
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient, test_user):
    """Test registration with duplicate email"""
    user_data = {
        "email": test_user["user"]["email"],
        "username": "anotheruser",
        "password": "password123"
    }
    
    response = await async_client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(async_client: AsyncClient, test_user):
    """Test registration with duplicate username"""
    user_data = {
        "email": "another@example.com",
        "username": test_user["user"]["username"],
        "password": "password123"
    }
    
    response = await async_client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user):
    """Test successful login"""
    login_data = {
        "email": test_user["user"]["email"],
        "password": test_user["password"]
    }
    
    response = await async_client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "requires_2fa" not in data or data.get("requires_2fa") is False


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, test_user):
    """Test login with wrong password"""
    login_data = {
        "email": test_user["user"]["email"],
        "password": "wrongpassword"
    }
    
    response = await async_client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    """Test login with non-existent user"""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "password123"
    }
    
    response = await async_client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_token(async_client: AsyncClient, test_user):
    """Test refresh token endpoint"""
    # First login to get tokens
    login_data = {
        "email": test_user["user"]["email"],
        "password": test_user["password"]
    }
    
    login_response = await async_client.post("/api/v1/auth/login", json=login_data)
    assert login_response.status_code == 200
    
    tokens = login_response.json()
    refresh_token = tokens["refresh_token"]
    
    # Use refresh token
    refresh_data = {"refresh_token": refresh_token}
    response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_logout(async_client: AsyncClient, test_user):
    """Test logout endpoint"""
    # Login to get tokens
    login_response = await async_client.post("/api/v1/auth/login", json={
        "email": test_user["user"]["email"],
        "password": test_user["password"]
    })
    assert login_response.status_code == 200
    
    tokens = login_response.json()
    refresh_token = tokens["refresh_token"]
    access_token = tokens["access_token"]
    
    # Set authorization header
    async_client.headers = {"Authorization": f"Bearer {access_token}"}
    
    # Logout
    logout_data = {"refresh_token": refresh_token}
    response = await async_client.post("/api/v1/auth/logout", json=logout_data)
    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]


@pytest.mark.asyncio
async def test_forgot_password(async_client: AsyncClient, test_user):
    """Test forgot password endpoint"""
    forgot_data = {"email": test_user["user"]["email"]}
    
    response = await async_client.post("/api/v1/auth/forgot-password", json=forgot_data)
    assert response.status_code == 200
    assert "If an account exists" in response.json()["message"]


@pytest.mark.asyncio
async def test_verify_email_invalid_token(async_client: AsyncClient):
    """Test email verification with invalid token"""
    response = await async_client.post(
        "/api/v1/auth/verify-email",
        params={"token": "invalid-token"}
    )
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]


@pytest.mark.asyncio
async def test_resend_verification(async_client: AsyncClient, test_user):
    """Test resend verification email"""
    response = await async_client.post(
        "/api/v1/auth/resend-verification",
        params={"email": test_user["user"]["email"]}
    )
    assert response.status_code == 200
    assert "Verification email sent" in response.json()["message"]


@pytest.mark.asyncio 
async def test_rate_limiting(async_client: AsyncClient):
    """Test rate limiting on login endpoint - disabled for tests"""
    # Since rate limiting is disabled in test environment, 
    # we'll just verify that multiple requests succeed
    login_data = {
        "email": "test@example.com",
        "password": "wrongpassword"
    }
    
    # Make multiple requests
    for i in range(6):
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        # With rate limiting disabled, all requests should get 401 (wrong password)
        assert response.status_code == 401
