# AI Integration Module

This module provides LangChain-based AI capabilities for intelligent network management and automation.

## Features

### AI Agents

1. **Network Administrator Agent**
   - Network device discovery and scanning
   - Connectivity testing and troubleshooting
   - Service status monitoring
   - Port scanning and security assessment

2. **System Analyst Agent**
   - Performance analysis and optimization
   - Resource utilization monitoring
   - Log analysis and error detection
   - Capacity planning and trend analysis

3. **Security Monitor Agent**
   - Threat detection and analysis
   - Vulnerability scanning
   - Security log correlation
   - Compliance monitoring

4. **Maintenance Agent**
   - Backup planning and execution
   - Predictive maintenance
   - Disaster recovery coordination
   - Patch management

### Tools

Each agent has access to specialized tools:

- **Network Tools**: NetworkScan, DeviceStatus, Ping, Traceroute, PortScan
- **System Tools**: SystemInfo, ProcessList, ServiceManagement, LogAnalysis, ResourceMonitor
- **Backup Tools**: BackupStatus, CreateBackup, RestoreBackup, BackupHistory
- **Monitoring Tools**: MetricsQuery, AlertManagement, PerformanceAnalysis, PredictiveMaintenance

## Installation

```bash
pip install -r ai/requirements.txt
```

## Configuration

Set up environment variables:

```bash
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
```

Or create a `.env` file with the configuration.

## Usage

### Basic Usage

```python
from ai.main import ask_ai

# Ask a general question (auto-selects agent)
response = ask_ai("Check the status of server-01")
print(response['response'])

# Use specific agent
response = ask_ai(
    "Analyze CPU performance for the last 24 hours",
    agent_type="system_analyst"
)
```

### Async Usage

```python
import asyncio
from ai.main import ask_ai_async

async def main():
    response = await ask_ai_async("Scan network 192.168.1.0/24")
    print(response['response'])

asyncio.run(main())
```

### Direct Agent Usage

```python
from ai.agents import NetworkAdminAgent

# Create agent
agent = NetworkAdminAgent()

# Use specialized methods
result = agent.diagnose_connectivity("server-01", "database-01")
print(result['output'])

# Or use general query
result = agent.run("What services are running on server-01?")
print(result['output'])
```

### Multi-Agent Query

```python
from ai.main import ai_orchestrator, AgentType

# Query multiple agents
result = ai_orchestrator.multi_agent_query(
    "Investigate high CPU usage on server-01",
    agent_types=[AgentType.SYSTEM_ANALYST, AgentType.SECURITY_MONITOR]
)

print(result['combined_response'])
```

## API Integration

### FastAPI Example

```python
from fastapi import FastAPI
from ai.main import ask_ai_async

app = FastAPI()

@app.post("/api/ai/query")
async def ai_query(query: str, agent_type: str = "auto"):
    result = await ask_ai_async(query, agent_type)
    return result
```

### WebSocket Integration

```python
from fastapi import WebSocket
from ai.main import ai_orchestrator, AgentType

@app.websocket("/ws/ai")
async def websocket_ai(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        data = await websocket.receive_json()
        query = data.get("query")
        agent_type = data.get("agent_type", "auto")
        
        result = await ai_orchestrator.process_query_async(
            query, 
            AgentType(agent_type)
        )
        
        await websocket.send_json(result)
```

## Desktop Integration

### Qt/PySide6 Integration

```python
from PySide6.QtCore import QThread, Signal
from ai.main import ask_ai

class AIWorker(QThread):
    result_ready = Signal(dict)
    
    def __init__(self, query, agent_type="auto"):
        super().__init__()
        self.query = query
        self.agent_type = agent_type
    
    def run(self):
        result = ask_ai(self.query, self.agent_type)
        self.result_ready.emit(result)

# In your Qt widget
def on_ai_query(self):
    query = self.input_field.text()
    self.worker = AIWorker(query)
    self.worker.result_ready.connect(self.on_ai_response)
    self.worker.start()

def on_ai_response(self, result):
    self.output_field.setText(result['response'])
```

## Advanced Features

### Custom Tools

```python
from langchain.tools import BaseTool
from ai.agents import NetworkAdminAgent

class CustomNetworkTool(BaseTool):
    name = "custom_network_tool"
    description = "Custom tool for special network operations"
    
    def _run(self, query: str) -> str:
        # Custom implementation
        return "Custom result"

# Add to agent
agent = NetworkAdminAgent()
agent.add_tool(CustomNetworkTool())
```

### Memory Management

```python
# Save conversation memory
agent.save_memory("/path/to/memory.json")

# Load previous conversation
agent.load_memory("/path/to/memory.json")

# Clear memory
agent.clear_memory()
```

### Configuration Options

```python
from ai.config import ai_config

# Modify configuration
ai_config.temperature = 0.5
ai_config.max_tokens = 3000
ai_config.enable_ssh_tools = True
```

## Security Considerations

1. **API Key Security**: Never commit API keys to version control
2. **Command Validation**: The system validates commands before execution
3. **Confirmation Required**: Destructive operations require confirmation
4. **Audit Logging**: All AI interactions are logged
5. **Access Control**: Integrate with your authentication system

## Performance Tips

1. **Use Async Operations**: For better performance in web applications
2. **Cache Results**: Enable caching for frequently accessed data
3. **Batch Operations**: Use multi-agent queries when appropriate
4. **Tool Selection**: Use specific agents instead of auto-selection when possible

## Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure environment variables are set correctly
2. **Tool Execution Errors**: Check system permissions for tools
3. **Memory Issues**: Clear memory if conversations become too long
4. **Performance**: Adjust max_tokens and temperature settings

### Debug Mode

```python
# Enable verbose logging
agent = NetworkAdminAgent(verbose=True)

# Check agent tools
print(agent.get_tool_names())

# View conversation history
history = ai_orchestrator.get_history()
```

## Future Enhancements

- [ ] Support for more LLM providers (Ollama, Hugging Face)
- [ ] Custom agent creation interface
- [ ] Enhanced tool authentication
- [ ] Workflow automation capabilities
- [ ] Integration with more monitoring systems
- [ ] Advanced prompt engineering
- [ ] Multi-modal capabilities (charts, diagrams)