"""
Centralized logging configuration for the application
"""

import logging
import logging.handlers
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import traceback
from pythonjsonlogger import jsonlogger

from app.core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add custom fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['environment'] = settings.ENVIRONMENT
        
        # Add context information if available
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        
        if hasattr(record, 'ip_address'):
            log_record['ip_address'] = record.ip_address
        
        # Add exception information
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
            log_record['stack_trace'] = traceback.format_exc()


class SecurityFilter(logging.Filter):
    """Filter to prevent logging of sensitive information"""
    
    SENSITIVE_FIELDS = [
        'password', 'token', 'secret', 'api_key', 'apikey',
        'authorization', 'cookie', 'session', 'csrf',
        'credit_card', 'card_number', 'cvv', 'ssn'
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Check message for sensitive data
        message = str(record.getMessage()).lower()
        
        for field in self.SENSITIVE_FIELDS:
            if field in message:
                # Mask sensitive data
                record.msg = self._mask_sensitive_data(record.msg, field)
        
        # Check extra fields
        for field in self.SENSITIVE_FIELDS:
            if hasattr(record, field):
                setattr(record, field, "***MASKED***")
        
        return True
    
    def _mask_sensitive_data(self, message: str, field: str) -> str:
        """Mask sensitive data in message"""
        import re
        
        # Simple masking - replace field value with asterisks
        pattern = f"{field}['\"]?[:=]['\"]?([^'\"\\s]+)"
        return re.sub(pattern, f"{field}=***MASKED***", message, flags=re.IGNORECASE)


class RequestContextFilter(logging.Filter):
    """Add request context to log records"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Import here to avoid circular imports
        from fastapi import Request
        from starlette.middleware.base import RequestResponseEndpoint
        
        # Try to get current request from context
        # This would need to be set by middleware
        request = getattr(record, 'request', None)
        
        if request and isinstance(request, Request):
            record.request_id = request.headers.get('X-Request-ID', 'no-request-id')
            record.ip_address = request.client.host if request.client else 'unknown'
            record.method = request.method
            record.path = request.url.path
            
            # Add user info if available
            if hasattr(request.state, 'user') and request.state.user:
                record.user_id = str(request.state.user.id)
                record.username = request.state.user.username
        
        return True


def setup_logging() -> None:
    """Configure application logging"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove default handlers
    root_logger.handlers = []
    
    # Console handler with colored output for development
    if settings.ENVIRONMENT == "development":
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(SecurityFilter())
        root_logger.addHandler(console_handler)
    
    # JSON file handler for production
    json_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "app.json",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    json_formatter = CustomJsonFormatter()
    json_handler.setFormatter(json_formatter)
    json_handler.addFilter(SecurityFilter())
    json_handler.addFilter(RequestContextFilter())
    root_logger.addHandler(json_handler)
    
    # Error log handler
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_handler.setFormatter(error_formatter)
    error_handler.addFilter(SecurityFilter())
    root_logger.addHandler(error_handler)
    
    # Security log handler
    security_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "security.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10  # Keep more security logs
    )
    security_formatter = CustomJsonFormatter()
    security_handler.setFormatter(security_formatter)
    security_handler.addFilter(SecurityFilter())
    
    # Add security handler to security logger
    security_logger = logging.getLogger("security")
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.INFO)
    security_logger.propagate = False
    
    # Performance log handler
    performance_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "performance.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    performance_formatter = CustomJsonFormatter()
    performance_handler.setFormatter(performance_formatter)
    
    # Add performance handler to performance logger
    performance_logger = logging.getLogger("performance")
    performance_logger.addHandler(performance_handler)
    performance_logger.setLevel(logging.INFO)
    performance_logger.propagate = False
    
    # Configure third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("ray").setLevel(logging.WARNING)
    
    # Suppress noisy loggers
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    
    root_logger.info("Logging system initialized", extra={
        "log_level": root_logger.level,
        "handlers": [h.__class__.__name__ for h in root_logger.handlers],
        "environment": settings.ENVIRONMENT
    })


# Logger factory
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


# Specialized loggers
def get_security_logger() -> logging.Logger:
    """Get security logger for authentication and authorization events"""
    return logging.getLogger("security")


def get_performance_logger() -> logging.Logger:
    """Get performance logger for monitoring application performance"""
    return logging.getLogger("performance")


# Logging utilities
def log_exception(logger: logging.Logger, message: str, exc: Exception, **kwargs) -> None:
    """Log an exception with context"""
    logger.error(
        message,
        exc_info=exc,
        extra={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            **kwargs
        }
    )


def log_security_event(event_type: str, success: bool, user_id: Optional[str] = None, **details) -> None:
    """Log a security event"""
    security_logger = get_security_logger()
    
    log_data = {
        "event_type": event_type,
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
        **details
    }
    
    if user_id:
        log_data["user_id"] = user_id
    
    if success:
        security_logger.info(f"Security event: {event_type}", extra=log_data)
    else:
        security_logger.warning(f"Security event failed: {event_type}", extra=log_data)


def log_performance_metric(metric_name: str, value: float, unit: str = "ms", **tags) -> None:
    """Log a performance metric"""
    performance_logger = get_performance_logger()
    
    performance_logger.info(
        f"Performance metric: {metric_name}",
        extra={
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "timestamp": datetime.utcnow().isoformat(),
            **tags
        }
    )


# Context managers for logging
class LogContext:
    """Context manager for adding context to logs"""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_context = {}
    
    def __enter__(self):
        # Save old context and set new context
        for key, value in self.context.items():
            if hasattr(self.logger, key):
                self.old_context[key] = getattr(self.logger, key)
            setattr(self.logger, key, value)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old context
        for key in self.context:
            if key in self.old_context:
                setattr(self.logger, key, self.old_context[key])
            else:
                delattr(self.logger, key)


class TimedOperation:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None, **tags):
        self.operation_name = operation_name
        self.logger = logger or get_performance_logger()
        self.tags = tags
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.utcnow() - self.start_time).total_seconds() * 1000
        
        log_data = {
            "operation": self.operation_name,
            "duration_ms": duration,
            "success": exc_type is None,
            **self.tags
        }
        
        if exc_type:
            log_data["error"] = str(exc_val)
        
        self.logger.info(f"Operation completed: {self.operation_name}", extra=log_data)