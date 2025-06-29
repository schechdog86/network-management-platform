"""
Command Parser - Main NLP Pipeline

Orchestrates the complete natural language command processing pipeline
using 2025 best practices:
- Intent recognition
- Entity extraction  
- Validation and safety checks
- Error handling and user feedback
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime

from langchain_core.language_models import BaseLanguageModel

from .intent_recognizer import IntentRecognizer, CommandIntent
from .entity_extractor import EntityExtractor, ExtractedEntity
from .command_validator import CommandValidator, ValidationContext, ValidationStatus, RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class ParsedCommand:
    """Complete parsed command with all components"""
    raw_command: str
    intent: CommandIntent
    intent_confidence: float
    entities: List[ExtractedEntity]
    validation_status: ValidationStatus
    risk_level: RiskLevel
    required_permissions: List[str]
    messages: List[str]
    confirmation_required: bool
    confirmation_prompt: Optional[str]
    executable: bool
    suggested_action: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class ParseResult:
    """Result of command parsing"""
    success: bool
    command: Optional[ParsedCommand]
    error: Optional[str]
    suggestions: List[str]
    clarification_needed: bool
    clarification_prompt: Optional[str]


class CommandParser:
    """Main command parser orchestrating NLP pipeline"""
    
    def __init__(self, llm: Optional[BaseLanguageModel] = None):
        self.llm = llm
        self.intent_recognizer = IntentRecognizer(llm)
        self.entity_extractor = EntityExtractor(llm)
        self.validator = CommandValidator()
        self.command_history = []
        
    def parse_command(self, 
                     command: str, 
                     context: Optional[Dict[str, Any]] = None,
                     validation_context: Optional[ValidationContext] = None) -> ParseResult:
        """Parse natural language command through complete pipeline"""
        
        try:
            # Stage 1: Intent Recognition
            logger.info(f"Parsing command: {command}")
            intent_result = self.intent_recognizer.recognize_intent(command)
            
            # Check if clarification needed
            if intent_result.confidence < 0.5 or intent_result.intent == CommandIntent.UNKNOWN:
                return self._handle_unclear_intent(command, intent_result)
            
            # Stage 2: Entity Extraction
            entities = self.entity_extractor.extract_entities(command, context)
            
            # Validate entities
            valid_entities, entity_errors = self.entity_extractor.validate_entities(entities)
            if entity_errors:
                return self._handle_entity_errors(command, intent_result, entity_errors)
            
            # Stage 3: Command Validation
            if not validation_context:
                validation_context = self._create_validation_context(context)
            
            validation_result = self.validator.validate_command(
                intent_result.intent,
                valid_entities,
                command,
                validation_context
            )
            
            # Stage 4: Build parsed command
            parsed_command = ParsedCommand(
                raw_command=command,
                intent=intent_result.intent,
                intent_confidence=intent_result.confidence,
                entities=valid_entities,
                validation_status=validation_result.status,
                risk_level=validation_result.risk_level,
                required_permissions=validation_result.required_permissions,
                messages=validation_result.messages,
                confirmation_required=(
                    validation_result.status == ValidationStatus.REQUIRES_CONFIRMATION
                ),
                confirmation_prompt=validation_result.confirmation_prompt,
                executable=(
                    validation_result.status in [
                        ValidationStatus.VALID,
                        ValidationStatus.REQUIRES_CONFIRMATION
                    ]
                ),
                suggested_action=validation_result.suggested_alternative,
                metadata={
                    'timestamp': datetime.now().isoformat(),
                    'parser_version': '2025.1',
                    'safety_checks': validation_result.safety_checks
                }
            )
            
            # Add to history
            self.command_history.append(parsed_command)
            
            # Return success result
            return ParseResult(
                success=True,
                command=parsed_command,
                error=None,
                suggestions=self._generate_suggestions(parsed_command),
                clarification_needed=False,
                clarification_prompt=None
            )
            
        except Exception as e:
            logger.error(f"Command parsing failed: {e}")
            return ParseResult(
                success=False,
                command=None,
                error=f"Failed to parse command: {str(e)}",
                suggestions=["Try rephrasing your command", "Use 'help' for examples"],
                clarification_needed=False,
                clarification_prompt=None
            )
    
    def _handle_unclear_intent(self, command: str, intent_result) -> ParseResult:
        """Handle unclear or ambiguous intent"""
        # Generate suggestions based on partial matches
        suggestions = []
        
        # Get example commands for likely intents
        if intent_result.intent != CommandIntent.UNKNOWN:
            examples = self.intent_recognizer.get_intent_examples(intent_result.intent)
            suggestions.extend(examples[:2])
        
        # Generate clarification prompt
        clarification = "I'm not sure what you want to do. "
        
        if intent_result.suggested_action:
            clarification += intent_result.suggested_action
        else:
            clarification += "Could you please clarify?"
        
        return ParseResult(
            success=False,
            command=None,
            error="Unable to understand the command",
            suggestions=suggestions,
            clarification_needed=True,
            clarification_prompt=clarification
        )
    
    def _handle_entity_errors(self, command: str, intent_result, errors: List[str]) -> ParseResult:
        """Handle entity extraction errors"""
        # Generate helpful error message
        error_msg = "Found issues with the command:\n" + "\n".join(f"• {e}" for e in errors)
        
        # Generate suggestions based on intent
        suggestions = []
        examples = self.intent_recognizer.get_intent_examples(intent_result.intent)
        if examples:
            suggestions.append(f"Example: {examples[0]}")
        
        return ParseResult(
            success=False,
            command=None,
            error=error_msg,
            suggestions=suggestions,
            clarification_needed=True,
            clarification_prompt="Please provide valid values for the highlighted issues"
        )
    
    def _create_validation_context(self, context: Optional[Dict[str, Any]]) -> ValidationContext:
        """Create validation context from general context"""
        if not context:
            context = {}
        
        return ValidationContext(
            user_role=context.get('user_role', 'operator'),
            time_of_day=datetime.now(),
            maintenance_window=context.get('maintenance_window', False),
            production_environment=context.get('production', True),
            previous_commands=[cmd.intent.value for cmd in self.command_history[-10:]],
            affected_systems=context.get('affected_systems', [])
        )
    
    def _generate_suggestions(self, command: ParsedCommand) -> List[str]:
        """Generate helpful suggestions based on parsed command"""
        suggestions = []
        
        # If blocked, suggest alternatives
        if command.validation_status == ValidationStatus.BLOCKED:
            if command.suggested_action:
                suggestions.append(command.suggested_action)
            suggestions.append("Contact administrator for elevated permissions")
        
        # If missing permissions
        elif command.validation_status == ValidationStatus.REQUIRES_ELEVATION:
            suggestions.append(f"Request permissions: {', '.join(command.required_permissions)}")
        
        # If high risk, suggest safety measures
        elif command.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            suggestions.append("Consider running in test environment first")
            suggestions.append("Ensure you have a recent backup")
        
        return suggestions
    
    def format_response(self, parse_result: ParseResult) -> str:
        """Format parse result for user display"""
        if not parse_result.success:
            response = f"❌ {parse_result.error}\n"
            
            if parse_result.clarification_needed:
                response += f"\n{parse_result.clarification_prompt}\n"
            
            if parse_result.suggestions:
                response += "\n💡 Suggestions:\n"
                for suggestion in parse_result.suggestions:
                    response += f"  • {suggestion}\n"
            
            return response
        
        # Success case
        cmd = parse_result.command
        response = f"✅ Understood: {cmd.intent.value.replace('_', ' ').title()}\n"
        response += f"   Confidence: {cmd.intent_confidence:.0%}\n"
        response += f"   Risk Level: {cmd.risk_level.value}\n"
        
        # Show extracted entities
        if cmd.entities:
            response += "\n📋 Detected:\n"
            for entity in cmd.entities:
                response += f"  • {entity.entity_type.value}: {entity.value}\n"
        
        # Show validation status
        if cmd.validation_status == ValidationStatus.VALID:
            response += "\n✅ Command validated and ready to execute\n"
        elif cmd.validation_status == ValidationStatus.REQUIRES_CONFIRMATION:
            response += f"\n⚠️  {cmd.confirmation_prompt}\n"
        elif cmd.validation_status == ValidationStatus.BLOCKED:
            response += "\n🚫 Command blocked for safety reasons\n"
        
        # Show messages
        if cmd.messages:
            response += "\n📝 Notes:\n"
            for msg in cmd.messages:
                response += f"  • {msg}\n"
        
        # Show suggestions
        if parse_result.suggestions:
            response += "\n💡 Suggestions:\n"
            for suggestion in parse_result.suggestions:
                response += f"  • {suggestion}\n"
        
        return response
    
    def get_command_preview(self, parsed_command: ParsedCommand) -> str:
        """Generate preview of what command will do"""
        intent_descriptions = {
            CommandIntent.NETWORK_SCAN: "Scan network {network} to discover active devices",
            CommandIntent.DEVICE_STATUS: "Check status and health of {device}",
            CommandIntent.CONNECTIVITY_TEST: "Test connectivity to {target}",
            CommandIntent.SERVICE_MANAGE: "{action} service {service}",
            CommandIntent.BACKUP_CREATE: "Create {type} backup of {target}",
            CommandIntent.PERFORMANCE_ANALYZE: "Analyze {metric} performance on {device}",
        }
        
        template = intent_descriptions.get(
            parsed_command.intent,
            f"Execute {parsed_command.intent.value}"
        )
        
        # Fill in entity values
        replacements = {}
        for entity in parsed_command.entities:
            key = entity.entity_type.value.split('_')[0]
            replacements[key] = entity.value
        
        preview = template
        for key, value in replacements.items():
            preview = preview.replace(f"{{{key}}}", value)
        
        # Remove any remaining placeholders
        preview = re.sub(r'\{[^}]+\}', '', preview)
        
        return preview
    
    def get_help(self, topic: Optional[str] = None) -> str:
        """Get help on using the command parser"""
        if not topic:
            return """
