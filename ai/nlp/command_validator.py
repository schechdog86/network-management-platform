"""
Command Validation and Safety Checks

Implements 2025 best practices for command validation:
- Multi-stage validation pipeline
- Context-aware safety checks
- Permission verification
- Risk assessment
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime, time

from .intent_recognizer import CommandIntent
from .entity_extractor import ExtractedEntity, EntityType

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for commands"""
    LOW = "low"           # Read-only operations
    MEDIUM = "medium"     # Modifications with limited scope
    HIGH = "high"         # System-wide changes
    CRITICAL = "critical" # Destructive or security-sensitive


class ValidationStatus(Enum):
    """Validation result status"""
    VALID = "valid"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_ELEVATION = "requires_elevation"
    BLOCKED = "blocked"
    INVALID = "invalid"


@dataclass
class ValidationResult:
    """Command validation result"""
    status: ValidationStatus
    risk_level: RiskLevel
    messages: List[str]
    required_permissions: List[str]
    confirmation_prompt: Optional[str] = None
    suggested_alternative: Optional[str] = None
    safety_checks: Dict[str, bool] = None


@dataclass
class ValidationContext:
    """Context for validation"""
    user_role: str = "operator"
    time_of_day: Optional[datetime] = None
    maintenance_window: bool = False
    production_environment: bool = True
    previous_commands: List[str] = None
    affected_systems: List[str] = None


