"""
AI Configuration Module
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class AIConfig:
    """AI Configuration settings"""
    
    # LLM Settings
    llm_provider: str = "openai"  # openai, anthropic, local
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 2000
    
    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Vector Store Settings
    vector_store_type: str = "chroma"  # chroma, faiss
    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Memory Settings
    memory_type: str = "conversation_buffer"  # conversation_buffer, conversation_summary
    memory_key: str = "chat_history"
    max_memory_tokens: int = 4000
    
    # Tool Settings
    enable_ssh_tools: bool = True
    enable_snmp_tools: bool = True
    enable_monitoring_tools: bool = True
    enable_backup_tools: bool = True
    
    # Security Settings
    require_confirmation: bool = True  # Require confirmation for destructive actions
    allowed_commands: list = None
    blocked_commands: list = None
    
    # Performance Settings
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour
    max_concurrent_operations: int = 5
    
    def __post_init__(self):
        # Load API keys from environment
        self.openai_api_key = self.openai_api_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = self.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        
        # Default allowed commands
        if self.allowed_commands is None:
            self.allowed_commands = [
                "status", "list", "show", "get", "describe",
                "monitor", "check", "verify", "test", "ping"
            ]
            
        # Default blocked commands
        if self.blocked_commands is None:
            self.blocked_commands = [
                "rm -rf", "format", "dd", "kill -9", "shutdown",
                "reboot", "halt", "poweroff"
            ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "llm_provider": self.llm_provider,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "vector_store_type": self.vector_store_type,
            "embedding_model": self.embedding_model,
            "memory_type": self.memory_type,
            "enable_ssh_tools": self.enable_ssh_tools,
            "enable_snmp_tools": self.enable_snmp_tools,
            "enable_monitoring_tools": self.enable_monitoring_tools,
            "enable_backup_tools": self.enable_backup_tools,
            "require_confirmation": self.require_confirmation,
            "cache_enabled": self.cache_enabled,
            "max_concurrent_operations": self.max_concurrent_operations
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'AIConfig':
        """Create config from dictionary"""
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})


# Global configuration instance
ai_config = AIConfig()


def get_llm_config() -> Dict[str, Any]:
    """Get LLM configuration for LangChain"""
    if ai_config.llm_provider == "openai":
        return {
            "model_name": ai_config.model_name,
            "temperature": ai_config.temperature,
            "max_tokens": ai_config.max_tokens,
            "openai_api_key": ai_config.openai_api_key
        }
    elif ai_config.llm_provider == "anthropic":
        return {
            "model": ai_config.model_name,
            "temperature": ai_config.temperature,
            "max_tokens_to_sample": ai_config.max_tokens,
            "anthropic_api_key": ai_config.anthropic_api_key
        }
    else:
        # Local model configuration
        return {
            "model_name": ai_config.model_name,
            "temperature": ai_config.temperature,
            "max_tokens": ai_config.max_tokens
        }


def get_embedding_config() -> Dict[str, Any]:
    """Get embedding configuration"""
    return {
        "model_name": ai_config.embedding_model,
        "encode_kwargs": {"normalize_embeddings": True}
    }


def validate_command(command: str) -> bool:
    """Validate if a command is allowed"""
    # Check blocked commands
    for blocked in ai_config.blocked_commands:
        if blocked in command.lower():
            return False
    
    # Check if command starts with allowed verb
    command_parts = command.strip().split()
    if command_parts:
        verb = command_parts[0].lower()
        if verb not in ai_config.allowed_commands:
            return ai_config.require_confirmation
    
    return True