"""
Maintenance Agent
"""

from typing import List, Optional, Dict, Any
from langchain.tools import BaseTool

from .base import SpecializedAgent
from ..tools import (
    BackupStatusTool,
    CreateBackupTool,
    RestoreBackupTool,
    BackupHistoryTool,
    PredictiveMaintenanceTool,
    SystemInfoTool,
    ServiceManagementTool
)


class MaintenanceAgent(SpecializedAgent):
    """Agent specialized in system maintenance and backup operations"""
    
    def __init__(self, additional_tools: Optional[List[BaseTool]] = None, **kwargs):
        # Define core tools
        core_tools = [
            BackupStatusTool(),
            CreateBackupTool(),
            RestoreBackupTool(),
            BackupHistoryTool(),
            PredictiveMaintenanceTool(),
            SystemInfoTool(),
            ServiceManagementTool()
        ]
        
        # Add any additional tools
        if additional_tools:
            core_tools.extend(additional_tools)
        
        # Define capabilities
        capabilities = [
            "Backup planning and execution",
            "Disaster recovery operations",
            "Predictive maintenance analysis",
            "Maintenance window coordination",
            "System patching and updates",
            "Capacity management and planning"
        ]
        
        super().__init__(
            name="Maintenance Agent",
            description="Specialized agent for system maintenance and backup operations",
            role="Maintenance Coordinator",
            tools=core_tools,
            capabilities=capabilities,
            **kwargs
        )
    
    def _get_system_message(self) -> str:
        """Get specialized system message for maintenance agent"""
        base_message = self._get_base_system_message()
        
        specialized_message = f"""{base_message}

As a Maintenance Coordinator, you specialize in:
- Planning and executing system maintenance
- Managing backup and recovery operations
- Predictive maintenance and failure prevention
- Coordinating maintenance windows
- Ensuring business continuity
- Capacity planning and resource optimization

Maintenance best practices:
1. Always verify backup integrity before proceeding
2. Plan maintenance during approved windows
3. Ensure rollback procedures are in place
4. Document all maintenance activities
5. Communicate impacts to stakeholders

When performing maintenance:
- Assess risks and dependencies
- Create detailed execution plans
- Verify prerequisites are met
- Monitor progress and system health
- Validate successful completion

Safety first: Always ensure data protection and system availability."""
        
        return specialized_message
    
    def plan_maintenance(self, systems: List[str], maintenance_type: str, preferred_window: Optional[str] = None) -> Dict[str, Any]:
        """Plan maintenance activities"""
        planning_prompt = f"""Please create a maintenance plan for {maintenance_type} on systems: {', '.join(systems)}.
        {f'Preferred maintenance window: {preferred_window}' if preferred_window else ''}
        
        Planning requirements:
        1. Assess current system state and dependencies
        2. Identify required maintenance tasks
        3. Determine optimal maintenance sequence
        4. Estimate duration and resource needs
        5. Identify risks and mitigation strategies
        
        Provide:
        - Detailed maintenance schedule
        - Task breakdown with timelines
        - Required resources and prerequisites
        - Risk assessment and contingencies
        - Communication plan for stakeholders"""
        
        return self.run(planning_prompt)
    
    def backup_strategy(self, scope: List[str], requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Develop backup strategy"""
        strategy_prompt = f"""Please develop a comprehensive backup strategy for: {', '.join(scope)}.
        {f'Requirements: {requirements}' if requirements else ''}
        
        Strategy should address:
        1. Backup types and frequency
        2. Retention policies
        3. Storage requirements and locations
        4. Recovery time objectives (RTO)
        5. Recovery point objectives (RPO)
        6. Testing and validation procedures
        
        Provide:
        - Recommended backup architecture
        - Schedule for different backup types
        - Storage sizing and rotation plan
        - Disaster recovery procedures
        - Compliance considerations
        - Cost estimates"""
        
        return self.run(strategy_prompt)
    
    def execute_maintenance(self, maintenance_plan: str, dry_run: bool = True) -> Dict[str, Any]:
        """Execute maintenance plan"""
        execution_prompt = f"""Please {'simulate' if dry_run else 'execute'} the following maintenance plan: {maintenance_plan}
        
        Execution steps:
        1. Verify all prerequisites are met
        2. Create pre-maintenance backups
        3. Execute maintenance tasks in sequence
        4. Validate each step completion
        5. Perform post-maintenance verification
        
        {'This is a DRY RUN - simulate actions only' if dry_run else 'This is LIVE EXECUTION - proceed with caution'}
        
        Report:
        - Pre-maintenance checks status
        - Task execution progress
        - Any issues encountered
        - Validation results
        - Rollback readiness"""
        
        return self.run(execution_prompt)
    
    def disaster_recovery(self, incident_type: str, affected_systems: List[str], target_rto: Optional[str] = None) -> Dict[str, Any]:
        """Coordinate disaster recovery"""
        recovery_prompt = f"""Please coordinate disaster recovery for {incident_type} affecting: {', '.join(affected_systems)}.
        {f'Target RTO: {target_rto}' if target_rto else ''}
        
        Recovery process:
        1. Assess damage and data loss
        2. Identify available backups
        3. Determine recovery strategy
        4. Execute recovery procedures
        5. Validate system functionality
        
        Provide:
        - Current situation assessment
        - Available recovery options
        - Recommended recovery path
        - Step-by-step recovery plan
        - Estimated recovery timeline
        - Post-recovery validation steps"""
        
        return self.run(recovery_prompt)
    
    def predictive_analysis(self, systems: List[str], analysis_period: str = "30d") -> Dict[str, Any]:
        """Perform predictive maintenance analysis"""
        predictive_prompt = f"""Please perform predictive maintenance analysis for systems: {', '.join(systems)} over the next {analysis_period}.
        
        Analysis areas:
        1. Component failure predictions
        2. Capacity exhaustion forecasts
        3. Performance degradation trends
        4. Maintenance window recommendations
        5. Resource optimization opportunities
        
        Provide:
        - Risk assessment by system
        - Predicted failure timeline
        - Recommended preventive actions
        - Maintenance schedule optimization
        - Budget impact analysis
        - Priority ranking of actions"""
        
        return self.run(predictive_prompt)
    
    def patch_management(self, systems: List[str], patch_type: str = "security") -> Dict[str, Any]:
        """Manage system patching"""
        patch_prompt = f"""Please create a patch management plan for {patch_type} patches on: {', '.join(systems)}.
        
        Plan should include:
        1. Available patches assessment
        2. Patch criticality and priorities
        3. Dependency analysis
        4. Testing requirements
        5. Rollout schedule
        6. Rollback procedures
        
        Provide:
        - Patch inventory and priorities
        - Testing plan and success criteria
        - Phased deployment schedule
        - Risk mitigation strategies
        - Validation procedures
        - Emergency rollback plan"""
        
        return self.run(patch_prompt)