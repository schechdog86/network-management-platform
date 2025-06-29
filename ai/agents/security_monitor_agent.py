"""
Security Monitor Agent
"""

from typing import List, Optional, Dict, Any
from langchain.tools import BaseTool

from .base import SpecializedAgent
from ..tools import (
    PortScanTool,
    LogAnalysisTool,
    NetworkScanTool,
    ProcessListTool,
    AlertManagementTool
)


class SecurityMonitorAgent(SpecializedAgent):
    """Agent specialized in security monitoring and threat detection"""
    
    def __init__(self, additional_tools: Optional[List[BaseTool]] = None, **kwargs):
        # Define core tools
        core_tools = [
            PortScanTool(),
            LogAnalysisTool(),
            NetworkScanTool(),
            ProcessListTool(),
            AlertManagementTool()
        ]
        
        # Add any additional tools
        if additional_tools:
            core_tools.extend(additional_tools)
        
        # Define capabilities
        capabilities = [
            "Security threat detection and analysis",
            "Vulnerability scanning and assessment",
            "Intrusion detection and response",
            "Security log analysis and correlation",
            "Compliance monitoring and reporting",
            "Incident response coordination"
        ]
        
        super().__init__(
            name="Security Monitor Agent",
            description="Specialized agent for security monitoring and threat detection",
            role="Security Monitor",
            tools=core_tools,
            capabilities=capabilities,
            **kwargs
        )
    
    def _get_system_message(self) -> str:
        """Get specialized system message for security monitor"""
        base_message = self._get_base_system_message()
        
        specialized_message = f"""{base_message}

As a Security Monitor, you specialize in:
- Detecting and analyzing security threats
- Monitoring for suspicious activities
- Vulnerability assessment and reporting
- Incident detection and response
- Compliance verification
- Security best practices enforcement

Security monitoring approach:
1. Continuous monitoring of security-relevant events
2. Correlation of events across multiple sources
3. Risk-based prioritization of findings
4. Clear documentation of security incidents
5. Actionable remediation recommendations

When detecting threats:
- Gather evidence from multiple sources
- Assess the severity and potential impact
- Determine if immediate action is required
- Document the chain of events
- Provide clear remediation steps

Always maintain confidentiality and follow security protocols.
Report critical security issues immediately with appropriate severity."""
        
        return specialized_message
    
    def security_audit(self, target: str, audit_type: str = "comprehensive") -> Dict[str, Any]:
        """Perform security audit"""
        audit_prompt = f"""Please perform a {audit_type} security audit on {target}.
        
        Audit should include:
        1. Port scan to identify exposed services
        2. Check for vulnerable service versions
        3. Analyze security logs for suspicious activities
        4. Review running processes for anomalies
        5. Check compliance with security policies
        
        Provide:
        - Executive summary of security posture
        - Detailed findings by category
        - Risk assessment for each finding
        - Prioritized remediation plan
        - Compliance status report"""
        
        return self.run(audit_prompt)
    
    def threat_hunt(self, indicators: Optional[List[str]] = None, time_range: str = "24h") -> Dict[str, Any]:
        """Perform proactive threat hunting"""
        threat_prompt = f"""Please perform threat hunting activities for the last {time_range}.
        {f'Look for these indicators: {", ".join(indicators)}' if indicators else 'Look for any suspicious activities.'}
        
        Hunt for:
        1. Unusual network connections or traffic patterns
        2. Suspicious process executions
        3. Abnormal user behavior patterns
        4. Signs of lateral movement
        5. Data exfiltration attempts
        6. Persistence mechanisms
        
        Provide:
        - Summary of hunting results
        - Detected anomalies and their severity
        - Evidence trail for suspicious activities
        - Recommended containment actions
        - Additional indicators to monitor"""
        
        return self.run(threat_prompt)
    
    def investigate_incident(self, incident_description: str, affected_systems: List[str]) -> Dict[str, Any]:
        """Investigate security incident"""
        investigation_prompt = f"""Please investigate the following security incident: {incident_description}
        Affected systems: {', '.join(affected_systems)}
        
        Investigation steps:
        1. Analyze logs around the incident timeframe
        2. Check for indicators of compromise
        3. Identify attack vectors and methods
        4. Determine the scope of compromise
        5. Assess data exposure or loss
        
        Provide:
        - Incident timeline and attack chain
        - Affected systems and data
        - Attack attribution (if possible)
        - Containment recommendations
        - Recovery steps and prevention measures"""
        
        return self.run(investigation_prompt)
    
    def vulnerability_scan(self, target: str, scan_depth: str = "standard") -> Dict[str, Any]:
        """Perform vulnerability scanning"""
        vuln_prompt = f"""Please perform a {scan_depth} vulnerability scan on {target}.
        
        Scan for:
        1. Open ports and exposed services
        2. Known vulnerabilities in running services
        3. Configuration weaknesses
        4. Missing security patches
        5. Default credentials or weak authentication
        
        Provide:
        - Vulnerability summary by severity
        - Detailed findings with CVE references
        - Exploitability assessment
        - Remediation priorities
        - Patch management recommendations"""
        
        return self.run(vuln_prompt)
    
    def compliance_check(self, standard: str, scope: List[str]) -> Dict[str, Any]:
        """Check compliance with security standards"""
        compliance_prompt = f"""Please check compliance with {standard} standard for systems: {', '.join(scope)}.
        
        Verify:
        1. Required security controls are in place
        2. Configuration meets standard requirements
        3. Logging and monitoring compliance
        4. Access control implementation
        5. Data protection measures
        
        Provide:
        - Overall compliance score
        - Detailed findings by control category
        - Non-compliance issues and gaps
        - Remediation requirements
        - Evidence documentation for audit"""
        
        return self.run(compliance_prompt)
    
    def generate_security_report(self, report_type: str = "weekly", recipients: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate security report"""
        report_prompt = f"""Please generate a {report_type} security report.
        
        Include:
        1. Security events summary and statistics
        2. Critical incidents and their resolution
        3. Vulnerability scan results
        4. Compliance status updates
        5. Security metrics and KPIs
        6. Trending threats and risks
        
        Format:
        - Executive summary for management
        - Technical details for security team
        - Metrics and trend analysis
        - Recommendations and action items
        - Upcoming security initiatives"""
        
        return self.run(report_prompt)