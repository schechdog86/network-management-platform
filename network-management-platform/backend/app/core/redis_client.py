"""
Redis client configuration and session management
"""

import json
import logging
import time
from typing import Any, Optional, Dict
import redis.asyncio as redis
from datetime import timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis connection pool
redis_pool = None


async def init_redis() -> redis.Redis:
    """Initialize Redis connection pool"""
    global redis_pool
    
    try:
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
            health_check_interval=30
        )
        
        # Test connection
        client = redis.Redis(connection_pool=redis_pool)
        await client.ping()
        logger.info("Redis connection established successfully")
        
        return client
        
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


async def get_redis() -> redis.Redis:
    """Get Redis client"""
    if redis_pool is None:
        await init_redis()
    return redis.Redis(connection_pool=redis_pool)


class SessionManager:
    """Session management using Redis"""
    
    def __init__(self):
        self.redis_client = None
    
    async def get_client(self) -> redis.Redis:
        """Get Redis client"""
        if self.redis_client is None:
            self.redis_client = await get_redis()
        return self.redis_client
    
    async def create_session(self, user_id: int, session_data: Dict[str, Any], ttl: int = 3600) -> str:
        """Create new user session"""
        import uuid
        
        session_id = str(uuid.uuid4())
        session_key = f"session:{session_id}"
        
        session_info = {
            "user_id": user_id,
            "created_at": int(time.time()),
            **session_data
        }
        
        client = await self.get_client()
        await client.setex(session_key, ttl, json.dumps(session_info))
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        session_key = f"session:{session_id}"
        
        client = await self.get_client()
        session_data = await client.get(session_key)
        
        if session_data:
            return json.loads(session_data)
        return None
    
    async def update_session(self, session_id: str, session_data: Dict[str, Any], ttl: int = 3600):
        """Update session data"""
        session_key = f"session:{session_id}"
        
        client = await self.get_client()
        existing_data = await client.get(session_key)
        
        if existing_data:
            current_data = json.loads(existing_data)
            current_data.update(session_data)
            current_data["updated_at"] = int(time.time())
            
            await client.setex(session_key, ttl, json.dumps(current_data))
            logger.info(f"Updated session {session_id}")
        else:
            logger.warning(f"Session {session_id} not found for update")
    
    async def delete_session(self, session_id: str):
        """Delete session"""
        session_key = f"session:{session_id}"
        
        client = await self.get_client()
        deleted = await client.delete(session_key)
        
        if deleted:
            logger.info(f"Deleted session {session_id}")
        else:
            logger.warning(f"Session {session_id} not found for deletion")
    
    async def get_user_sessions(self, user_id: int) -> list[str]:
        """Get all sessions for a user"""
        client = await self.get_client()
        
        # Scan for all session keys
        session_ids = []
        async for key in client.scan_iter(match="session:*"):
            session_data = await client.get(key)
            if session_data:
                data = json.loads(session_data)
                if data.get("user_id") == user_id:
                    session_ids.append(key.decode().split(":")[1])
        
        return session_ids
    
    async def delete_user_sessions(self, user_id: int):
        """Delete all sessions for a user"""
        session_ids = await self.get_user_sessions(user_id)
        
        for session_id in session_ids:
            await self.delete_session(session_id)
        
        logger.info(f"Deleted {len(session_ids)} sessions for user {user_id}")


class CacheManager:
    """Cache management using Redis"""
    
    def __init__(self):
        self.redis_client = None
    
    async def get_client(self) -> redis.Redis:
        """Get Redis client"""
        if self.redis_client is None:
            self.redis_client = await get_redis()
        return self.redis_client
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set cache value"""
        client = await self.get_client()
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        await client.setex(key, ttl, value)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cache value"""
        client = await self.get_client()
        value = await client.get(key)
        
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value.decode()
        return None
    
    async def delete(self, key: str):
        """Delete cache key"""
        client = await self.get_client()
        await client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        client = await self.get_client()
        return bool(await client.exists(key))
    
    async def expire(self, key: str, ttl: int):
        """Set expiration for key"""
        client = await self.get_client()
        await client.expire(key, ttl)
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment numeric value"""
        client = await self.get_client()
        return await client.incrby(key, amount)
    
    async def get_pattern(self, pattern: str) -> Dict[str, Any]:
        """Get all keys matching pattern"""
        client = await self.get_client()
        
        result = {}
        async for key in client.scan_iter(match=pattern):
            value = await client.get(key)
            if value:
                try:
                    result[key.decode()] = json.loads(value)
                except json.JSONDecodeError:
                    result[key.decode()] = value.decode()
        
        return result
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        client = await self.get_client()
        
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)
        
        if keys:
            return await client.delete(*keys)
        return 0


class RateLimiter:
    """Rate limiting using Redis"""
    
    def __init__(self):
        self.redis_client = None
    
    async def get_client(self) -> redis.Redis:
        """Get Redis client"""
        if self.redis_client is None:
            self.redis_client = await get_redis()
        return self.redis_client
    
    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check if request is allowed under rate limit"""
        import time
        
        client = await self.get_client()
        current_time = int(time.time())
        window_start = current_time - window
        
        # Use sliding window log
        pipe = client.pipeline()
        
        # Remove old entries
        await pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        count = await pipe.zcard(key)
        
        if count >= limit:
            return False
        
        # Add current request
        await pipe.zadd(key, {str(current_time): current_time})
        await pipe.expire(key, window)
        
        await pipe.execute()
        return True
    
    async def get_remaining(self, key: str, limit: int, window: int) -> int:
        """Get remaining requests in current window"""
        import time
        
        client = await self.get_client()
        current_time = int(time.time())
        window_start = current_time - window
        
        # Remove old entries and count
        await client.zremrangebyscore(key, 0, window_start)
        count = await client.zcard(key)
        
        return max(0, limit - count)


# Global instances
session_manager = SessionManager()
cache_manager = CacheManager()
rate_limiter = RateLimiter()


async def health_check() -> Dict[str, Any]:
    """Redis health check"""
    try:
        client = await get_redis()
        
        # Test basic operations
        await client.ping()
        
        # Get info
        info = await client.info()
        
        return {
            "status": "healthy",
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0)
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }