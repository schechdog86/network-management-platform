"""
Request/Response logging middleware
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json

from app.core.logging_config import get_logger, log_performance_metric, TimedOperation


logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.exclude_paths = {"/health", "/metrics", "/api/docs", "/api/redoc", "/openapi.json"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        await self._log_request(request, request_id)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.2f}ms"
            
            # Log response
            await self._log_response(request, response, duration, request_id)
            
            # Log performance metric
            log_performance_metric(
                "http_request_duration",
                duration,
                unit="ms",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code
            )
            
            return response
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=e,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            
            # Re-raise exception
            raise
    
    async def _log_request(self, request: Request, request_id: str) -> None:
        """Log incoming request"""
        # Get client info
        client_host = request.client.host if request.client else "unknown"
        
        # Get user info if available
        user_info = {}
        if hasattr(request.state, "user") and request.state.user:
            user_info = {
                "user_id": str(request.state.user.id),
                "username": request.state.user.username
            }
        
        # Prepare log data
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_host": client_host,
            "user_agent": request.headers.get("user-agent", "unknown"),
            **user_info
        }
        
        # Log content type and size for POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            log_data["content_type"] = request.headers.get("content-type", "unknown")
            log_data["content_length"] = request.headers.get("content-length", "0")
        
        logger.info(
            f"Request received: {request.method} {request.url.path}",
            extra=log_data
        )
    
    async def _log_response(self, request: Request, response: Response, duration: float, request_id: str) -> None:
        """Log outgoing response"""
        # Get user info if available
        user_info = {}
        if hasattr(request.state, "user") and request.state.user:
            user_info = {
                "user_id": str(request.state.user.id),
                "username": request.state.user.username
            }
        
        # Prepare log data
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration,
            **user_info
        }
        
        # Log level based on status code
        if response.status_code >= 500:
            logger.error(
                f"Request completed with error: {request.method} {request.url.path} - {response.status_code}",
                extra=log_data
            )
        elif response.status_code >= 400:
            logger.warning(
                f"Request completed with client error: {request.method} {request.url.path} - {response.status_code}",
                extra=log_data
            )
        else:
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra=log_data
            )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to add request context to all log records"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Create a context that will be available to all loggers
        import contextvars
        
        request_context = contextvars.ContextVar('request_context', default=None)
        
        # Set request context
        token = request_context.set({
            'request_id': getattr(request.state, 'request_id', None),
            'user_id': getattr(request.state, 'user', {}).get('id') if hasattr(request.state, 'user') else None,
            'method': request.method,
            'path': request.url.path,
            'client_host': request.client.host if request.client else 'unknown'
        })
        
        try:
            response = await call_next(request)
            return response
        finally:
            # Reset context
            request_context.reset(token)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log audit events for sensitive operations"""
    
    AUDIT_PATHS = {
        "/api/v1/auth/register": "user_registration",
        "/api/v1/auth/token": "user_login",
        "/api/v1/auth/change-password": "password_change",
        "/api/v1/devices": "device_management",
        "/api/v1/backup/jobs": "backup_operation",
        "/api/v1/pxe/deployments": "pxe_deployment"
    }
    
    AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if this request should be audited
        should_audit = (
            request.method in self.AUDIT_METHODS and
            any(request.url.path.startswith(path) for path in self.AUDIT_PATHS)
        )
        
        if not should_audit:
            return await call_next(request)
        
        # Get audit event type
        event_type = None
        for path, etype in self.AUDIT_PATHS.items():
            if request.url.path.startswith(path):
                event_type = etype
                break
        
        # Process request
        response = await call_next(request)
        
        # Log audit event
        await self._log_audit_event(request, response, event_type)
        
        return response
    
    async def _log_audit_event(self, request: Request, response: Response, event_type: str) -> None:
        """Log an audit event"""
        from app.core.logging_config import log_security_event
        
        # Get user info
        user_id = None
        username = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = str(request.state.user.id)
            username = request.state.user.username
        
        # Determine success
        success = 200 <= response.status_code < 300
        
        # Log security event
        log_security_event(
            event_type=event_type,
            success=success,
            user_id=user_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            client_host=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown"),
            username=username
        )