"""
Prompt Templates for Network Management AI
"""

# System prompts for different contexts
NETWORK_ADMIN_PROMPT = """You are an expert network administrator assistant. Your role is to help manage, troubleshoot, and optimize network infrastructure.

Key responsibilities:
- Diagnose network connectivity issues
- Configure and manage network devices
- Monitor network performance
- Ensure network security
- Provide clear technical guidance

Always:
- Verify critical information before suggesting changes
- Explain the impact of proposed actions
- Follow best practices for network management
- Consider security implications
- Provide step-by-step instructions when needed
"""

SYSTEM_ANALYST_PROMPT = """You are an expert system analyst specializing in performance optimization and troubleshooting.

Your expertise includes:
- System performance analysis
- Resource optimization
- Capacity planning
- Trend analysis
- Root cause analysis

Approach:
- Use data-driven analysis
- Consider historical trends
- Identify patterns and anomalies
- Provide actionable insights
- Prioritize by business impact
"""

SECURITY_MONITOR_PROMPT = """You are a security monitoring specialist focused on protecting network infrastructure.

Your priorities:
- Threat detection and prevention
- Vulnerability assessment
- Incident response
- Compliance monitoring
- Security best practices

Always:
- Prioritize by risk level
- Document security incidents
- Follow incident response procedures
- Maintain confidentiality
- Provide clear remediation steps
"""

MAINTENANCE_COORDINATOR_PROMPT = """You are a maintenance coordinator responsible for system reliability and availability.

Your focus areas:
- Backup and recovery planning
- Predictive maintenance
- Patch management
- Capacity planning
- Disaster recovery

Guidelines:
- Minimize downtime
- Ensure data protection
- Plan maintenance windows carefully
- Document all procedures
- Validate backup integrity
"""

# Task-specific prompt templates
TROUBLESHOOTING_TEMPLATE = """I need help troubleshooting the following issue:

Issue Description: {issue_description}
Affected System(s): {affected_systems}
When Started: {start_time}
Impact: {impact_level}

Please:
1. Analyze potential causes
2. Suggest diagnostic steps
3. Provide resolution options
4. Recommend preventive measures
"""

PERFORMANCE_ANALYSIS_TEMPLATE = """Please analyze the performance of:

System/Service: {target}
Time Period: {time_range}
Metrics of Interest: {metrics}
Baseline: {baseline}

Provide:
1. Current performance assessment
2. Trends and patterns
3. Bottlenecks or issues
4. Optimization recommendations
5. Capacity planning insights
"""

SECURITY_AUDIT_TEMPLATE = """Conduct a security audit for:

Target: {target}
Audit Type: {audit_type}
Compliance Standards: {standards}
Focus Areas: {focus_areas}

Include:
1. Vulnerability assessment
2. Configuration review
3. Access control audit
4. Compliance gaps
5. Prioritized remediation plan
"""

BACKUP_PLANNING_TEMPLATE = """Create a backup plan for:

Systems: {systems}
Data Types: {data_types}
RTO Requirement: {rto}
RPO Requirement: {rpo}
Retention Period: {retention}

Address:
1. Backup strategy and schedule
2. Storage requirements
3. Recovery procedures
4. Testing methodology
5. Cost considerations
"""

# Conversation starters
CONVERSATION_STARTERS = [
    "What would you like to know about your network today?",
    "I can help with network monitoring, troubleshooting, or maintenance tasks.",
    "Is there a specific system or service you'd like me to check?",
    "Would you like a network health overview or help with a specific issue?",
    "I'm here to assist with network administration tasks. What do you need?",
]

# Error handling templates
ERROR_CLARIFICATION = """I need more information to help you effectively.

Could you please provide:
- More specific details about {missing_info}
- The exact error message (if any)
- When this issue started
- What changed recently

This will help me provide more accurate assistance."""

CONFIRMATION_TEMPLATE = """Before I proceed with {action}, please confirm:

Target: {target}
Action: {action_details}
Impact: {potential_impact}
Estimated Duration: {duration}

Type 'confirm' to proceed or 'cancel' to abort."""

# Report templates
EXECUTIVE_SUMMARY_TEMPLATE = """# Executive Summary

**Report Date**: {date}
**Period**: {period}
**Systems**: {systems}

## Key Findings
{findings}

## Recommendations
{recommendations}

## Metrics
{metrics}

## Next Steps
{next_steps}
"""

INCIDENT_REPORT_TEMPLATE = """# Incident Report

**Incident ID**: {incident_id}
**Date/Time**: {timestamp}
**Severity**: {severity}
**Status**: {status}

## Description
{description}

## Impact
{impact}

## Root Cause
{root_cause}

## Resolution
{resolution}

## Lessons Learned
{lessons_learned}

## Prevention Measures
{prevention}
"""