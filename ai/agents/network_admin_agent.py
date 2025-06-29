"""
Network Administrator Agent
"""

from typing import List, Optional, Dict, Any
from langchain.tools import BaseTool

from .base import SpecializedAgent
from ..tools import (
    NetworkScanTool,
    DeviceStatusTool,
    PingTool,
    TracerouteTool,
    PortScanTool,
    ServiceManagementTool
)


class NetworkAdminAgent(SpecializedAgent):
    """Agent specialized in network administration tasks"""
    
    def __init__(self, additional_tools: Optional[List[BaseTool]] = None, **kwargs):
        # Define core tools
        core_tools = [
            NetworkScanTool(),
            DeviceStatusTool(),
            PingTool(),
            TracerouteTool(),
            PortScanTool(),
            ServiceManagementTool()
        ]
        
        # Add any additional tools
        if additional_tools:
            core_tools.extend(additional_tools)
        
        # Define capabilities
        capabilities = [
            "Network device discovery and scanning",
            "Connectivity testing and troubleshooting",
            "Service status monitoring and management",
            "Network path analysis and diagnostics",
            "Port scanning and security assessment",
            "Device configuration validation"
        ]
        
        super().__init__(
            name="Network Administrator Agent",
            description="Specialized agent for network administration and troubleshooting",
            role="Network Administrator",
            tools=core_tools,
            capabilities=capabilities,
            **kwargs
        )
    
    def _get_system_message(self) -> str:
        """Get specialized system message for network admin"""
        base_message = self._get_base_system_message()
        
        specialized_message = f"""{base_message}

As a Network Administrator, you specialize in:
- Diagnosing network connectivity issues
- Managing network devices and services  
- Performing security assessments
- Optimizing network performance
- Troubleshooting complex network problems

When handling network issues:
1. Start with basic connectivity tests (ping)
2. Escalate to more detailed diagnostics if needed
3. Check service status on affected devices
4. Verify network paths and routing
5. Document all findings and recommendations

Security considerations:
- Always verify before making changes to production systems
- Follow principle of least privilege
- Document security findings appropriately
- Recommend patches and updates when needed

Remember to be thorough but efficient in your analysis."""
        
        return specialized_message
    
    def diagnose_connectivity(self, source: str, destination: str) -> Dict[str, Any]:
        """Specialized method for connectivity diagnosis"""
        diagnosis_prompt = f"""Please diagnose the network connectivity between {source} and {destination}.
        
        Perform the following checks:
        1. Ping test from source to destination
        2. Traceroute to identify the network path
        3. Check if common ports are accessible
        4. Verify DNS resolution if using hostnames
        5. Check for any service issues on the destination
        
        Provide a comprehensive diagnosis with specific recommendations."""
        
        return self.run(diagnosis_prompt)
    
    def network_health_check(self, network_range: str) -> Dict[str, Any]:
        """Perform comprehensive network health check"""
        health_check_prompt = f"""Please perform a comprehensive health check for network {network_range}.
        
        Include:
        1. Scan for all active devices
        2. Check status of critical services
        3. Identify any devices that are down or unreachable
        4. Check for unusual port activity
        5. Provide overall network health assessment
        
        Summarize findings and highlight any issues requiring attention."""
        
        return self.run(health_check_prompt)
    
    def troubleshoot_service(self, device: str, service: str) -> Dict[str, Any]:
        """Troubleshoot specific service issues"""
        troubleshoot_prompt = f"""Please troubleshoot the {service} service on {device}.
        
        Steps to perform:
        1. Check if the device is reachable
        2. Verify the service status
        3. Check relevant ports for the service
        4. Look for any related issues
        5. Provide specific steps to resolve the issue
        
        Include both immediate fixes and long-term recommendations."""
        
        return self.run(troubleshoot_prompt)
    
    def security_scan(self, target: str) -> Dict[str, Any]:
        """Perform security-focused network scan"""
        security_prompt = f"""Please perform a security assessment scan on {target}.
        
        Focus on:
        1. Open ports and services
        2. Potentially vulnerable services
        3. Unusual or unexpected services
        4. Compliance with security best practices
        5. Recommendations for hardening
        
        Provide a risk assessment and prioritized recommendations."""
        
        return self.run(security_prompt)