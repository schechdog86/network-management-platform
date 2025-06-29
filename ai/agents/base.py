"""
Base Agent Class for Network Management
"""

from typing import Any, Dict, List, Optional, Type, Union
from abc import ABC, abstractmethod
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.tools import BaseTool
import logging

from ..config import ai_config, get_llm_config

logger = logging.getLogger(__name__)


class BaseNetworkAgent(ABC):
    """Base class for all network management agents"""
    
    def __init__(
        self,
        name: str,
        description: str,
        tools: List[BaseTool],
        llm: Optional[Any] = None,
        memory_type: str = "buffer",
        verbose: bool = True
    ):
        self.name = name
        self.description = description
        self.tools = tools
        self.verbose = verbose
        
        # Initialize LLM
        self.llm = llm or self._create_llm()
        
        # Initialize memory
        self.memory = self._create_memory(memory_type)
        
        # Create prompt
        self.prompt = self._create_prompt()
        
        # Create agent
        self.agent = self._create_agent()
        
        # Create executor
        self.executor = self._create_executor()
    
    def _create_llm(self) -> Any:
        """Create LLM instance based on configuration"""
        llm_config = get_llm_config()
        
        if ai_config.llm_provider == "openai":
            return ChatOpenAI(**llm_config)
        elif ai_config.llm_provider == "anthropic":
            return ChatAnthropic(**llm_config)
        else:
            # Local model or custom implementation
            raise NotImplementedError(f"Provider {ai_config.llm_provider} not implemented")
    
    def _create_memory(self, memory_type: str) -> Any:
        """Create memory instance"""
        memory_key = ai_config.memory_key
        
        if memory_type == "buffer":
            return ConversationBufferMemory(
                memory_key=memory_key,
                return_messages=True
            )
        elif memory_type == "summary":
            return ConversationSummaryMemory(
                llm=self.llm,
                memory_key=memory_key,
                return_messages=True,
                max_token_limit=ai_config.max_memory_tokens
            )
        else:
            return ConversationBufferMemory(
                memory_key=memory_key,
                return_messages=True
            )
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """Create agent prompt template"""
        system_message = self._get_system_message()
        
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name=ai_config.memory_key),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
    
    @abstractmethod
    def _get_system_message(self) -> str:
        """Get system message for the agent"""
        pass
    
    def _create_agent(self) -> Any:
        """Create the agent"""
        return create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
    
    def _create_executor(self) -> AgentExecutor:
        """Create agent executor"""
        return AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=self.verbose,
            max_iterations=10,
            max_execution_time=300,  # 5 minutes
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
    
    def run(self, input_text: str) -> Dict[str, Any]:
        """Run the agent with input"""
        try:
            # Log the input
            logger.info(f"{self.name} received input: {input_text}")
            
            # Execute agent
            result = self.executor.invoke({"input": input_text})
            
            # Log successful execution
            logger.info(f"{self.name} completed successfully")
            
            return {
                "success": True,
                "output": result.get("output", ""),
                "intermediate_steps": result.get("intermediate_steps", [])
            }
            
        except Exception as e:
            logger.error(f"{self.name} error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "output": f"I encountered an error: {str(e)}"
            }
    
    async def arun(self, input_text: str) -> Dict[str, Any]:
        """Run the agent asynchronously"""
        try:
            # Log the input
            logger.info(f"{self.name} received async input: {input_text}")
            
            # Execute agent
            result = await self.executor.ainvoke({"input": input_text})
            
            # Log successful execution
            logger.info(f"{self.name} completed successfully (async)")
            
            return {
                "success": True,
                "output": result.get("output", ""),
                "intermediate_steps": result.get("intermediate_steps", [])
            }
            
        except Exception as e:
            logger.error(f"{self.name} async error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "output": f"I encountered an error: {str(e)}"
            }
    
    def clear_memory(self):
        """Clear conversation memory"""
        self.memory.clear()
        logger.info(f"{self.name} memory cleared")
    
    def save_memory(self, filepath: str):
        """Save memory to file"""
        try:
            import json
            memory_data = {
                "agent": self.name,
                "messages": [
                    {
                        "type": msg.type,
                        "content": msg.content
                    }
                    for msg in self.memory.chat_memory.messages
                ]
            }
            
            with open(filepath, 'w') as f:
                json.dump(memory_data, f, indent=2)
                
            logger.info(f"{self.name} memory saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save memory: {str(e)}")
    
    def load_memory(self, filepath: str):
        """Load memory from file"""
        try:
            import json
            from langchain.schema import HumanMessage, AIMessage
            
            with open(filepath, 'r') as f:
                memory_data = json.load(f)
            
            # Clear existing memory
            self.memory.clear()
            
            # Restore messages
            for msg in memory_data.get("messages", []):
                if msg["type"] == "human":
                    self.memory.chat_memory.add_user_message(msg["content"])
                elif msg["type"] == "ai":
                    self.memory.chat_memory.add_ai_message(msg["content"])
                    
            logger.info(f"{self.name} memory loaded from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load memory: {str(e)}")
    
    def get_tool_names(self) -> List[str]:
        """Get list of available tool names"""
        return [tool.name for tool in self.tools]
    
    def add_tool(self, tool: BaseTool):
        """Add a new tool to the agent"""
        self.tools.append(tool)
        # Recreate agent and executor with new tools
        self.agent = self._create_agent()
        self.executor = self._create_executor()
        logger.info(f"Added tool '{tool.name}' to {self.name}")
    
    def remove_tool(self, tool_name: str):
        """Remove a tool from the agent"""
        self.tools = [t for t in self.tools if t.name != tool_name]
        # Recreate agent and executor without removed tool
        self.agent = self._create_agent()
        self.executor = self._create_executor()
        logger.info(f"Removed tool '{tool_name}' from {self.name}")


class SpecializedAgent(BaseNetworkAgent):
    """Base class for specialized agents with role-specific capabilities"""
    
    def __init__(
        self,
        name: str,
        description: str,
        role: str,
        tools: List[BaseTool],
        capabilities: List[str],
        **kwargs
    ):
        self.role = role
        self.capabilities = capabilities
        super().__init__(name, description, tools, **kwargs)
    
    def _get_base_system_message(self) -> str:
        """Get base system message that can be extended by subclasses"""
        return f"""You are {self.name}, a specialized {self.role} for network management systems.

Your capabilities include:
{chr(10).join(f"- {cap}" for cap in self.capabilities)}

Always:
1. Provide clear, actionable responses
2. Use available tools to gather information before making recommendations
3. Explain your reasoning when making decisions
4. Alert on any potential risks or issues
5. Follow security best practices

Available tools: {', '.join(self.get_tool_names())}
"""