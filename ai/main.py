"""
Main AI Integration Module
"""

from typing import Dict, Any, Optional, List
import asyncio
from enum import Enum

from .agents import (
    NetworkAdminAgent,
    SystemAnalystAgent,
    SecurityMonitorAgent,
    MaintenanceAgent
)
from .agents.predictive_maintenance import PredictiveMaintenanceAgent
from .config import ai_config


class AgentType(Enum):
    """Available agent types"""
    NETWORK_ADMIN = "network_admin"
    SYSTEM_ANALYST = "system_analyst" 
    SECURITY_MONITOR = "security_monitor"
    MAINTENANCE = "maintenance"
    PREDICTIVE_MAINTENANCE = "predictive_maintenance"
    AUTO = "auto"  # Automatically select best agent


class AIOrchestrator:
    """Main orchestrator for AI agents"""
    
    def __init__(self):
        self.agents = self._initialize_agents()
        self.conversation_history = []
        
    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize all available agents"""
        return {
            AgentType.NETWORK_ADMIN: NetworkAdminAgent(),
            AgentType.SYSTEM_ANALYST: SystemAnalystAgent(),
            AgentType.SECURITY_MONITOR: SecurityMonitorAgent(),
            AgentType.MAINTENANCE: MaintenanceAgent(),
            AgentType.PREDICTIVE_MAINTENANCE: PredictiveMaintenanceAgent()
        }
    
    def _select_agent(self, query: str, agent_type: AgentType = AgentType.AUTO) -> Any:
        """Select the appropriate agent for the query"""
        if agent_type != AgentType.AUTO:
            return self.agents[agent_type]
        
        # Simple keyword-based agent selection
        query_lower = query.lower()
        
        # Network admin keywords
        if any(keyword in query_lower for keyword in ['ping', 'network', 'connectivity', 'port', 'scan', 'device']):
            return self.agents[AgentType.NETWORK_ADMIN]
        
        # System analyst keywords
        elif any(keyword in query_lower for keyword in ['performance', 'cpu', 'memory', 'disk', 'analyze', 'trend']):
            return self.agents[AgentType.SYSTEM_ANALYST]
        
        # Security keywords
        elif any(keyword in query_lower for keyword in ['security', 'threat', 'vulnerability', 'audit', 'incident']):
            return self.agents[AgentType.SECURITY_MONITOR]
        
        # Maintenance keywords
        elif any(keyword in query_lower for keyword in ['backup', 'restore', 'maintenance', 'patch', 'update']):
            return self.agents[AgentType.MAINTENANCE]
        
        # Predictive maintenance keywords
        elif any(keyword in query_lower for keyword in ['predict', 'mtbf', 'failure', 'health', 'forecast', 'schedule maintenance']):
            return self.agents[AgentType.PREDICTIVE_MAINTENANCE]
        
        # Default to network admin
        else:
            return self.agents[AgentType.NETWORK_ADMIN]
    
    def process_query(self, query: str, agent_type: AgentType = AgentType.AUTO, 
                      context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a query using the appropriate agent"""
        # Select agent
        agent = self._select_agent(query, agent_type)
        
        # Add context to query if provided
        if context:
            context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            query = f"{query}\n\nContext:\n{context_str}"
        
        # Process query
        result = agent.run(query)
        
        # Store in history
        self.conversation_history.append({
            "query": query,
            "agent": agent.name,
            "result": result
        })
        
        return {
            "agent_used": agent.name,
            "response": result.get("output", ""),
            "success": result.get("success", False),
            "error": result.get("error", None)
        }
    
    async def process_query_async(self, query: str, agent_type: AgentType = AgentType.AUTO,
                                  context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a query asynchronously"""
        # Select agent
        agent = self._select_agent(query, agent_type)
        
        # Add context to query if provided
        if context:
            context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            query = f"{query}\n\nContext:\n{context_str}"
        
        # Process query
        result = await agent.arun(query)
        
        # Store in history
        self.conversation_history.append({
            "query": query,
            "agent": agent.name,
            "result": result
        })
        
        return {
            "agent_used": agent.name,
            "response": result.get("output", ""),
            "success": result.get("success", False),
            "error": result.get("error", None)
        }
    
    def multi_agent_query(self, query: str, agent_types: List[AgentType]) -> Dict[str, Any]:
        """Process query with multiple agents and combine results"""
        results = {}
        
        for agent_type in agent_types:
            agent = self.agents[agent_type]
            result = agent.run(query)
            results[agent.name] = result
        
        # Combine results
        combined_response = self._combine_agent_responses(results)
        
        return {
            "agents_used": [agent.name for agent in self.agents.values() if agent.name in results],
            "individual_responses": results,
            "combined_response": combined_response,
            "success": all(r.get("success", False) for r in results.values())
        }
    
    def _combine_agent_responses(self, results: Dict[str, Any]) -> str:
        """Combine responses from multiple agents"""
        combined = []
        
        for agent_name, result in results.items():
            if result.get("success"):
                combined.append(f"**{agent_name}**:\n{result.get('output', '')}")
        
        return "\n\n---\n\n".join(combined)
    
    def get_agent_capabilities(self, agent_type: AgentType) -> Dict[str, Any]:
        """Get capabilities of a specific agent"""
        agent = self.agents[agent_type]
        
        return {
            "name": agent.name,
            "description": agent.description,
            "role": getattr(agent, 'role', 'Unknown'),
            "capabilities": getattr(agent, 'capabilities', []),
            "tools": agent.get_tool_names()
        }
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        for agent in self.agents.values():
            agent.clear_memory()
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get conversation history"""
        if limit:
            return self.conversation_history[-limit:]
        return self.conversation_history
    
    async def analyze_system_health(self, device_id: str) -> Dict[str, Any]:
        """Analyze system health using predictive maintenance"""
        agent = self.agents[AgentType.PREDICTIVE_MAINTENANCE]
        return await agent.analyze_system_health(device_id)
    
    async def predict_failures(self, device_ids: List[str]) -> Dict[str, Any]:
        """Predict failures for multiple devices"""
        agent = self.agents[AgentType.PREDICTIVE_MAINTENANCE]
        results = {}
        
        for device_id in device_ids:
            results[device_id] = await agent.predict_mtbf(device_id)
        
        return {
            "predictions": results,
            "total_devices": len(device_ids),
            "at_risk": sum(1 for r in results.values() if r.get("mtbf_days", 999) < 30)
        }
    
    async def generate_maintenance_schedule(self, device_ids: List[str]) -> Dict[str, Any]:
        """Generate optimized maintenance schedule"""
        agent = self.agents[AgentType.PREDICTIVE_MAINTENANCE]
        return await agent.generate_maintenance_schedule(device_ids)
    
    async def process_command(self, parsed_command: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Process a parsed command from NLP"""
        intent = parsed_command.get("intent", "")
        entities = parsed_command.get("entities", {})
        
        # Route to appropriate agent based on intent
        if intent == "network_scan":
            agent = self.agents[AgentType.NETWORK_ADMIN]
            query = f"Scan network {entities.get('target', 'local')}"
        elif intent == "system_check":
            agent = self.agents[AgentType.SYSTEM_ANALYST]
            query = f"Check system {entities.get('system', 'all')}"
        elif intent == "security_audit":
            agent = self.agents[AgentType.SECURITY_MONITOR]
            query = f"Run security audit on {entities.get('target', 'all systems')}"
        elif intent == "backup_management":
            agent = self.agents[AgentType.MAINTENANCE]
            query = f"Manage backup for {entities.get('target', 'all systems')}"
        elif intent == "predict_maintenance":
            agent = self.agents[AgentType.PREDICTIVE_MAINTENANCE]
            query = f"Predict maintenance for {entities.get('target', 'all devices')}"
        else:
            # Default to network admin
            agent = self.agents[AgentType.NETWORK_ADMIN]
            query = parsed_command.get("original_text", "")
        
        # Process with selected agent
        result = await agent.arun(query)
        
        return {
            "agent_used": agent.name,
            "intent": intent,
            "entities": entities,
            "result": result.get("output", ""),
            "success": result.get("success", False),
            "error": result.get("error", None)
        }
    
    async def chat(self, message: str, context: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """Process a chat message"""
        # Select best agent based on message content
        agent = self._select_agent(message)
        
        # Build context string
        context_messages = []
        for ctx in context[-5:]:  # Last 5 messages
            role = ctx.get("role", "user")
            content = ctx.get("content", "")
            context_messages.append(f"{role}: {content}")
        
        full_query = f"{message}\n\nConversation context:\n" + "\n".join(context_messages)
        
        # Process with agent
        result = await agent.arun(full_query)
        
        # Extract any learned information
        response = result.get("output", "")
        learned_info = None
        
        # Simple learning extraction (would be more sophisticated in production)
        if "you can" in response.lower() or "this allows" in response.lower():
            learned_info = {
                "category": "capability",
                "title": f"AI Assistant Capability",
                "content": response[:200],
                "tags": ["ai", "assistant", agent.name.lower()]
            }
        
        return {
            "response": response,
            "model": agent.name,
            "tokens": len(response.split()),  # Simple token count
            "sources": [],
            "learned_info": learned_info
        }


# Global orchestrator instance
ai_orchestrator = AIOrchestrator()


# Convenience functions
def ask_ai(query: str, agent_type: str = "auto", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Simple function to ask AI a question"""
    agent_enum = AgentType(agent_type) if agent_type != "auto" else AgentType.AUTO
    return ai_orchestrator.process_query(query, agent_enum, context)


async def ask_ai_async(query: str, agent_type: str = "auto", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Async function to ask AI a question"""
    agent_enum = AgentType(agent_type) if agent_type != "auto" else AgentType.AUTO
    return await ai_orchestrator.process_query_async(query, agent_enum, context)


def get_ai_capabilities() -> Dict[str, Any]:
    """Get capabilities of all AI agents"""
    capabilities = {}
    
    for agent_type in AgentType:
        if agent_type != AgentType.AUTO:
            capabilities[agent_type.value] = ai_orchestrator.get_agent_capabilities(agent_type)
    
    return capabilities