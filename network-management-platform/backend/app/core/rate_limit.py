"""
Rate limiting implementation for API endpoints
"""

import time
from typing import Optional, Dict, Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from datetime import datetime, timedelta
import json
import hashlib

from app.core.config import settings
from app.core.redis_client import get_redis_client


class RateLimiter:
    """Rate limiter using Redis for distributed rate limiting"""
    
    def __init__(
        self,
        requests: int,
        window: int,
        identifier: Optional[Callable] = None,
        error_message: str = "Rate limit exceeded"
    ):
        """
        Initialize rate limiter
        
        Args:
            requests: Number of allowed requests
            window: Time window in seconds
            identifier: Function to extract identifier from request (default: IP address)
            error_message: Error message to return when rate limit is exceeded
        """
        self.requests = requests
        self.window = window
        self.identifier = identifier or self._default_identifier
        self.error_message = error_message
    
    def _default_identifier(self, request: Request) -> str:
        """Default identifier using IP address"""
        # Get real IP considering proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0]
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"
    
    async def __call__(self, request: Request) -> None:
        """Check rate limit for the request"""
        redis_client = await get_redis_client()
        
        # Get identifier for this request
        identifier = self.identifier(request)
        key = f"rate_limit:{request.url.path}:{identifier}"
        
        try:
            # Use Redis pipeline for atomic operations
            async with redis_client.pipeline() as pipe:
                # Get current window start time
                now = time.time()
                window_start = now - self.window
                
                # Remove old entries
                await pipe.zremrangebyscore(key, 0, window_start)
                
                # Count requests in current window
                await pipe.zcard(key)
                
                # Add current request
                await pipe.zadd(key, {str(now): now})
                
                # Set expiry
                await pipe.expire(key, self.window)
                
                # Execute pipeline
                results = await pipe.execute()
                request_count = results[1]  # zcard result
                
                if request_count >= self.requests:
                    # Calculate retry after
                    oldest_request = await redis_client.zrange(key, 0, 0, withscores=True)
                    if oldest_request:
                        retry_after = int(self.window - (now - oldest_request[0][1]))
                    else:
                        retry_after = self.window
                    
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=self.error_message,
                        headers={"Retry-After": str(retry_after)}
                    )
                    
        except redis.RedisError as e:
            # Log error but don't block request if Redis is down
            print(f"Rate limiting error: {e}")
            # Could implement fallback to in-memory rate limiting here


class UserRateLimiter(RateLimiter):
    """Rate limiter that uses authenticated user ID"""
    
    def __init__(self, requests: int, window: int, error_message: str = "Rate limit exceeded"):
        super().__init__(requests, window, self._user_identifier, error_message)
    
    def _user_identifier(self, request: Request) -> str:
        """Extract user ID from request"""
        # This assumes user is attached to request by auth middleware
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.id}"
        # Fallback to IP-based limiting for unauthenticated requests
        return self._default_identifier(request)


class EndpointRateLimiter(RateLimiter):
    """Rate limiter for specific endpoint patterns"""
    
    def __init__(
        self,
        default_requests: int = 100,
        default_window: int = 60,
        endpoint_limits: Optional[Dict[str, Dict[str, int]]] = None
    ):
        """
        Initialize endpoint-specific rate limiter
        
        Args:
            default_requests: Default number of requests
            default_window: Default window in seconds
            endpoint_limits: Dict of endpoint patterns to limits
                Example: {
                    "/api/v1/auth/*": {"requests": 5, "window": 60},
                    "/api/v1/devices/scan": {"requests": 10, "window": 300}
                }
        """
        self.default_requests = default_requests
        self.default_window = default_window
        self.endpoint_limits = endpoint_limits or {}
        super().__init__(default_requests, default_window)
    
    async def __call__(self, request: Request) -> None:
        """Check rate limit based on endpoint"""
        # Find matching endpoint pattern
        path = request.url.path
        
        for pattern, limits in self.endpoint_limits.items():
            if self._match_pattern(path, pattern):
                self.requests = limits["requests"]
                self.window = limits["window"]
                break
        else:
            # Use defaults if no pattern matches
            self.requests = self.default_requests
            self.window = self.default_window
        
        await super().__call__(request)
    
    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern (supports * wildcard)"""
        if "*" in pattern:
            # Simple wildcard matching
            pattern_parts = pattern.split("*")
            if len(pattern_parts) == 2:
                return path.startswith(pattern_parts[0]) and path.endswith(pattern_parts[1])
        return path == pattern


# Pre-configured rate limiters
def rate_limit(requests: int = 100, window: int = 60):
    """Decorator to apply rate limiting to an endpoint"""
    def decorator(func):
        limiter = RateLimiter(requests, window)
        func.__rate_limiter__ = limiter
        return func
    return decorator


# Common rate limiters
auth_rate_limiter = RateLimiter(
    requests=5,
    window=60,
    error_message="Too many authentication attempts. Please try again later."
)

general_rate_limiter = RateLimiter(
    requests=100,
    window=60,
    error_message="Too many requests. Please slow down."
)

bulk_operation_limiter = RateLimiter(
    requests=10,
    window=300,
    error_message="Too many bulk operations. Please wait before trying again."
)

# Endpoint-specific rate limiter with common patterns
api_rate_limiter = EndpointRateLimiter(
    default_requests=100,
    default_window=60,
    endpoint_limits={
        "/api/v1/auth/login": {"requests": 5, "window": 60},
        "/api/v1/auth/register": {"requests": 3, "window": 300},
        "/api/v1/devices/scan": {"requests": 10, "window": 300},
        "/api/v1/backup/jobs": {"requests": 10, "window": 300},
        "/api/v1/pxe/deployments": {"requests": 5, "window": 300},
        "/api/v1/wake-on-lan/wake/bulk": {"requests": 10, "window": 60},
    }
)


# Middleware to apply rate limiting globally
async def rate_limit_middleware(request: Request, call_next):
    """Global rate limiting middleware"""
    # Skip rate limiting for health checks and docs
    if request.url.path in ["/health", "/api/docs", "/api/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Apply endpoint-specific rate limiting
    try:
        await api_rate_limiter(request)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail},
            headers=e.headers
        )
    
    response = await call_next(request)
    
    # Add rate limit headers to response
    redis_client = await get_redis_client()
    identifier = api_rate_limiter.identifier(request)
    key = f"rate_limit:{request.url.path}:{identifier}"
    
    try:
        # Get current usage
        now = time.time()
        window_start = now - api_rate_limiter.window
        count = await redis_client.zcount(key, window_start, now)
        
        response.headers["X-RateLimit-Limit"] = str(api_rate_limiter.requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, api_rate_limiter.requests - count))
        response.headers["X-RateLimit-Reset"] = str(int(now + api_rate_limiter.window))
    except:
        pass  # Don't fail if we can't add headers
    
    return response