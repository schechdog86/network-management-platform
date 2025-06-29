"""
Authentication API tests
"""

import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_create_user(client: TestClient):
    """Test user creation"""
    # First create admin user would be needed
    # This is a placeholder test
    pass


def test_login(client: TestClient):
    """Test user login"""
    # This is a placeholder test
    pass


def test_protected_endpoint_without_token(client: TestClient):
    """Test accessing protected endpoint without token"""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_hashing():
    """Test password hashing functionality"""
    from app.core.auth import get_password_hash, verify_password
    
    password = "test_password_123"
    hashed = get_password_hash(password)
    
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)


@pytest.mark.asyncio
async def test_jwt_tokens():
    """Test JWT token creation and verification"""
    from app.core.auth import create_access_token, decode_token
    
    data = {"sub": "testuser"}
    token = create_access_token(data)
    
    token_data = decode_token(token)
    assert token_data is not None
    assert token_data.username == "testuser"