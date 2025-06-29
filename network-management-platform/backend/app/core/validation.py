"""
Data validation middleware and utilities
"""

from typing import Any, Dict, List, Optional, Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError, BaseModel
import json
import re
from datetime import datetime
import ipaddress


class ValidationError(HTTPException):
    """Custom validation error with detailed error messages"""
    def __init__(self, errors: List[Dict[str, Any]]):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": errors}
        )


class DataValidator:
    """Base data validator class"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username format (alphanumeric, underscore, dash, 3-32 chars)"""
        pattern = r'^[a-zA-Z0-9_-]{3,32}$'
        return bool(re.match(pattern, username))
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """
        Validate password strength
        Returns dict with validation results
        """
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "strength": DataValidator._calculate_password_strength(password)
        }
    
    @staticmethod
    def _calculate_password_strength(password: str) -> str:
        """Calculate password strength (weak, medium, strong)"""
        score = 0
        
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        if re.search(r'[A-Z]', password) and re.search(r'[a-z]', password):
            score += 1
        if re.search(r'\d', password):
            score += 1
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        
        if score <= 2:
            return "weak"
        elif score <= 4:
            return "medium"
        else:
            return "strong"
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address (IPv4 or IPv6)"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_mac_address(mac: str) -> bool:
        """Validate MAC address format"""
        pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(pattern, mac))
    
    @staticmethod
    def validate_hostname(hostname: str) -> bool:
        """Validate hostname format"""
        if len(hostname) > 255:
            return False
        
        if hostname.endswith("."):
            hostname = hostname[:-1]
        
        allowed = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
        return all(allowed.match(x) for x in hostname.split("."))
    
    @staticmethod
    def validate_port(port: int) -> bool:
        """Validate port number"""
        return 1 <= port <= 65535
    
    @staticmethod
    def validate_cidr(cidr: str) -> bool:
        """Validate CIDR notation"""
        try:
            ipaddress.ip_network(cidr, strict=False)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_cron(cron: str) -> bool:
        """Validate cron expression"""
        # Simple validation for standard cron format (5 fields)
        fields = cron.strip().split()
        if len(fields) != 5:
            return False
        
        # Define allowed values for each field
        allowed_values = [
            r'^(\*|[0-5]?\d)(,(\*|[0-5]?\d))*$',  # minute
            r'^(\*|[01]?\d|2[0-3])(,(\*|[01]?\d|2[0-3]))*$',  # hour
            r'^(\*|[1-9]|[12]\d|3[01])(,(\*|[1-9]|[12]\d|3[01]))*$',  # day
            r'^(\*|[1-9]|1[0-2])(,(\*|[1-9]|1[0-2]))*$',  # month
            r'^(\*|[0-7])(,(\*|[0-7]))*$',  # weekday
        ]
        
        for i, field in enumerate(fields):
            if not re.match(allowed_values[i], field):
                return False
        
        return True