class CommandValidator:
    """Advanced command validator with safety checks"""
    
    def __init__(self):
        self._init_risk_mappings()
        self._init_permission_mappings()
        self._init_safety_rules()
        self._init_blocked_patterns()
    
    def _init_risk_mappings(self):
        """Initialize risk level mappings"""
        self.risk_mappings = {
            # Low risk - read-only operations
            CommandIntent.DEVICE_STATUS: RiskLevel.LOW,
            CommandIntent.CONNECTIVITY_TEST: RiskLevel.LOW,
            CommandIntent.PORT_CHECK: RiskLevel.LOW,
            CommandIntent.ROUTE_TRACE: RiskLevel.LOW,
            CommandIntent.SYSTEM_INFO: RiskLevel.LOW,
            CommandIntent.BACKUP_STATUS: RiskLevel.LOW,
            CommandIntent.METRICS_QUERY: RiskLevel.LOW,
            
            # Medium risk - limited modifications
            CommandIntent.NETWORK_SCAN: RiskLevel.MEDIUM,
            CommandIntent.LOG_ANALYSIS: RiskLevel.MEDIUM,
            CommandIntent.PERFORMANCE_ANALYZE: RiskLevel.MEDIUM,
            CommandIntent.ALERT_MANAGE: RiskLevel.MEDIUM,
            
            # High risk - system modifications
            CommandIntent.SERVICE_MANAGE: RiskLevel.HIGH,
            CommandIntent.PROCESS_MANAGE: RiskLevel.HIGH,
            CommandIntent.BACKUP_CREATE: RiskLevel.HIGH,
            CommandIntent.SECURITY_SCAN: RiskLevel.HIGH,
            
            # Critical risk - destructive operations
            CommandIntent.BACKUP_RESTORE: RiskLevel.CRITICAL,
            CommandIntent.COMPLIANCE_AUDIT: RiskLevel.CRITICAL,
        }
    
    def _init_permission_mappings(self):
        """Initialize required permissions"""
        self.permission_mappings = {
            CommandIntent.NETWORK_SCAN: ["network:scan"],
            CommandIntent.DEVICE_STATUS: ["device:read"],
            CommandIntent.CONNECTIVITY_TEST: ["network:test"],
            CommandIntent.SERVICE_MANAGE: ["service:manage", "system:modify"],
            CommandIntent.BACKUP_CREATE: ["backup:create", "storage:write"],
            CommandIntent.BACKUP_RESTORE: ["backup:restore", "system:critical"],
            CommandIntent.SECURITY_SCAN: ["security:scan", "system:audit"],
            CommandIntent.PROCESS_MANAGE: ["process:manage", "system:modify"],
        }
    
    def _init_safety_rules(self):
        """Initialize safety rules"""
        self.safety_rules = {
            # Time-based rules
            'business_hours': {
                'start': time(8, 0),
                'end': time(18, 0),
                'blocked_intents': [
                    CommandIntent.SERVICE_MANAGE,
                    CommandIntent.BACKUP_RESTORE
                ],
                'message': "This operation is blocked during business hours"
            },
            
            # Production safeguards
            'production_limits': {
                'requires_confirmation': [
                    CommandIntent.SERVICE_MANAGE,
                    CommandIntent.PROCESS_MANAGE,
                    CommandIntent.BACKUP_RESTORE
                ],
                'blocked_services': [
                    'kernel', 'init', 'systemd'
                ],
                'message': "Production system modification requires confirmation"
            },
            
            # Resource limits
            'resource_limits': {
                'max_scan_range': 256,  # /24 maximum
                'max_concurrent_operations': 5,
                'max_backup_size_gb': 100
            }
        }
    
    def _init_blocked_patterns(self):
        """Initialize blocked command patterns"""
        self.blocked_patterns = [
            # Dangerous system commands
            r'rm\s+-rf\s+/',
            r'format\s+[cC]:',
            r'dd\s+if=/dev/zero',
            r'kill\s+-9\s+1\b',
            r'shutdown\s+-h\s+now',
            r'init\s+0',
            
            # Dangerous network commands
            r'iptables\s+-F',
            r'route\s+del\s+default',
            
            # SQL injection patterns
            r"';|--|\bor\b\s+1=1|\bunion\b.*\bselect\b",
            
            # Path traversal
            r'\.\./\.\./\.\.',
            
            # Wildcard deletions
            r'rm\s+.*\*',
            r'del\s+.*\*\.\*'
        ]
        
        self.compiled_blocked = [re.compile(p, re.IGNORECASE) for p in self.blocked_patterns]
    
    def validate_command(self, 
                        intent: CommandIntent,
                        entities: List[ExtractedEntity],
                        raw_command: str,
                        context: Optional[ValidationContext] = None) -> ValidationResult:
        """Validate command with multi-stage pipeline"""
        
        if not context:
            context = ValidationContext()
        
        # Stage 1: Check for blocked patterns
        blocked_check = self._check_blocked_patterns(raw_command)
        if blocked_check:
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                risk_level=RiskLevel.CRITICAL,
                messages=[f"Blocked: {blocked_check}"],
                required_permissions=[],
                suggested_alternative="Please use a safer command"
            )
        
        # Stage 2: Determine risk level
        risk_level = self._assess_risk(intent, entities)
        
        # Stage 3: Check permissions
        required_permissions = self._get_required_permissions(intent)
        permission_check = self._check_permissions(required_permissions, context)
        
        # Stage 4: Apply safety rules
        safety_checks = self._apply_safety_rules(intent, entities, context)
        
        # Stage 5: Entity validation
        entity_validation = self._validate_entities(intent, entities)
        
        # Stage 6: Context validation
        context_validation = self._validate_context(intent, entities, context)
        
        # Combine results
        return self._combine_validation_results(
            risk_level, permission_check, safety_checks, 
            entity_validation, context_validation, intent, entities
        )
    
    def _check_blocked_patterns(self, command: str) -> Optional[str]:
        """Check for blocked command patterns"""
        for pattern in self.compiled_blocked:
            if pattern.search(command):
                return f"Command matches blocked pattern: {pattern.pattern}"
        return None
    
    def _assess_risk(self, intent: CommandIntent, entities: List[ExtractedEntity]) -> RiskLevel:
        """Assess command risk level"""
        base_risk = self.risk_mappings.get(intent, RiskLevel.MEDIUM)
        
        # Elevate risk based on entities
        for entity in entities:
            # System-critical devices
            if entity.entity_type == EntityType.DEVICE_NAME:
                if any(critical in entity.normalized_value for critical in 
                       ['prod', 'master', 'primary', 'database', 'auth']):
                    if base_risk == RiskLevel.MEDIUM:
                        base_risk = RiskLevel.HIGH
                    elif base_risk == RiskLevel.HIGH:
                        base_risk = RiskLevel.CRITICAL
            
            # Sensitive services
            elif entity.entity_type == EntityType.SERVICE_NAME:
                if entity.normalized_value in ['kernel', 'systemd', 'init', 'ssh', 'firewall']:
                    base_risk = RiskLevel.CRITICAL
            
            # Large IP ranges
            elif entity.entity_type == EntityType.IP_RANGE:
                try:
                    import ipaddress
                    network = ipaddress.ip_network(entity.value, strict=False)
                    if network.num_addresses > 256:
                        base_risk = RiskLevel.HIGH
                except:
                    pass
        
        return base_risk
    
    def _get_required_permissions(self, intent: CommandIntent) -> List[str]:
        """Get required permissions for intent"""
        return self.permission_mappings.get(intent, ["system:read"])
    
    def _check_permissions(self, required: List[str], context: ValidationContext) -> Tuple[bool, List[str]]:
        """Check if user has required permissions"""
        # Simplified permission check - in production, integrate with RBAC
        user_permissions = {
            'admin': ['*'],
            'operator': ['device:read', 'network:scan', 'network:test', 'backup:create'],
            'viewer': ['device:read', 'network:test']
        }
        
        user_perms = user_permissions.get(context.user_role, [])
        
        if '*' in user_perms:
            return True, []
        
        missing = [p for p in required if p not in user_perms]
        return len(missing) == 0, missing
    
    def _apply_safety_rules(self, intent: CommandIntent, 
                           entities: List[ExtractedEntity], 
                           context: ValidationContext) -> Dict[str, bool]:
        """Apply safety rules"""
        checks = {}
        
        # Business hours check
        if context.time_of_day:
            current_time = context.time_of_day.time()
            business_hours = self.safety_rules['business_hours']
            
            if business_hours['start'] <= current_time <= business_hours['end']:
                if intent in business_hours['blocked_intents']:
                    checks['business_hours'] = False
                else:
                    checks['business_hours'] = True
            else:
                checks['business_hours'] = True
        
        # Production environment checks
        if context.production_environment:
            prod_limits = self.safety_rules['production_limits']
            
            if intent in prod_limits['requires_confirmation']:
                checks['production_confirmation'] = False
            
            # Check for blocked services
            for entity in entities:
                if entity.entity_type == EntityType.SERVICE_NAME:
                    if entity.normalized_value in prod_limits['blocked_services']:
                        checks['blocked_service'] = False
        
        # Resource limit checks
        resource_limits = self.safety_rules['resource_limits']
        
        for entity in entities:
            if entity.entity_type == EntityType.IP_RANGE:
                try:
                    import ipaddress
                    network = ipaddress.ip_network(entity.value, strict=False)
                    if network.num_addresses > resource_limits['max_scan_range']:
                        checks['scan_range_limit'] = False
                except:
                    pass
        
        return checks
    
    def _validate_entities(self, intent: CommandIntent, entities: List[ExtractedEntity]) -> Dict[str, Any]:
        """Validate entities for the intent"""
        validation = {'valid': True, 'messages': []}
        
        # Check required entities for intent
        required_entities = {
            CommandIntent.CONNECTIVITY_TEST: [EntityType.DEVICE_NAME, EntityType.IP_ADDRESS],
            CommandIntent.SERVICE_MANAGE: [EntityType.SERVICE_NAME, EntityType.ACTION],
            CommandIntent.PORT_CHECK: [EntityType.PORT],
            CommandIntent.BACKUP_RESTORE: [EntityType.BACKUP_TYPE],
        }
        
        if intent in required_entities:
            entity_types = {e.entity_type for e in entities}
            required = required_entities[intent]
            
            # Check if any of the required types is present
            if not any(req in entity_types for req in required):
                validation['valid'] = False
                validation['messages'].append(
                    f"Missing required information: {', '.join(r.value for r in required)}"
                )
        
        return validation
    
    def _validate_context(self, intent: CommandIntent, 
                         entities: List[ExtractedEntity], 
                         context: ValidationContext) -> Dict[str, Any]:
        """Validate command in context"""
        validation = {'valid': True, 'messages': []}
        
        # Check maintenance window requirements
        if not context.maintenance_window:
            if intent in [CommandIntent.SERVICE_MANAGE, CommandIntent.BACKUP_RESTORE]:
                validation['messages'].append(
                    "Warning: Operation outside maintenance window"
                )
        
        # Check for repeated commands (potential automation attack)
        if context.previous_commands:
            recent_commands = context.previous_commands[-10:]
            if recent_commands.count(str(intent)) > 5:
                validation['valid'] = False
                validation['messages'].append(
                    "Too many repeated commands detected"
                )
        
        return validation
    
    def _combine_validation_results(self, risk_level: RiskLevel,
                                   permission_check: Tuple[bool, List[str]],
                                   safety_checks: Dict[str, bool],
                                   entity_validation: Dict[str, Any],
                                   context_validation: Dict[str, Any],
                                   intent: CommandIntent,
                                   entities: List[ExtractedEntity]) -> ValidationResult:
        """Combine all validation results"""
        messages = []
        status = ValidationStatus.VALID
        
        # Permission check
        has_perms, missing_perms = permission_check
        if not has_perms:
            status = ValidationStatus.REQUIRES_ELEVATION
            messages.append(f"Missing permissions: {', '.join(missing_perms)}")
        
        # Safety checks
        failed_safety = [k for k, v in safety_checks.items() if not v]
        if failed_safety:
            if 'blocked_service' in failed_safety:
                status = ValidationStatus.BLOCKED
                messages.append("Cannot modify system-critical service")
            elif 'production_confirmation' in failed_safety:
                status = ValidationStatus.REQUIRES_CONFIRMATION
                messages.append("Production system modification requires confirmation")
            else:
                messages.extend([f"Failed safety check: {check}" for check in failed_safety])
        
        # Entity validation
        if not entity_validation['valid']:
            status = ValidationStatus.INVALID
            messages.extend(entity_validation['messages'])
        
        # Context validation
        if not context_validation['valid']:
            if status != ValidationStatus.BLOCKED:
                status = ValidationStatus.INVALID
            messages.extend(context_validation['messages'])
        
        # Generate confirmation prompt if needed
        confirmation_prompt = None
        if status == ValidationStatus.REQUIRES_CONFIRMATION:
            confirmation_prompt = self._generate_confirmation_prompt(intent, entities, risk_level)
        
        return ValidationResult(
            status=status,
            risk_level=risk_level,
            messages=messages,
            required_permissions=missing_perms if not has_perms else [],
            confirmation_prompt=confirmation_prompt,
            safety_checks=safety_checks
        )
    
    def _generate_confirmation_prompt(self, intent: CommandIntent, 
                                    entities: List[ExtractedEntity], 
                                    risk_level: RiskLevel) -> str:
        """Generate confirmation prompt"""
        action = intent.value.replace('_', ' ')
        
        # Build entity description
        entity_desc = []
        for entity in entities:
            if entity.entity_type in [EntityType.DEVICE_NAME, EntityType.SERVICE_NAME]:
                entity_desc.append(entity.value)
        
        target = ' on '.join(entity_desc) if entity_desc else 'the system'
        
        prompt = f"⚠️  {risk_level.value.upper()} RISK: {action} {target}\n\n"
        prompt += "This action may affect system availability.\n"
        prompt += "Type 'CONFIRM' to proceed or 'CANCEL' to abort: "
        
        return prompt