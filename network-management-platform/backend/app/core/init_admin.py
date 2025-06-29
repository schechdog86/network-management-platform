"""
Initialize default admin user and roles
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.auth import get_password_hash
from app.models.user import User, Role

logger = logging.getLogger(__name__)


async def create_default_roles(db: AsyncSession):
    """Create default roles"""
    default_roles = [
        {
            "name": "admin",
            "description": "Full system administrator access",
            "permissions": [
                "system:manage",
                "users:manage", 
                "devices:manage",
                "network:manage",
                "backup:manage",
                "ai:manage"
            ]
        },
        {
            "name": "operator",
            "description": "Network operations access",
            "permissions": [
                "devices:read",
                "devices:control",
                "network:read",
                "network:manage",
                "backup:read"
            ]
        },
        {
            "name": "viewer",
            "description": "Read-only access to system information",
            "permissions": [
                "devices:read",
                "network:read",
                "backup:read"
            ]
        }
    ]
    
    for role_data in default_roles:
        # Check if role exists
        result = await db.execute(select(Role).where(Role.name == role_data["name"]))
        existing_role = result.scalar_one_or_none()
        
        if not existing_role:
            import json
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
                permissions=json.dumps(role_data["permissions"])
            )
            db.add(role)
            logger.info(f"Created role: {role_data['name']}")
    
    await db.commit()


async def create_admin_user(db: AsyncSession):
    """Create default admin user"""
    admin_username = "admin"
    admin_email = "admin@networkplatform.local"
    admin_password = "admin123"  # Change this in production!
    
    # Check if admin user exists
    result = await db.execute(select(User).where(User.username == admin_username))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        logger.info("Admin user already exists")
        return existing_user
    
    # Get admin role
    result = await db.execute(select(Role).where(Role.name == "admin"))
    admin_role = result.scalar_one_or_none()
    
    if not admin_role:
        logger.error("Admin role not found")
        return None
    
    # Create admin user
    admin_user = User(
        username=admin_username,
        email=admin_email,
        full_name="System Administrator",
        hashed_password=get_password_hash(admin_password),
        is_active=True,
        is_superuser=True
    )
    
    admin_user.roles.append(admin_role)
    db.add(admin_user)
    await db.commit()
    await db.refresh(admin_user)
    
    logger.info(f"Created admin user: {admin_username}")
    logger.warning(f"Default admin password is '{admin_password}' - CHANGE THIS IN PRODUCTION!")
    
    return admin_user


async def init_admin_data():
    """Initialize admin user and roles"""
    try:
        async with AsyncSessionLocal() as db:
            logger.info("Initializing admin data...")
            
            # Create default roles
            await create_default_roles(db)
            
            # Create admin user
            await create_admin_user(db)
            
            logger.info("Admin data initialization complete")
            
    except Exception as e:
        logger.error(f"Failed to initialize admin data: {e}")
        raise


if __name__ == "__main__":
    # Run initialization
    asyncio.run(init_admin_data())