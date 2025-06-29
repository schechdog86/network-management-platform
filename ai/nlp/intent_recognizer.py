"""
Intent Recognition for Network Commands

Recognizes user intent from natural language commands using hybrid approach:
- Rule-based patterns for critical commands
- ML classification for flexible interpretation
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CommandIntent(Enum):
    """Supported command intents"""
    # Network operations
    NETWORK_SCAN = "network_scan"
    DEVICE_STATUS = "device_status"
    CONNECTIVITY_TEST = "connectivity_test"
    PORT_CHECK = "port_check"
    ROUTE_TRACE = "route_trace"
    
    # System operations
    SERVICE_MANAGE = "service_manage"
    PROCESS_MANAGE = "process_manage"
    RESOURCE_CHECK = "resource_check"
    LOG_ANALYSIS = "log_analysis"
    SYSTEM_INFO = "system_info"
    
    # Backup operations
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"
    BACKUP_STATUS = "backup_status"
    
    # Monitoring operations
    METRICS_QUERY = "metrics_query"
    ALERT_MANAGE = "alert_manage"
    PERFORMANCE_ANALYZE = "performance_analyze"
    
    # Security operations
    SECURITY_SCAN = "security_scan"
    VULNERABILITY_CHECK = "vulnerability_check"
    COMPLIANCE_AUDIT = "compliance_audit"
    
    # Unknown
    UNKNOWN = "unknown"


@dataclass
class IntentConfidence:
    """Intent recognition result with confidence"""
    intent: CommandIntent
    confidence: float
    evidence: List[str]
    suggested_action: Optional[str] = None


class IntentClassification(BaseModel):
    """LLM output schema for intent classification"""
    intent: str = Field(description="The recognized command intent")
    confidence: float = Field(description="Confidence score between 0 and 1")
    reasoning: str = Field(description="Explanation for the classification")
    ambiguity: Optional[str] = Field(None, description="Any ambiguity in the command")


class IntentRecognizer:
    """Hybrid intent recognizer using rules and LLM"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self._init_patterns()
        self._init_llm_classifier()
    
    def _init_patterns(self):
        """Initialize rule-based patterns for high-confidence matching"""
        self.patterns = {
            CommandIntent.NETWORK_SCAN: [
                r"scan\s+(network|subnet|ip\s*range)",
                r"discover\s+(devices?|hosts?|machines?)",
                r"find\s+(all\s+)?(devices?|computers?|servers?)",
                r"network\s+discovery",
                r"arp\s+scan"
            ],
            CommandIntent.DEVICE_STATUS: [
                r"(check|show|get)\s+(device|server|host|machine)\s+status",
                r"status\s+of\s+\w+",
                r"is\s+\w+\s+(up|down|online|offline|running)",
                r"health\s+(check|status)\s+\w+"
            ],
            CommandIntent.CONNECTIVITY_TEST: [
                r"ping\s+\w+",
                r"test\s+connect(ion|ivity)",
                r"can\s+(i\s+)?reach\s+\w+",
                r"check\s+connect(ion|ivity)\s+to\s+\w+"
            ],
            CommandIntent.PORT_CHECK: [
                r"(check|scan|test)\s+ports?\s+",
                r"port\s+\d+\s+(open|closed|status)",
                r"is\s+port\s+\d+\s+open",
                r"service\s+on\s+port\s+\d+"
            ],
            CommandIntent.SERVICE_MANAGE: [
                r"(start|stop|restart|reload)\s+(service|daemon)\s+\w+",
                r"(start|stop|restart)\s+\w+\s+service",
                r"service\s+\w+\s+(start|stop|restart|status)",
                r"systemctl\s+(start|stop|restart|status)"
            ],
            CommandIntent.BACKUP_CREATE: [
                r"(create|make|perform|start)\s+(a\s+)?backup",
                r"backup\s+(system|server|database|files?)",
                r"take\s+(a\s+)?backup",
                r"save\s+current\s+state"
            ],
            CommandIntent.BACKUP_RESTORE: [
                r"restore\s+(from\s+)?backup",
                r"recover\s+(system|server|database|files?)",
                r"rollback\s+to\s+",
                r"revert\s+to\s+(previous|backup)"
            ],
            CommandIntent.SECURITY_SCAN: [
                r"security\s+(scan|check|audit|assessment)",
                r"vulnerability\s+(scan|check|assessment)",
                r"check\s+for\s+vulnerabilit(y|ies)",
                r"pentest|penetration\s+test"
            ],
            CommandIntent.PERFORMANCE_ANALYZE: [
                r"(analyze|check)\s+performance",
                r"performance\s+(report|analysis|metrics)",
                r"why\s+is\s+\w+\s+slow",
                r"(cpu|memory|disk|network)\s+usage"
            ],
            CommandIntent.LOG_ANALYSIS: [
                r"(check|analyze|search|grep)\s+logs?",
                r"(show|get)\s+.*errors?\s+in\s+logs?",
                r"log\s+analysis",
                r"what\s+errors?\s+in\s+logs?"
            ]
        }
        
        # Compile patterns for efficiency
        self.compiled_patterns = {}
        for intent, patterns in self.patterns.items():
            self.compiled_patterns[intent] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
    
    def _init_llm_classifier(self):
        """Initialize LLM-based classifier if available"""
        if self.llm:
            self.parser = PydanticOutputParser(pydantic_object=IntentClassification)
            
            self.classification_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at classifying network and system administration commands.
                
                Classify the user's command into one of these intents:
                - network_scan: Scanning networks or discovering devices
                - device_status: Checking device/server status or health
                - connectivity_test: Testing connectivity (ping, reachability)
                - port_check: Checking port status or scanning ports
                - route_trace: Tracing network routes
                - service_manage: Starting/stopping/restarting services
                - process_manage: Managing processes
                - resource_check: Checking CPU/memory/disk usage
                - log_analysis: Analyzing or searching logs
                - system_info: Getting system information
                - backup_create: Creating backups
                - backup_restore: Restoring from backups
                - backup_status: Checking backup status
                - metrics_query: Querying monitoring metrics
                - alert_manage: Managing alerts
                - performance_analyze: Analyzing performance
                - security_scan: Security scanning or auditing
                - vulnerability_check: Checking for vulnerabilities
                - compliance_audit: Compliance checking
                - unknown: If the command doesn't fit any category
                
                {format_instructions}
                """),
                ("human", "Classify this command: {command}")
            ])
            
            self.classification_chain = (
                self.classification_prompt.partial(
                    format_instructions=self.parser.get_format_instructions()
                ) | self.llm | self.parser
            )
    
    def recognize_intent(self, command: str) -> IntentConfidence:
        """Recognize intent from natural language command"""
        # First try rule-based matching for high confidence
        rule_result = self._match_patterns(command)
        
        if rule_result and rule_result.confidence >= 0.9:
            logger.info(f"High confidence rule match: {rule_result.intent}")
            return rule_result
        
        # If LLM available, use it for complex cases
        if self.llm and (not rule_result or rule_result.confidence < 0.7):
            llm_result = self._classify_with_llm(command)
            
            # Combine results if both available
            if rule_result and llm_result:
                return self._combine_results(rule_result, llm_result, command)
            elif llm_result:
                return llm_result
        
        # Return rule result or unknown
        return rule_result or IntentConfidence(
            intent=CommandIntent.UNKNOWN,
            confidence=0.0,
            evidence=["No matching patterns found"],
            suggested_action="Please clarify your command"
        )
    
    def _match_patterns(self, command: str) -> Optional[IntentConfidence]:
        """Match command against rule patterns"""
        matches = []
        
        for intent, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(command):
                    matches.append((intent, pattern.pattern))
        
        if not matches:
            return None
        
        # If single match, high confidence
        if len(matches) == 1:
            intent, pattern = matches[0]
            return IntentConfidence(
                intent=intent,
                confidence=0.95,
                evidence=[f"Matched pattern: {pattern}"]
            )
        
        # Multiple matches, lower confidence
        intents = {intent for intent, _ in matches}
        if len(intents) == 1:
            # Same intent, multiple patterns
            intent = list(intents)[0]
            return IntentConfidence(
                intent=intent,
                confidence=0.9,
                evidence=[f"Matched {len(matches)} patterns"]
            )
        else:
            # Multiple intents, ambiguous
            primary_intent = matches[0][0]
            return IntentConfidence(
                intent=primary_intent,
                confidence=0.6,
                evidence=[f"Ambiguous: matched {len(intents)} different intents"],
                suggested_action="Please be more specific"
            )
    
    def _classify_with_llm(self, command: str) -> Optional[IntentConfidence]:
        """Classify intent using LLM"""
        try:
            result = self.classification_chain.invoke({"command": command})
            
            # Map string intent to enum
            intent_str = result.intent.upper().replace(" ", "_")
            try:
                intent = CommandIntent[intent_str]
            except KeyError:
                intent = CommandIntent.UNKNOWN
            
            return IntentConfidence(
                intent=intent,
                confidence=result.confidence,
                evidence=[result.reasoning],
                suggested_action=result.ambiguity
            )
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return None
    
    def _combine_results(self, rule_result: IntentConfidence, 
                        llm_result: IntentConfidence, 
                        command: str) -> IntentConfidence:
        """Combine rule and LLM results"""
        # If they agree, boost confidence
        if rule_result.intent == llm_result.intent:
            return IntentConfidence(
                intent=rule_result.intent,
                confidence=min(0.99, (rule_result.confidence + llm_result.confidence) / 1.8),
                evidence=rule_result.evidence + llm_result.evidence
            )
        
        # If they disagree, prefer higher confidence
        if rule_result.confidence > llm_result.confidence + 0.2:
            return rule_result
        elif llm_result.confidence > rule_result.confidence + 0.2:
            return llm_result
        else:
            # Too close, need clarification
            return IntentConfidence(
                intent=llm_result.intent,  # Prefer LLM for complex cases
                confidence=0.5,
                evidence=[
                    f"Rule suggests: {rule_result.intent.value}",
                    f"LLM suggests: {llm_result.intent.value}"
                ],
                suggested_action=f"Did you mean to {rule_result.intent.value} or {llm_result.intent.value}?"
            )
    
    def get_intent_examples(self, intent: CommandIntent) -> List[str]:
        """Get example commands for an intent"""
        examples = {
            CommandIntent.NETWORK_SCAN: [
                "scan network 192.168.1.0/24",
                "discover all devices on the network",
                "find servers in subnet"
            ],
            CommandIntent.DEVICE_STATUS: [
                "check status of server-01",
                "show device health for web-server",
                "is database-01 online?"
            ],
            CommandIntent.CONNECTIVITY_TEST: [
                "ping google.com",
                "test connectivity to 192.168.1.1",
                "can I reach the database server?"
            ],
            CommandIntent.SERVICE_MANAGE: [
                "restart nginx service",
                "stop mysql on server-01",
                "start the web server"
            ],
            CommandIntent.BACKUP_CREATE: [
                "create a backup of the system",
                "backup the main database",
                "take a snapshot of server-01"
            ],
            CommandIntent.PERFORMANCE_ANALYZE: [
                "analyze CPU usage on server-01",
                "why is the database slow?",
                "check performance metrics"
            ]
        }
        
        return examples.get(intent, [])