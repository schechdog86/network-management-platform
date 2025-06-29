"""
Configuration management for the desktop application
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG = {
    "api": {
        "base_url": "http://localhost:8000",
        "timeout": 30,
        "verify_ssl": True
    },
    "api_url": "http://localhost:8000",  # For backward compatibility
    "ui": {
        "theme": "default",
        "refresh_interval": 5,
        "notifications_enabled": True
    },
    "network": {
        "scan_interval": 300,
        "max_concurrent_scans": 5,
        "timeout": 10
    },
    "monitoring": {
        "update_interval": 60,
        "retention_days": 30,
        "alert_threshold": 0.8
    },
    "backup": {
        "default_location": "/var/backups/network",
        "compression": True,
        "encryption": True,
        "retention_days": 90
    },
    "ai": {
        "enabled": True,
        "model": "gpt-3.5-turbo",
        "max_tokens": 2000,
        "temperature": 0.7
    }
}

class Config:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        
    def _get_default_config_path(self) -> str:
        """Get the default configuration file path"""
        home = Path.home()
        config_dir = home / ".config" / "network-manager"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "desktop-config.json")
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                    # Merge with defaults
                    return self._merge_configs(DEFAULT_CONFIG, user_config)
            except Exception as e:
                print(f"Error loading config: {e}")
                return DEFAULT_CONFIG.copy()
        else:
            # Create default config
            self.save()
            return DEFAULT_CONFIG.copy()
            
    def _merge_configs(self, default: Dict, user: Dict) -> Dict:
        """Recursively merge user config with defaults"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
        
    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot-separated key"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        
    def save(self) -> None:
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def reload(self) -> None:
        """Reload configuration from file"""
        self.config = self._load_config()

def load_config(config_path: str = None) -> Config:
    """Load configuration instance"""
    return Config(config_path)