Natural Language Command Interface - Help

SUPPORTED OPERATIONS:
• Network Operations: scan, ping, trace route, check ports
• System Management: start/stop services, check status
• Monitoring: view metrics, analyze performance, manage alerts
• Backup Operations: create, restore, check backup status
• Security: scan vulnerabilities, audit compliance

EXAMPLES:
• "scan network 192.168.1.0/24"
• "check status of web-server"
• "restart nginx service"
• "analyze CPU usage for last 24 hours"
• "create backup of database server"

SAFETY FEATURES:
• Commands are validated before execution
• High-risk operations require confirmation
• Blocked patterns prevent dangerous commands
• Permission checks ensure authorized access

Type 'help <topic>' for detailed help on specific topics.
"""
        
        # Topic-specific help
        help_topics = {
            'network': """
NETWORK OPERATIONS:
• Scan: "scan network 192.168.1.0/24", "discover devices in subnet"
• Status: "check device status server-01", "is database online?"
• Connectivity: "ping google.com", "test connection to 10.0.0.1"
• Ports: "check port 443 on web-server", "scan ports on 192.168.1.100"
""",
            'service': """
SERVICE MANAGEMENT:
• Start: "start nginx service", "start web server"
• Stop: "stop mysql", "shutdown database service"
• Restart: "restart apache on web-server"
• Status: "check nginx status", "is postgresql running?"
""",
            'backup': """
BACKUP OPERATIONS:
• Create: "create full backup", "backup database server"
• Restore: "restore from yesterday's backup"
• Status: "check backup status", "show recent backups"
""",
            'safety': """
SAFETY FEATURES:
• Pattern Blocking: Dangerous commands are automatically blocked
• Confirmation: High-risk operations require explicit confirmation
• Permission Checks: Operations require appropriate permissions
• Audit Trail: All commands are logged for security
• Context Awareness: Commands validated based on time and environment
"""
        }
        
        return help_topics.get(topic, f"No help available for topic: {topic}")