"""
Command Executor - Executes validated commands

Bridges parsed commands to actual tool execution using LangChain agents
with 2025 best practices:
- Safe execution with rollback capability
- Progress tracking and feedback
- Error handling and recovery
- Audit logging
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
import json

from .command_parser import ParsedCommand, CommandIntent
from .entity_extractor import ExtractedEntity, EntityType
from ..agents import NetworkAdminAgent, SystemAnalystAgent, SecurityMonitorAgent, MaintenanceAgent
from ..main import AgentType, ai_orchestrator

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context for command execution"""
    dry_run: bool = False
    timeout: int = 300  # 5 minutes default
    rollback_enabled: bool = True
    progress_callback: Optional[Callable[[str, float], None]] = None
    log_execution: bool = True


@dataclass
class ExecutionResult:
    """Result of command execution"""
    success: bool
    output: Any
    error: Optional[str]
    execution_time: float
    rollback_available: bool
    audit_log: Dict[str, Any]
    warnings: List[str]


class CommandExecutor:
    """Executes parsed commands using appropriate agents"""
    
    def __init__(self):
        self.execution_history = []
        self.rollback_handlers = {}
        self._init_execution_mappings()
    
    def _init_execution_mappings(self):
        """Map intents to execution strategies"""
        self.execution_strategies = {
            # Network operations
            CommandIntent.NETWORK_SCAN: self._execute_network_scan,
            CommandIntent.DEVICE_STATUS: self._execute_device_status,
            CommandIntent.CONNECTIVITY_TEST: self._execute_connectivity_test,
            CommandIntent.PORT_CHECK: self._execute_port_check,
            CommandIntent.ROUTE_TRACE: self._execute_route_trace,
            
            # System operations
            CommandIntent.SERVICE_MANAGE: self._execute_service_manage,
            CommandIntent.PROCESS_MANAGE: self._execute_process_manage,
            CommandIntent.RESOURCE_CHECK: self._execute_resource_check,
            CommandIntent.LOG_ANALYSIS: self._execute_log_analysis,
            CommandIntent.SYSTEM_INFO: self._execute_system_info,
            
            # Backup operations
            CommandIntent.BACKUP_CREATE: self._execute_backup_create,
            CommandIntent.BACKUP_RESTORE: self._execute_backup_restore,
            CommandIntent.BACKUP_STATUS: self._execute_backup_status,
            
            # Monitoring operations
            CommandIntent.METRICS_QUERY: self._execute_metrics_query,
            CommandIntent.ALERT_MANAGE: self._execute_alert_manage,
            CommandIntent.PERFORMANCE_ANALYZE: self._execute_performance_analyze,
            
            # Security operations
            CommandIntent.SECURITY_SCAN: self._execute_security_scan,
            CommandIntent.VULNERABILITY_CHECK: self._execute_vulnerability_check,
            CommandIntent.COMPLIANCE_AUDIT: self._execute_compliance_audit,
        }
    
    async def execute_command(self, 
                            parsed_command: ParsedCommand,
                            context: Optional[ExecutionContext] = None) -> ExecutionResult:
        """Execute a parsed command"""
        if not context:
            context = ExecutionContext()
        
        start_time = datetime.now()
        audit_log = self._create_audit_log(parsed_command, context)
        
        try:
            # Check if command is executable
            if not parsed_command.executable:
                return ExecutionResult(
                    success=False,
                    output=None,
                    error="Command is not executable due to validation failures",
                    execution_time=0,
                    rollback_available=False,
                    audit_log=audit_log,
                    warnings=parsed_command.messages
                )
            
            # Get execution strategy
            strategy = self.execution_strategies.get(parsed_command.intent)
            if not strategy:
                return ExecutionResult(
                    success=False,
                    output=None,
                    error=f"No execution strategy for intent: {parsed_command.intent}",
                    execution_time=0,
                    rollback_available=False,
                    audit_log=audit_log,
                    warnings=[]
                )
            
            # Report progress
            if context.progress_callback:
                context.progress_callback("Starting execution...", 0.1)
            
            # Execute with timeout
            if asyncio.iscoroutinefunction(strategy):
                result = await asyncio.wait_for(
                    strategy(parsed_command, context),
                    timeout=context.timeout
                )
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, strategy, parsed_command, context),
                    timeout=context.timeout
                )
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update audit log
            audit_log['execution_time'] = execution_time
            audit_log['success'] = result.get('success', True)
            
            # Log execution if enabled
            if context.log_execution:
                self._log_execution(audit_log)
            
            # Add to history
            self.execution_history.append({
                'command': parsed_command,
                'result': result,
                'timestamp': start_time,
                'audit_log': audit_log
            })
            
            return ExecutionResult(
                success=result.get('success', True),
                output=result.get('output'),
                error=result.get('error'),
                execution_time=execution_time,
                rollback_available=self._has_rollback(parsed_command),
                audit_log=audit_log,
                warnings=result.get('warnings', [])
            )
            
        except asyncio.TimeoutError:
            execution_time = (datetime.now() - start_time).total_seconds()
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Command execution timed out after {context.timeout} seconds",
                execution_time=execution_time,
                rollback_available=False,
                audit_log=audit_log,
                warnings=[]
            )
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Command execution failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                execution_time=execution_time,
                rollback_available=False,
                audit_log=audit_log,
                warnings=[]
            )
    
    def _create_audit_log(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Create audit log entry"""
        return {
            'timestamp': datetime.now().isoformat(),
            'command': command.raw_command,
            'intent': command.intent.value,
            'risk_level': command.risk_level.value,
            'dry_run': context.dry_run,
            'entities': [
                {
                    'type': e.entity_type.value,
                    'value': e.value
                } for e in command.entities
            ],
            'validation_status': command.validation_status.value,
            'user': 'current_user',  # Would get from auth context
            'session_id': 'session_123'  # Would get from session
        }
    
    def _log_execution(self, audit_log: Dict[str, Any]):
        """Log execution to audit system"""
        # In production, this would write to audit log system
        logger.info(f"Command executed: {json.dumps(audit_log)}")
    
    def _has_rollback(self, command: ParsedCommand) -> bool:
        """Check if command has rollback capability"""
        rollback_capable = [
            CommandIntent.SERVICE_MANAGE,
            CommandIntent.BACKUP_RESTORE,
            CommandIntent.PROCESS_MANAGE
        ]
        return command.intent in rollback_capable
    
    # Execution strategies for each intent
    
    async def _execute_network_scan(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute network scan"""
        # Extract network from entities
        network = None
        for entity in command.entities:
            if entity.entity_type in [EntityType.IP_RANGE, EntityType.IP_ADDRESS]:
                network = entity.value
                break
        
        if not network:
            return {'success': False, 'error': 'No network specified'}
        
        # Build query for agent
        query = f"Scan network {network} and list all discovered devices with their status"
        
        if context.progress_callback:
            context.progress_callback("Scanning network...", 0.5)
        
        # Use network admin agent
        result = await ai_orchestrator.process_query_async(
            query,
            AgentType.NETWORK_ADMIN
        )
        
        return {
            'success': result['success'],
            'output': result['response'],
            'error': result.get('error')
        }
    
    async def _execute_device_status(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute device status check"""
        # Extract device from entities
        device = None
        for entity in command.entities:
            if entity.entity_type == EntityType.DEVICE_NAME:
                device = entity.value
                break
        
        if not device:
            return {'success': False, 'error': 'No device specified'}
        
        query = f"Check the detailed status of {device} including connectivity, services, and resource usage"
        
        if context.progress_callback:
            context.progress_callback(f"Checking {device}...", 0.5)
        
        result = await ai_orchestrator.process_query_async(
            query,
            AgentType.NETWORK_ADMIN
        )
        
        return {
            'success': result['success'],
            'output': result['response'],
            'error': result.get('error')
        }
    
    async def _execute_connectivity_test(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute connectivity test"""
        # Extract target
        target = None
        for entity in command.entities:
            if entity.entity_type in [EntityType.DEVICE_NAME, EntityType.IP_ADDRESS]:
                target = entity.value
                break
        
        if not target:
            return {'success': False, 'error': 'No target specified'}
        
        query = f"Test connectivity to {target} using ping and report latency and packet loss"
        
        result = await ai_orchestrator.process_query_async(
            query,
            AgentType.NETWORK_ADMIN
        )
        
        return {
            'success': result['success'],
            'output': result['response'],
            'error': result.get('error')
        }
    
    async def _execute_service_manage(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute service management"""
        # Extract service and action
        service = None
        action = None
        device = None
        
        for entity in command.entities:
            if entity.entity_type == EntityType.SERVICE_NAME:
                service = entity.value
            elif entity.entity_type == EntityType.ACTION:
                action = entity.value
            elif entity.entity_type == EntityType.DEVICE_NAME:
                device = entity.value
        
        if not service:
            return {'success': False, 'error': 'No service specified'}
        
        if not action:
            # Try to infer from command
            cmd_lower = command.raw_command.lower()
            if 'start' in cmd_lower:
                action = 'start'
            elif 'stop' in cmd_lower:
                action = 'stop'
            elif 'restart' in cmd_lower:
                action = 'restart'
            else:
                return {'success': False, 'error': 'No action specified'}
        
        # Build query
        target = f"on {device}" if device else ""
        query = f"{action.capitalize()} the {service} service {target}"
        
        if context.dry_run:
            return {
                'success': True,
                'output': f"DRY RUN: Would {action} {service} {target}",
                'warnings': ['This is a dry run - no actual changes made']
            }
        
        # Store rollback info
        if context.rollback_enabled:
            rollback_id = f"{command.intent}_{datetime.now().timestamp()}"
            self.rollback_handlers[rollback_id] = {
                'service': service,
                'action': 'start' if action == 'stop' else 'stop' if action == 'start' else 'restart',
                'device': device
            }
        
        result = await ai_orchestrator.process_query_async(
            query,
            AgentType.NETWORK_ADMIN
        )
        
        return {
            'success': result['success'],
            'output': result['response'],
            'error': result.get('error')
        }
    
    async def _execute_backup_create(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute backup creation"""
        # Extract backup type and target
        backup_type = 'full'
        target = None
        
        for entity in command.entities:
            if entity.entity_type == EntityType.BACKUP_TYPE:
                backup_type = entity.value
            elif entity.entity_type == EntityType.DEVICE_NAME:
                target = entity.value
        
        query = f"Create a {backup_type} backup"
        if target:
            query += f" of {target}"
        
        if context.progress_callback:
            context.progress_callback("Initiating backup...", 0.2)
        
        result = await ai_orchestrator.process_query_async(
            query,
            AgentType.MAINTENANCE
        )
        
        return {
            'success': result['success'],
            'output': result['response'],
            'error': result.get('error')
        }
    
    async def _execute_performance_analyze(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute performance analysis"""
        # Extract target and metrics
        target = None
        metrics = []
        time_range = "24h"
        
        for entity in command.entities:
            if entity.entity_type == EntityType.DEVICE_NAME:
                target = entity.value
            elif entity.entity_type == EntityType.METRIC_TYPE:
                metrics.append(entity.value)
            elif entity.entity_type == EntityType.TIME_RANGE:
                time_range = entity.value
        
        query = f"Analyze performance"
        if metrics:
            query += f" focusing on {', '.join(metrics)}"
        if target:
            query += f" for {target}"
        query += f" over the {time_range}"
        
        result = await ai_orchestrator.process_query_async(
            query,
            AgentType.SYSTEM_ANALYST
        )
        
        return {
            'success': result['success'],
            'output': result['response'],
            'error': result.get('error')
        }
    
    async def _execute_security_scan(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute security scan"""
        # Extract target
        target = None
        for entity in command.entities:
            if entity.entity_type in [EntityType.DEVICE_NAME, EntityType.IP_ADDRESS]:
                target = entity.value
                break
        
        query = f"Perform a security scan"
        if target:
            query += f" on {target}"
        query += " and report any vulnerabilities or security issues"
        
        if context.progress_callback:
            context.progress_callback("Running security scan...", 0.3)
        
        result = await ai_orchestrator.process_query_async(
            query,
            AgentType.SECURITY_MONITOR
        )
        
        return {
            'success': result['success'],
            'output': result['response'],
            'error': result.get('error')
        }
    
    # Add more execution strategies for other intents...
    
    async def _execute_port_check(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute port check"""
        ports = []
        target = None
        
        for entity in command.entities:
            if entity.entity_type == EntityType.PORT:
                ports.append(entity.normalized_value)
            elif entity.entity_type in [EntityType.DEVICE_NAME, EntityType.IP_ADDRESS]:
                target = entity.value
        
        if not ports:
            return {'success': False, 'error': 'No ports specified'}
        
        query = f"Check if ports {', '.join(map(str, ports))} are open"
        if target:
            query += f" on {target}"
        
        result = await ai_orchestrator.process_query_async(query, AgentType.NETWORK_ADMIN)
        return {'success': result['success'], 'output': result['response'], 'error': result.get('error')}
    
    async def _execute_route_trace(self, command: ParsedCommand, context: ExecutionContext) -> Dict[str, Any]:
        """Execute route trace"""
        target = None
        for entity in command.entities:
            if entity.entity_type in [EntityType.DEVICE_NAME, EntityType.IP_ADDRESS]:
                target = entity.value
                break
        
        if not target:
            return {'success': False, 'error': 'No target specified'}
        
        query = f"Trace the network route to {target}"
        result = await ai_orchestrator.process_query_async(query, AgentType.NETWORK_ADMIN)
        return {'success': result['success'], 'output': result['response'], 'error': result.get('error')}
    
    # Additional execution methods can be added for other intents...