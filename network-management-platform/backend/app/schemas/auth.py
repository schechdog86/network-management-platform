"""
Authentication schemas for request/response validation
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token data extracted from JWT"""
    username: Optional[str] = None


class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """User update schema"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    """User schema with database fields"""
    id: int
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    roles: List[str] = []
    
    model_config = ConfigDict(from_attributes=True)


class User(UserInDB):
    """User response schema"""
    pass


class UserLogin(BaseModel):
    """User login schema"""
    username: str
    password: str


class PasswordChange(BaseModel):
    """Password change schema"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class RoleBase(BaseModel):
    """Base role schema"""
    name: str = Field(..., min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    permissions: List[str] = []


class RoleCreate(RoleBase):
    """Role creation schema"""
    pass


class RoleUpdate(BaseModel):
    """Role update schema"""
    name: Optional[str] = Field(None, min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    permissions: Optional[List[str]] = None


class Role(RoleBase):
    """Role response schema"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AuditLogBase(BaseModel):
    """Base audit log schema"""
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[dict] = None


class AuditLog(AuditLogBase):
    """Audit log response schema"""
    id: int
    user_id: int
    username: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)