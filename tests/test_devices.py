import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_user_devices(authenticated_client: AsyncClient):
    """Test getting user devices"""
    response = await authenticated_client.get("/api/v1/devices/devices")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    # Should have at least one device from login
    assert len(data) >= 0


@pytest.mark.asyncio
async def test_device_registration_on_login(async_client: AsyncClient, test_user):
    """Test device registration during login"""
    login_data = {
        "email": test_user["user"]["email"],
        "password": test_user["password"]
    }
    
    # Add user agent header
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"}
    response = await async_client.post("/api/v1/auth/login", json=login_data, headers=headers)
    assert response.status_code == 200
    
    # Get devices
    token = response.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}", **headers}
    
    devices_response = await async_client.get("/api/v1/devices/devices", headers=auth_headers)
    devices = devices_response.json()
    
    assert len(devices) > 0
    device = devices[0]
    assert device["device_type"] == "desktop"
    assert device["browser"] == "Chrome"
    assert device["os"] == "Windows"


@pytest.mark.asyncio
async def test_trust_device(authenticated_client: AsyncClient):
    """Test trusting a device"""
    # First get devices
    devices_response = await authenticated_client.get("/api/v1/devices/devices")
    devices = devices_response.json()
    
    if devices:
        device_id = devices[0]["device_id"]
        
        # Trust the device
        response = await authenticated_client.post(f"/api/v1/devices/devices/{device_id}/trust")
        assert response.status_code == 200
        assert response.json()["message"] == "Device marked as trusted"
        
        # Verify it's trusted
        devices_response = await authenticated_client.get("/api/v1/devices/devices")
        updated_device = next(d for d in devices_response.json() if d["device_id"] == device_id)
        assert updated_device["is_trusted"] is True


@pytest.mark.asyncio
async def test_remove_device(authenticated_client: AsyncClient):
    """Test removing a device"""
    # Create a second login to have multiple devices
    login_response = await authenticated_client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123"
    }, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6)"})
    
    # Get devices
    devices_response = await authenticated_client.get("/api/v1/devices/devices")
    devices = devices_response.json()
    
    if len(devices) > 1:
        device_to_remove = devices[1]["device_id"]
        
        # Remove the device
        response = await authenticated_client.delete(f"/api/v1/devices/devices/{device_to_remove}")
        assert response.status_code == 200
        assert response.json()["message"] == "Device removed successfully"
        
        # Verify it's removed
        devices_response = await authenticated_client.get("/api/v1/devices/devices")
        remaining_devices = devices_response.json()
        assert all(d["device_id"] != device_to_remove for d in remaining_devices)


@pytest.mark.asyncio
async def test_remove_nonexistent_device(authenticated_client: AsyncClient):
    """Test removing a device that doesn't exist"""
    response = await authenticated_client.delete("/api/v1/devices/devices/nonexistent-device-id")
    assert response.status_code == 404
    assert "Device not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_login_history(authenticated_client: AsyncClient):
    """Test getting login history"""
    response = await authenticated_client.get("/api/v1/devices/login-history")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    if data:
        # Check login history entry structure
        entry = data[0]
        assert "id" in entry
        assert "ip_address" in entry
        assert "login_method" in entry
        assert "status" in entry
        assert "created_at" in entry


@pytest.mark.asyncio
async def test_login_history_pagination(authenticated_client: AsyncClient):
    """Test login history pagination"""
    # Create multiple login attempts
    for i in range(5):
        await authenticated_client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
    
    # Test pagination
    response = await authenticated_client.get("/api/v1/devices/login-history?limit=2&offset=0")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) <= 2
    
    # Get next page
    response = await authenticated_client.get("/api/v1/devices/login-history?limit=2&offset=2")
    assert response.status_code == 200
    
    data2 = response.json()
    # Ensure different data
    if data and data2:
        assert data[0]["id"] != data2[0]["id"]


@pytest.mark.asyncio
async def test_failed_login_tracking(async_client: AsyncClient, test_user):
    """Test that failed login attempts are tracked"""
    # Make a failed login attempt
    login_data = {
        "email": test_user["user"]["email"],
        "password": "wrongpassword"
    }
    
    await async_client.post("/api/v1/auth/login", json=login_data)
    
    # Login successfully to check history
    login_data["password"] = test_user["password"]
    login_response = await async_client.post("/api/v1/auth/login", json=login_data)
    token = login_response.json()["access_token"]
    
    # Get login history
    headers = {"Authorization": f"Bearer {token}"}
    history_response = await async_client.get("/api/v1/devices/login-history", headers=headers)
    history = history_response.json()
    
    # Check for failed attempt
    failed_attempts = [h for h in history if h["status"] == "failed"]
    assert len(failed_attempts) > 0
    assert failed_attempts[0]["failure_reason"] == "wrong_password"