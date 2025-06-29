"""
Authentication API endpoints
"""

from datetime import timedelta
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.core.logging_config import get_logger, log_security_event, TimedOperation
from app.core.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    decode_token,
    create_api_key,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.models.user import User, Role, AuditLog
from app.core.rate_limit import auth_rate_limiter
from app.core.validation import validate_request, validate_user_registration, DataValidator
from app.schemas.auth import (
    Token,
    User as UserSchema,
    UserCreate,
    UserUpdate,
    UserLogin,
    PasswordChange,
    Role as RoleSchema,
    RoleCreate,
    RoleUpdate,
    AuditLog as AuditLogSchema
)

logger = get_logger(__name__)

router = APIRouter()

# OAuth2 scheme for JWT tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_active_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current active user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    user = await get_current_user(db, token)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user if they have admin privileges"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def log_audit_action(
    db: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    resource_id: str = None,
    details: dict = None,
    request: Request = None
):
    """Log user action for audit trail"""
    audit_log = AuditLog(
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=json.dumps(details) if details else None,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None
    )
    db.add(audit_log)
    await db.commit()


@router.post("/register", response_model=UserSchema, dependencies=[Depends(auth_rate_limiter)])
async def register_user(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
    request: Request = None
):
    """Register a new user (admin only)"""
    # Validate user data
    validation_result = validate_user_registration(user_create)
    if not validation_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": validation_result["errors"]}
        )
    
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_create.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_create.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_create.password)
    db_user = User(
        username=user_create.username,
        email=user_create.email,
        full_name=user_create.full_name,
        hashed_password=hashed_password,
        is_active=user_create.is_active
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    # Log audit action
    await log_audit_action(
        db, current_user, "create_user", "user", 
        str(db_user.id), {"username": db_user.username}, request
    )
    
    return db_user


@router.post("/token", response_model=Token, dependencies=[Depends(auth_rate_limiter)])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Login endpoint that returns JWT tokens"""
    async with TimedOperation("user_login", logger, username=form_data.username):
        user = await authenticate_user(db, form_data.username, form_data.password)
        if not user:
            await log_audit_action(
                db, None, "failed_login", "user", 
                form_data.username, {"reason": "invalid_credentials"}, request
            )
            log_security_event(
                "login_failed",
                success=False,
                username=form_data.username,
                reason="invalid_credentials",
                ip_address=request.client.host if request.client else "unknown"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user.username})
    
    # Log successful login
    await log_audit_action(
        db, user, "login", "user", None, {"method": "password"}, request
    )
    
    log_security_event(
        "login_success",
        success=True,
        user_id=str(user.id),
        username=user.username,
        ip_address=request.client.host if request.client else "unknown"
    )
    
    logger.info(f"User logged in successfully: {user.username}")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=Token, dependencies=[Depends(auth_rate_limiter)])
async def refresh_access_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = decode_token(refresh_token)
    if token_data is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.username == token_data.username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(data={"sub": user.username})
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserSchema)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Update current user information"""
    update_data = user_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "password":
            current_user.hashed_password = get_password_hash(value)
        else:
            setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    # Log audit action
    await log_audit_action(
        db, current_user, "update_profile", "user", 
        str(current_user.id), {"fields": list(update_data.keys())}, request
    )
    
    return current_user


@router.post("/change-password", dependencies=[Depends(auth_rate_limiter)])
async def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Change user password"""
    from app.core.auth import verify_password
    
    if not verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    current_user.hashed_password = get_password_hash(password_change.new_password)
    await db.commit()
    
    # Log audit action
    await log_audit_action(
        db, current_user, "change_password", "user", 
        str(current_user.id), None, request
    )
    
    return {"message": "Password changed successfully"}


@router.post("/api-key", dependencies=[Depends(auth_rate_limiter)])
async def generate_api_key(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Generate API key for current user"""
    api_key = create_api_key(current_user.id)
    current_user.api_key = api_key
    await db.commit()
    
    # Log audit action
    await log_audit_action(
        db, current_user, "generate_api_key", "user", 
        str(current_user.id), None, request
    )
    
    return {"api_key": api_key}


@router.get("/users", response_model=List[UserSchema])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)"""
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/users/{user_id}", response_model=UserSchema)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID (admin only)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Update user by ID (admin only)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "password":
            user.hashed_password = get_password_hash(value)
        else:
            setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    # Log audit action
    await log_audit_action(
        db, current_user, "update_user", "user", 
        str(user.id), {"fields": list(update_data.keys())}, request
    )
    
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Delete user by ID (admin only)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    await db.delete(user)
    await db.commit()
    
    # Log audit action
    await log_audit_action(
        db, current_user, "delete_user", "user", 
        str(user.id), {"username": user.username}, request
    )
    
    return {"message": "User deleted successfully"}