"""
System Analyst Agent
"""

from typing import List, Optional, Dict, Any
from langchain.tools import BaseTool

from .base import SpecializedAgent
from ..tools import (
    SystemInfoTool,
    ProcessListTool,
    LogAnalysisTool,
    ResourceMonitorTool,
    MetricsQueryTool,
    PerformanceAnalysisTool
)


class SystemAnalystAgent(SpecializedAgent):
    """Agent specialized in system analysis and performance optimization"""
    
    def __init__(self, additional_tools: Optional[List[BaseTool]] = None, **kwargs):
        # Define core tools
        core_tools = [
            SystemInfoTool(),
            ProcessListTool(),
            LogAnalysisTool(),
            ResourceMonitorTool(),
            MetricsQueryTool(),
            PerformanceAnalysisTool()
        ]
        
        # Add any additional tools
        if additional_tools:
            core_tools.extend(additional_tools)
        
        # Define capabilities
        capabilities = [
            "System performance analysis and optimization",
            "Resource utilization monitoring",
            "Process and service analysis",
            "Log analysis and error detection",
            "Trend analysis and capacity planning",
            "Performance bottleneck identification"
        ]
        
        super().__init__(
            name="System Analyst Agent",
            description="Specialized agent for system analysis and performance optimization",
            role="System Analyst",
            tools=core_tools,
            capabilities=capabilities,
            **kwargs
        )
    
    def _get_system_message(self) -> str:
        """Get specialized system message for system analyst"""
        base_message = self._get_base_system_message()
        
        specialized_message = f"""{base_message}

As a System Analyst, you specialize in:
- Analyzing system performance and resource utilization
- Identifying bottlenecks and optimization opportunities
- Performing root cause analysis for system issues
- Capacity planning and trend analysis
- Log analysis and error pattern detection

When analyzing systems:
1. Gather comprehensive metrics before making conclusions
2. Look for patterns and correlations in the data
3. Consider both immediate and historical context
4. Provide data-driven recommendations
5. Prioritize findings by business impact

Analysis methodology:
- Start with high-level system overview
- Drill down into specific problem areas
- Correlate metrics across different subsystems
- Validate findings with multiple data sources
- Document analysis methodology and assumptions

Always provide actionable insights with clear next steps."""
        
        return specialized_message
    
    def analyze_system_performance(self, target: str, time_range: str = "24h") -> Dict[str, Any]:
        """Perform comprehensive system performance analysis"""
        analysis_prompt = f"""Please perform a comprehensive performance analysis for {target} over the last {time_range}.
        
        Analyze:
        1. CPU utilization patterns and trends
        2. Memory usage and potential leaks
        3. Disk I/O performance and bottlenecks
        4. Network throughput and latency
        5. Process resource consumption
        6. System errors and warnings in logs
        
        Provide:
        - Executive summary of system health
        - Identified performance issues
        - Root cause analysis for any problems
        - Prioritized optimization recommendations
        - Capacity planning insights"""
        
        return self.run(analysis_prompt)
    
    def investigate_issue(self, symptom: str, target: Optional[str] = None) -> Dict[str, Any]:
        """Investigate specific system issue"""
        investigation_prompt = f"""Please investigate the following issue: {symptom}
        {f'on system {target}' if target else ''}
        
        Investigation steps:
        1. Gather relevant system metrics
        2. Analyze recent logs for errors or warnings
        3. Check resource utilization at the time of issue
        4. Identify any abnormal process behavior
        5. Look for correlating events
        
        Provide:
        - Root cause analysis
        - Evidence supporting conclusions
        - Immediate remediation steps
        - Long-term prevention recommendations"""
        
        return self.run(investigation_prompt)
    
    def capacity_planning(self, target: str, projection_period: str = "90d") -> Dict[str, Any]:
        """Perform capacity planning analysis"""
        capacity_prompt = f"""Please perform capacity planning analysis for {target} with a {projection_period} projection.
        
        Analyze:
        1. Historical resource utilization trends
        2. Growth patterns for CPU, memory, disk, and network
        3. Peak usage patterns and seasonality
        4. Current capacity constraints
        5. Projected resource exhaustion dates
        
        Provide:
        - Current capacity utilization summary
        - Projected resource needs
        - Risk assessment for capacity constraints
        - Recommended upgrade timeline
        - Cost optimization opportunities"""
        
        return self.run(capacity_prompt)
    
    def analyze_logs(self, log_source: str, issue_type: Optional[str] = None, time_range: str = "1h") -> Dict[str, Any]:
        """Perform detailed log analysis"""
        log_prompt = f"""Please analyze logs from {log_source} for the last {time_range}.
        {f'Focus on {issue_type} issues.' if issue_type else ''}
        
        Analysis should include:
        1. Error and warning frequency
        2. Error patterns and clusters
        3. Unusual or suspicious activities
        4. Performance-related log entries
        5. Security-relevant events
        
        Provide:
        - Summary of critical findings
        - Categorized list of issues
        - Timeline of significant events
        - Recommendations for each issue type
        - Suggested monitoring improvements"""
        
        return self.run(log_prompt)
    
    def benchmark_performance(self, target: str, baseline: Optional[str] = None) -> Dict[str, Any]:
        """Benchmark system performance against baseline"""
        benchmark_prompt = f"""Please benchmark the performance of {target}
        {f'against baseline {baseline}' if baseline else 'and establish performance baseline'}.
        
        Benchmark areas:
        1. CPU performance metrics
        2. Memory throughput and latency
        3. Disk I/O operations and throughput
        4. Network bandwidth and latency
        5. Application response times
        
        Provide:
        - Performance metrics summary
        - Comparison with baseline or industry standards
        - Performance grade/score
        - Areas exceeding or below expectations
        - Optimization recommendations for underperforming areas"""
        
        return self.run(benchmark_prompt)