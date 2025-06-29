"""
Authentication and authorization module
JWT token generation and validation
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import TokenData

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token settings
ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        token_data = TokenData(username=username)
        return token_data
    except JWTError:
        return None


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password"""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    return user


async def get_current_user(db: AsyncSession, token: str) -> Optional[User]:
    """Get current user from JWT token"""
    token_data = decode_token(token)
    if token_data is None:
        return None
    
    result = await db.execute(
        select(User).where(
            User.username == token_data.username,
            User.is_active == True
        )
    )
    user = result.scalar_one_or_none()
    return user


def create_api_key(user_id: int) -> str:
    """Create API key for a user"""
    data = {
        "sub": str(user_id),
        "type": "api_key",
        "iat": datetime.utcnow()
    }
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


async def validate_api_key(db: AsyncSession, api_key: str) -> Optional[User]:
    """Validate API key and return associated user"""
    try:
        payload = jwt.decode(api_key, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "api_key":
            return None
        
        user_id = int(payload.get("sub"))
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.is_active == True
            )
        )
        return result.scalar_one_or_none()
    except (JWTError, ValueError):
        return None


def check_permissions(user: User, required_permissions: list[str]) -> bool:
    """Check if user has required permissions"""
    if user.is_superuser:
        return True
    
    user_permissions = set()
    for role in user.roles:
        user_permissions.update(role.permissions)
    
    return all(perm in user_permissions for perm in required_permissions)