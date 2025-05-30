import pytest
from httpx import AsyncClient
import io


@pytest.mark.asyncio
async def test_get_current_user(authenticated_client: AsyncClient):
    """Test get current user endpoint"""
    response = await authenticated_client.get("/api/v1/users/me")
    assert response.status_code == 200
    
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_update_current_user(authenticated_client: AsyncClient):
    """Test update current user endpoint"""
    update_data = {
        "full_name": "Updated Name",
        "phone": "+9876543210"
    }
    
    response = await authenticated_client.put("/api/v1/users/me", json=update_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["full_name"] == update_data["full_name"]
    assert data["phone"] == update_data["phone"]


@pytest.mark.asyncio
async def test_update_password(authenticated_client: AsyncClient):
    """Test password update"""
    update_data = {
        "password": "newpassword123"
    }
    
    response = await authenticated_client.put("/api/v1/users/me", json=update_data)
    assert response.status_code == 200
    
    # Try to login with new password
    login_data = {
        "email": "test@example.com",
        "password": "newpassword123"
    }
    
    login_response = await authenticated_client.post("/api/v1/auth/login", json=login_data)
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_list_users_unauthorized(authenticated_client: AsyncClient):
    """Test list users without admin privileges"""
    response = await authenticated_client.get("/api/v1/users/")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_admin(async_client: AsyncClient, admin_user):
    """Test list users with admin privileges"""
    # Login as admin
    login_data = {
        "email": admin_user["user"].email,
        "password": admin_user["password"]
    }
    
    login_response = await async_client.post("/api/v1/auth/login", json=login_data)
    assert login_response.status_code == 200
    
    token = login_response.json()["access_token"]
    async_client.headers = {"Authorization": f"Bearer {token}"}
    
    # List users
    response = await async_client.get("/api/v1/users/")
    assert response.status_code == 200
    
    users = response.json()
    assert isinstance(users, list)
    assert len(users) >= 1


@pytest.mark.asyncio
async def test_get_user_by_id_admin(async_client: AsyncClient, admin_user, test_user):
    """Test get specific user by admin"""
    # Login as admin
    login_data = {
        "email": admin_user["user"].email,
        "password": admin_user["password"]
    }
    
    login_response = await async_client.post("/api/v1/auth/login", json=login_data)
    token = login_response.json()["access_token"]
    async_client.headers = {"Authorization": f"Bearer {token}"}
    
    # Get specific user
    user_id = test_user["user"]["id"]
    response = await async_client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == test_user["user"]["email"]


@pytest.mark.asyncio
async def test_upload_avatar(authenticated_client: AsyncClient):
    """Test avatar upload"""
    # Create a test image file
    from PIL import Image
    import io
    
    # Create a simple image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    files = {
        "file": ("test_avatar.png", img_bytes, "image/png")
    }
    
    response = await authenticated_client.post("/api/v1/users/me/avatar", files=files)
    assert response.status_code == 200
    
    data = response.json()
    assert "avatar_url" in data
    assert data["message"] == "Avatar uploaded successfully"


@pytest.mark.asyncio
async def test_delete_avatar(authenticated_client: AsyncClient):
    """Test avatar deletion"""
    response = await authenticated_client.delete("/api/v1/users/me/avatar")
    assert response.status_code == 200
    
    data = response.json()
    assert data["message"] == "Avatar deleted successfully"


@pytest.mark.asyncio
async def test_upload_invalid_file(authenticated_client: AsyncClient):
    """Test upload non-image file"""
    files = {
        "file": ("test.txt", b"This is not an image", "text/plain")
    }
    
    response = await authenticated_client.post("/api/v1/users/me/avatar", files=files)
    assert response.status_code == 400
    assert "file type not allowed" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_large_file(authenticated_client: AsyncClient):
    """Test upload file larger than limit"""
    # Create a large fake file (> 5MB)
    large_content = b"x" * (6 * 1024 * 1024)  # 6MB
    
    files = {
        "file": ("large.png", large_content, "image/png")
    }
    
    response = await authenticated_client.post("/api/v1/users/me/avatar", files=files)
    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()