class SanitizationMiddleware:
    """Middleware to sanitize input data"""
    
    @staticmethod
    def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
        """Sanitize string input"""
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Strip whitespace
        value = value.strip()
        
        # Limit length if specified
        if max_length and len(value) > max_length:
            value = value[:max_length]
        
        return value
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent directory traversal"""
        # Remove path separators and null bytes
        filename = filename.replace('/', '').replace('\\', '').replace('\x00', '')
        
        # Remove leading dots
        filename = filename.lstrip('.')
        
        # Limit length
        max_length = 255
        if len(filename) > max_length:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            if ext:
                max_name_length = max_length - len(ext) - 1
                filename = f"{name[:max_name_length]}.{ext}"
            else:
                filename = filename[:max_length]
        
        return filename
    
    @staticmethod
    def sanitize_html(html: str) -> str:
        """Basic HTML sanitization (remove script tags)"""
        # Remove script tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove event handlers
        html = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
        
        return html


async def validation_middleware(request: Request, call_next):
    """
    Middleware to validate request data
    """
    # Skip validation for certain paths
    skip_paths = ["/health", "/api/docs", "/api/redoc", "/openapi.json"]
    if request.url.path in skip_paths:
        return await call_next(request)
    
    # Validate content type for POST/PUT/PATCH requests
    if request.method in ["POST", "PUT", "PATCH"]:
        content_type = request.headers.get("content-type", "")
        
        if not content_type:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Content-Type header is required"}
            )
        
        # Check for JSON content type
        if request.url.path.startswith("/api/") and "application/json" not in content_type:
            # Allow multipart/form-data for file uploads
            if "multipart/form-data" not in content_type:
                return JSONResponse(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    content={"detail": "Content-Type must be application/json"}
                )
    
    # Validate request size
    max_body_size = 10 * 1024 * 1024  # 10MB
    if request.headers.get("content-length"):
        content_length = int(request.headers["content-length"])
        if content_length > max_body_size:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request body too large. Maximum size is {max_body_size} bytes"}
            )
    
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response


# Custom validators for specific data types
class NetworkConfigValidator:
    """Validator for network configuration data"""
    
    @staticmethod
    def validate_vlan_id(vlan_id: int) -> bool:
        """Validate VLAN ID (1-4094)"""
        return 1 <= vlan_id <= 4094
    
    @staticmethod
    def validate_mtu(mtu: int) -> bool:
        """Validate MTU size (68-9000 for most networks)"""
        return 68 <= mtu <= 9000
    
    @staticmethod
    def validate_subnet_mask(mask: str) -> bool:
        """Validate subnet mask"""
        try:
            # Convert to CIDR to validate
            addr = ipaddress.IPv4Network(f"0.0.0.0/{mask}", strict=False)
            return True
        except (ValueError, ipaddress.AddressValueError):
            return False


class BackupConfigValidator:
    """Validator for backup configuration"""
    
    @staticmethod
    def validate_retention_days(days: int) -> bool:
        """Validate retention period"""
        return 1 <= days <= 3650  # 1 day to 10 years
    
    @staticmethod
    def validate_backup_path(path: str) -> bool:
        """Validate backup path (no traversal)"""
        # Check for path traversal attempts
        if '..' in path or path.startswith('/'):
            return False
        
        # Check for valid characters
        valid_chars = re.compile(r'^[a-zA-Z0-9_\-/]+$')
        return bool(valid_chars.match(path))


# Validation decorators for endpoints
def validate_request(validator_func: Callable) -> Callable:
    """
    Decorator to validate request data
    
    Usage:
        @router.post("/endpoint")
        @validate_request(validate_user_data)
        async def endpoint(data: UserData):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Extract request data
            for arg in args:
                if isinstance(arg, BaseModel):
                    # Validate using provided validator
                    validation_result = validator_func(arg)
                    if not validation_result.get("valid", True):
                        raise ValidationError(validation_result.get("errors", []))
            
            return await func(*args, **kwargs)
        
        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        
        return wrapper
    return decorator


# Example usage validators
def validate_user_registration(data: BaseModel) -> Dict[str, Any]:
    """Validate user registration data"""
    errors = []
    
    if hasattr(data, 'username') and not DataValidator.validate_username(data.username):
        errors.append({
            "field": "username",
            "message": "Username must be 3-32 characters and contain only letters, numbers, underscores, or dashes"
        })
    
    if hasattr(data, 'email') and not DataValidator.validate_email(data.email):
        errors.append({
            "field": "email",
            "message": "Invalid email format"
        })
    
    if hasattr(data, 'password'):
        password_validation = DataValidator.validate_password(data.password)
        if not password_validation["valid"]:
            errors.append({
                "field": "password",
                "message": "; ".join(password_validation["errors"])
            })
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def validate_network_scan(data: BaseModel) -> Dict[str, Any]:
    """Validate network scan request"""
    errors = []
    
    if hasattr(data, 'target'):
        # Validate IP or CIDR
        if not DataValidator.validate_ip_address(data.target) and not DataValidator.validate_cidr(data.target):
            errors.append({
                "field": "target",
                "message": "Target must be a valid IP address or CIDR notation"
            })
    
    if hasattr(data, 'ports') and data.ports:
        for port in data.ports:
            if not DataValidator.validate_port(port):
                errors.append({
                    "field": "ports",
                    "message": f"Invalid port number: {port}"
                })
                break
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }