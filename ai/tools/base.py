"""
Base Tool Classes for LangChain Integration
"""

from typing import Any, Dict, Optional, Type, Union
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun
import asyncio
import logging

logger = logging.getLogger(__name__)


class BaseNetworkTool(BaseTool, ABC):
    """Base class for all network management tools"""
    
    # Tool metadata
    return_direct: bool = False
    
    def _run(
        self,
        *args,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs
    ) -> Any:
        """Run the tool synchronously"""
        try:
            result = self._execute(*args, **kwargs)
            return self._format_output(result)
        except Exception as e:
            logger.error(f"Error in {self.name}: {str(e)}")
            return f"Error: {str(e)}"
    
    async def _arun(
        self,
        *args,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs
    ) -> Any:
        """Run the tool asynchronously"""
        try:
            result = await self._aexecute(*args, **kwargs)
            return self._format_output(result)
        except Exception as e:
            logger.error(f"Error in {self.name}: {str(e)}")
            return f"Error: {str(e)}"
    
    @abstractmethod
    def _execute(self, *args, **kwargs) -> Any:
        """Execute the tool logic synchronously"""
        pass
    
    async def _aexecute(self, *args, **kwargs) -> Any:
        """Execute the tool logic asynchronously"""
        # Default implementation runs sync version in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._execute, *args, **kwargs)
    
    def _format_output(self, result: Any) -> str:
        """Format the tool output"""
        if isinstance(result, dict):
            return self._format_dict(result)
        elif isinstance(result, list):
            return self._format_list(result)
        else:
            return str(result)
    
    def _format_dict(self, data: Dict[str, Any], indent: int = 0) -> str:
        """Format dictionary output"""
        lines = []
        indent_str = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{indent_str}{key}:")
                lines.append(self._format_dict(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{indent_str}{key}:")
                lines.append(self._format_list(value, indent + 1))
            else:
                lines.append(f"{indent_str}{key}: {value}")
        
        return "\n".join(lines)
    
    def _format_list(self, data: list, indent: int = 0) -> str:
        """Format list output"""
        lines = []
        indent_str = "  " * indent
        
        for i, item in enumerate(data):
            if isinstance(item, dict):
                lines.append(f"{indent_str}- Item {i + 1}:")
                lines.append(self._format_dict(item, indent + 1))
            else:
                lines.append(f"{indent_str}- {item}")
        
        return "\n".join(lines)


class NetworkToolInput(BaseModel):
    """Base input model for network tools"""
    target: Optional[str] = Field(None, description="Target device or network")
    timeout: Optional[int] = Field(30, description="Operation timeout in seconds")


class RequiresConfirmationMixin:
    """Mixin for tools that require confirmation"""
    
    requires_confirmation: bool = True
    confirmation_prompt: str = "This action may affect system operation. Proceed?"
    
    def get_confirmation(self, action: str) -> bool:
        """Get user confirmation for action"""
        # In production, this would integrate with the UI
        # For now, we'll assume confirmation is given
        logger.info(f"Confirmation required for: {action}")
        return True


class CachedToolMixin:
    """Mixin for tools with caching capability"""
    
    cache_enabled: bool = True
    cache_ttl: int = 300  # 5 minutes
    _cache: Dict[str, Any] = {}
    
    def get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result if available"""
        if not self.cache_enabled:
            return None
        
        if key in self._cache:
            result, timestamp = self._cache[key]
            import time
            if time.time() - timestamp < self.cache_ttl:
                return result
            else:
                del self._cache[key]
        
        return None
    
    def cache_result(self, key: str, result: Any) -> None:
        """Cache a result"""
        if self.cache_enabled:
            import time
            self._cache[key] = (result, time.time())


class AsyncToolMixin:
    """Mixin for async-first tools"""
    
    async def gather_results(self, *coroutines) -> list:
        """Gather results from multiple async operations"""
        return await asyncio.gather(*coroutines, return_exceptions=True)
    
    async def run_with_timeout(self, coro, timeout: int):
        """Run coroutine with timeout"""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": f"Operation timed out after {timeout} seconds"}