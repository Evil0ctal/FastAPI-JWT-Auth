import pytest
from httpx import AsyncClient
import pyotp
import json


@pytest.mark.asyncio
async def test_2fa_status_not_enabled(authenticated_client: AsyncClient):
    """Test 2FA status when not enabled"""
    response = await authenticated_client.get("/api/v1/2fa/status")
    assert response.status_code == 200
    
    data = response.json()
    assert data["enabled"] is False
    assert data["enabled_at"] is None


@pytest.mark.asyncio
async def test_2fa_setup(authenticated_client: AsyncClient):
    """Test 2FA setup"""
    response = await authenticated_client.post("/api/v1/2fa/setup")
    assert response.status_code == 200
    
    data = response.json()
    assert "secret" in data
    assert "qr_code" in data
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8
    
    # Verify QR code is base64 data URL
    assert data["qr_code"].startswith("data:image/png;base64,")
    
    return data["secret"]


@pytest.mark.asyncio
async def test_2fa_enable(authenticated_client: AsyncClient):
    """Test enabling 2FA"""
    # First setup 2FA
    setup_response = await authenticated_client.post("/api/v1/2fa/setup")
    secret = setup_response.json()["secret"]
    
    # Generate valid TOTP code
    totp = pyotp.TOTP(secret)
    code = totp.now()
    
    # Enable 2FA
    enable_data = {"code": code}
    response = await authenticated_client.post("/api/v1/2fa/enable", json=enable_data)
    assert response.status_code == 200
    assert response.json()["message"] == "2FA enabled successfully"
    
    # Check status
    status_response = await authenticated_client.get("/api/v1/2fa/status")
    assert status_response.json()["enabled"] is True


@pytest.mark.asyncio
async def test_2fa_enable_invalid_code(authenticated_client: AsyncClient):
    """Test enabling 2FA with invalid code"""
    # First setup 2FA
    await authenticated_client.post("/api/v1/2fa/setup")
    
    # Try to enable with invalid code
    enable_data = {"code": "123456"}
    response = await authenticated_client.post("/api/v1/2fa/enable", json=enable_data)
    assert response.status_code == 400
    assert "Invalid verification code" in response.json()["detail"]


@pytest.mark.asyncio
async def test_2fa_verify(authenticated_client: AsyncClient):
    """Test 2FA verification"""
    # Setup and enable 2FA
    setup_response = await authenticated_client.post("/api/v1/2fa/setup")
    secret = setup_response.json()["secret"]
    
    totp = pyotp.TOTP(secret)
    code = totp.now()
    
    enable_data = {"code": code}
    await authenticated_client.post("/api/v1/2fa/enable", json=enable_data)
    
    # Verify 2FA
    new_code = totp.now()
    verify_data = {"code": new_code}
    response = await authenticated_client.post("/api/v1/2fa/verify", json=verify_data)
    assert response.status_code == 200
    assert response.json()["message"] == "2FA code verified successfully"


@pytest.mark.asyncio
async def test_2fa_backup_codes(authenticated_client: AsyncClient):
    """Test 2FA backup codes"""
    # Setup and enable 2FA
    setup_response = await authenticated_client.post("/api/v1/2fa/setup")
    secret = setup_response.json()["secret"]
    backup_codes = setup_response.json()["backup_codes"]
    
    totp = pyotp.TOTP(secret)
    code = totp.now()
    
    enable_data = {"code": code}
    await authenticated_client.post("/api/v1/2fa/enable", json=enable_data)
    
    # Verify with backup code
    verify_data = {"code": backup_codes[0]}
    response = await authenticated_client.post("/api/v1/2fa/verify", json=verify_data)
    assert response.status_code == 200
    
    # Try to use the same backup code again (should fail)
    response = await authenticated_client.post("/api/v1/2fa/verify", json=verify_data)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_2fa_regenerate_backup_codes(authenticated_client: AsyncClient):
    """Test regenerating backup codes"""
    # Setup and enable 2FA first
    setup_response = await authenticated_client.post("/api/v1/2fa/setup")
    secret = setup_response.json()["secret"]
    old_backup_codes = setup_response.json()["backup_codes"]
    
    totp = pyotp.TOTP(secret)
    code = totp.now()
    
    enable_data = {"code": code}
    await authenticated_client.post("/api/v1/2fa/enable", json=enable_data)
    
    # Regenerate backup codes
    response = await authenticated_client.post("/api/v1/2fa/backup-codes/regenerate")
    assert response.status_code == 200
    
    data = response.json()
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8
    assert data["backup_codes"] != old_backup_codes


@pytest.mark.asyncio
async def test_2fa_disable(authenticated_client: AsyncClient):
    """Test disabling 2FA"""
    # Setup and enable 2FA first
    setup_response = await authenticated_client.post("/api/v1/2fa/setup")
    secret = setup_response.json()["secret"]
    
    totp = pyotp.TOTP(secret)
    code = totp.now()
    
    enable_data = {"code": code}
    await authenticated_client.post("/api/v1/2fa/enable", json=enable_data)
    
    # Disable 2FA
    response = await authenticated_client.post("/api/v1/2fa/disable")
    assert response.status_code == 200
    assert response.json()["message"] == "2FA disabled successfully"
    
    # Check status
    status_response = await authenticated_client.get("/api/v1/2fa/status")
    assert status_response.json()["enabled"] is False


@pytest.mark.asyncio
async def test_login_with_2fa(async_client: AsyncClient, test_user):
    """Test login flow with 2FA enabled"""
    # First enable 2FA for the user
    login_data = {
        "email": test_user["user"]["email"],
        "password": test_user["password"]
    }
    
    # Login to get access token
    login_response = await async_client.post("/api/v1/auth/login", json=login_data)
    token = login_response.json()["access_token"]
    
    # Setup and enable 2FA
    headers = {"Authorization": f"Bearer {token}"}
    setup_response = await async_client.post("/api/v1/2fa/setup", headers=headers)
    secret = setup_response.json()["secret"]
    
    totp = pyotp.TOTP(secret)
    code = totp.now()
    
    enable_data = {"code": code}
    await async_client.post("/api/v1/2fa/enable", json=enable_data, headers=headers)
    
    # Now try to login again
    login_response = await async_client.post("/api/v1/auth/login", json=login_data)
    assert login_response.status_code == 200
    
    data = login_response.json()
    assert data["requires_2fa"] is True
    assert "access_token" in data  # Partial token
    
    # Complete login with 2FA
    partial_token = data["access_token"]
    device_id = data.get("device_id", "test-device")
    
    new_code = totp.now()
    verify_headers = {"Authorization": f"Bearer {partial_token}"}
    
    verify_response = await async_client.post(
        "/api/v1/auth/verify-2fa",
        params={"code": new_code, "device_id": device_id},
        headers=verify_headers
    )
    assert verify_response.status_code == 200
    
    final_data = verify_response.json()
    assert "access_token" in final_data
    assert "refresh_token" in final_data
    assert final_data["token_type"] == "bearer"