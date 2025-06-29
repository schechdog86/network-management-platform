"""
Entity Extraction for Network Commands

Extracts entities (devices, IPs, services, etc.) from natural language commands
using 2025 best practices:
- Hybrid NER with custom IT terminology
- Context-aware extraction
- Validation and normalization
"""

import re
import ipaddress
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Types of entities in network commands"""
    DEVICE_NAME = "device_name"
    IP_ADDRESS = "ip_address"
    IP_RANGE = "ip_range"
    PORT = "port"
    SERVICE_NAME = "service_name"
    TIME_RANGE = "time_range"
    FILE_PATH = "file_path"
    USER = "user"
    METRIC_TYPE = "metric_type"
    ACTION = "action"
    BACKUP_TYPE = "backup_type"
    SEVERITY = "severity"
    PROTOCOL = "protocol"


@dataclass
class ExtractedEntity:
    """Extracted entity with metadata"""
    entity_type: EntityType
    value: Any
    normalized_value: Any
    confidence: float
    position: Optional[Tuple[int, int]] = None
    context: Optional[str] = None


class NetworkCommandEntities(BaseModel):
    """Schema for LLM entity extraction"""
    devices: List[str] = Field(default_factory=list, description="Device names or hostnames")
    ip_addresses: List[str] = Field(default_factory=list, description="IP addresses")
    ip_ranges: List[str] = Field(default_factory=list, description="IP ranges or subnets")
    ports: List[int] = Field(default_factory=list, description="Port numbers")
    services: List[str] = Field(default_factory=list, description="Service names")
    time_ranges: List[str] = Field(default_factory=list, description="Time ranges or durations")
    file_paths: List[str] = Field(default_factory=list, description="File or directory paths")
    metrics: List[str] = Field(default_factory=list, description="Metric types (cpu, memory, etc.)")
    actions: List[str] = Field(default_factory=list, description="Actions to perform")
    
    @validator('ip_addresses')
    def validate_ips(cls, v):
        """Validate IP addresses"""
        valid_ips = []
        for ip in v:
            try:
                ipaddress.ip_address(ip)
                valid_ips.append(ip)
            except:
                logger.warning(f"Invalid IP address: {ip}")
        return valid_ips
    
    @validator('ports')
    def validate_ports(cls, v):
        """Validate port numbers"""
        return [p for p in v if 0 < p <= 65535]


class EntityExtractor:
    """Advanced entity extractor for network commands"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self._init_patterns()
        self._init_dictionaries()
        self._init_llm_extractor()
    
    def _init_patterns(self):
        """Initialize regex patterns for entity extraction"""
        self.patterns = {
            EntityType.IP_ADDRESS: re.compile(
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
            ),
            EntityType.IP_RANGE: re.compile(
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)/\d{1,2}\b'
            ),
            EntityType.PORT: re.compile(
                r'\b(?:port\s+)?(\d{1,5})\b'
            ),
            EntityType.TIME_RANGE: re.compile(
                r'\b(\d+)\s*(second|minute|hour|day|week|month)s?\b|\b(last|past|next)\s+\d+\s*(hour|day|week)s?\b'
            ),
            EntityType.FILE_PATH: re.compile(
                r'(?:/[\w\-\.]+)+/?|(?:[a-zA-Z]:\\(?:[\w\-\.]+\\)*[\w\-\.]*)'
            ),
            EntityType.DEVICE_NAME: re.compile(
                r'\b(?:server|host|device|machine|node|system)[-_]?\d*\w*\b',
                re.IGNORECASE
            )
        }
    
    def _init_dictionaries(self):
        """Initialize domain-specific dictionaries"""
        self.dictionaries = {
            EntityType.SERVICE_NAME: {
                'web': ['nginx', 'apache', 'httpd', 'apache2'],
                'database': ['mysql', 'postgresql', 'postgres', 'mariadb', 'mongodb', 'redis'],
                'mail': ['postfix', 'sendmail', 'dovecot', 'exim'],
                'monitoring': ['prometheus', 'grafana', 'nagios', 'zabbix'],
                'container': ['docker', 'containerd', 'kubernetes', 'k8s'],
                'network': ['dhcp', 'dns', 'bind', 'dnsmasq', 'iptables', 'firewalld'],
                'security': ['sshd', 'ssh', 'fail2ban', 'ufw', 'selinux']
            },
            EntityType.METRIC_TYPE: [
                'cpu', 'memory', 'disk', 'network', 'bandwidth', 'latency',
                'iops', 'throughput', 'connections', 'requests', 'errors'
            ],
            EntityType.ACTION: [
                'start', 'stop', 'restart', 'reload', 'enable', 'disable',
                'check', 'monitor', 'analyze', 'scan', 'backup', 'restore'
            ],
            EntityType.BACKUP_TYPE: [
                'full', 'incremental', 'differential', 'snapshot', 'system',
                'database', 'configuration', 'user-data'
            ],
            EntityType.SEVERITY: [
                'critical', 'error', 'warning', 'info', 'debug',
                'high', 'medium', 'low'
            ],
            EntityType.PROTOCOL: [
                'tcp', 'udp', 'icmp', 'http', 'https', 'ssh', 'ftp',
                'smtp', 'dns', 'dhcp', 'snmp'
            ]
        }
        
        # Build reverse lookup for quick entity type identification
        self.reverse_lookup = {}
        for entity_type, values in self.dictionaries.items():
            if isinstance(values, dict):
                for category, items in values.items():
                    for item in items:
                        self.reverse_lookup[item.lower()] = entity_type
            else:
                for item in values:
                    self.reverse_lookup[item.lower()] = entity_type
    
    def _init_llm_extractor(self):
        """Initialize LLM-based entity extractor"""
        if self.llm:
            self.parser = PydanticOutputParser(pydantic_object=NetworkCommandEntities)
            
            self.extraction_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at extracting entities from network and system administration commands.
                
                Extract the following types of entities:
                - Device names (server-01, web-server, db-host, etc.)
                - IP addresses (192.168.1.1, 10.0.0.5, etc.)
                - IP ranges (192.168.1.0/24, 10.0.0.0/16, etc.)
                - Port numbers (80, 443, 22, 3306, etc.)
                - Service names (nginx, mysql, docker, etc.)
                - Time ranges (last 24 hours, past week, etc.)
                - File paths (/var/log/syslog, /etc/nginx/nginx.conf, etc.)
                - Metrics (cpu, memory, disk, network, etc.)
                - Actions (start, stop, restart, check, etc.)
                
                {format_instructions}
                """),
                ("human", "Extract entities from: {command}")
            ])
            
            self.extraction_chain = (
                self.extraction_prompt.partial(
                    format_instructions=self.parser.get_format_instructions()
                ) | self.llm | self.parser
            )
    
    def extract_entities(self, command: str, context: Optional[Dict[str, Any]] = None) -> List[ExtractedEntity]:
        """Extract all entities from command"""
        entities = []
        
        # Rule-based extraction
        rule_entities = self._extract_with_rules(command)
        entities.extend(rule_entities)
        
        # Dictionary-based extraction
        dict_entities = self._extract_with_dictionaries(command)
        entities.extend(dict_entities)
        
        # LLM-based extraction for complex cases
        if self.llm:
            llm_entities = self._extract_with_llm(command, context)
            entities.extend(llm_entities)
        
        # Deduplicate and merge entities
        entities = self._merge_entities(entities)
        
        # Apply context if available
        if context:
            entities = self._apply_context(entities, context)
        
        return entities
    
    def _extract_with_rules(self, command: str) -> List[ExtractedEntity]:
        """Extract entities using regex patterns"""
        entities = []
        
        for entity_type, pattern in self.patterns.items():
            for match in pattern.finditer(command):
                value = match.group(0)
                normalized = self._normalize_entity(entity_type, value)
                
                entities.append(ExtractedEntity(
                    entity_type=entity_type,
                    value=value,
                    normalized_value=normalized,
                    confidence=0.9,
                    position=(match.start(), match.end())
                ))
        
        return entities
    
    def _extract_with_dictionaries(self, command: str) -> List[ExtractedEntity]:
        """Extract entities using domain dictionaries"""
        entities = []
        words = command.lower().split()
        
        for i, word in enumerate(words):
            # Clean word of punctuation
            clean_word = re.sub(r'[^\w\-]', '', word)
            
            if clean_word in self.reverse_lookup:
                entity_type = self.reverse_lookup[clean_word]
                
                # Get original case from command
                start_pos = command.lower().find(word)
                if start_pos != -1:
                    original_value = command[start_pos:start_pos + len(word)]
                else:
                    original_value = word
                
                entities.append(ExtractedEntity(
                    entity_type=entity_type,
                    value=original_value,
                    normalized_value=clean_word,
                    confidence=0.95,
                    context=self._get_word_context(words, i)
                ))
        
        return entities
    
    def _extract_with_llm(self, command: str, context: Optional[Dict[str, Any]]) -> List[ExtractedEntity]:
        """Extract entities using LLM"""
        try:
            result = self.extraction_chain.invoke({"command": command})
            entities = []
            
            # Convert LLM results to ExtractedEntity objects
            for device in result.devices:
                entities.append(ExtractedEntity(
                    entity_type=EntityType.DEVICE_NAME,
                    value=device,
                    normalized_value=device.lower(),
                    confidence=0.8
                ))
            
            for ip in result.ip_addresses:
                entities.append(ExtractedEntity(
                    entity_type=EntityType.IP_ADDRESS,
                    value=ip,
                    normalized_value=ip,
                    confidence=0.9
                ))
            
            for ip_range in result.ip_ranges:
                entities.append(ExtractedEntity(
                    entity_type=EntityType.IP_RANGE,
                    value=ip_range,
                    normalized_value=ip_range,
                    confidence=0.9
                ))
            
            for port in result.ports:
                entities.append(ExtractedEntity(
                    entity_type=EntityType.PORT,
                    value=str(port),
                    normalized_value=port,
                    confidence=0.9
                ))
            
            for service in result.services:
                entities.append(ExtractedEntity(
                    entity_type=EntityType.SERVICE_NAME,
                    value=service,
                    normalized_value=service.lower(),
                    confidence=0.85
                ))
            
            for time_range in result.time_ranges:
                entities.append(ExtractedEntity(
                    entity_type=EntityType.TIME_RANGE,
                    value=time_range,
                    normalized_value=self._normalize_time_range(time_range),
                    confidence=0.8
                ))
            
            return entities
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []
    
    def _normalize_entity(self, entity_type: EntityType, value: str) -> Any:
        """Normalize entity value"""
        if entity_type == EntityType.IP_ADDRESS:
            try:
                return str(ipaddress.ip_address(value))
            except:
                return value
        
        elif entity_type == EntityType.IP_RANGE:
            try:
                return str(ipaddress.ip_network(value, strict=False))
            except:
                return value
        
        elif entity_type == EntityType.PORT:
            # Extract just the number
            match = re.search(r'\d+', value)
            if match:
                return int(match.group())
            return value
        
        elif entity_type in [EntityType.DEVICE_NAME, EntityType.SERVICE_NAME]:
            return value.lower().replace('-', '_')
        
        elif entity_type == EntityType.TIME_RANGE:
            return self._normalize_time_range(value)
        
        return value
    
    def _normalize_time_range(self, time_str: str) -> str:
        """Normalize time range to standard format"""
        # Convert various formats to standard format
        replacements = {
            'last': 'past',
            'mins': 'minutes',
            'min': 'minutes',
            'hrs': 'hours',
            'hr': 'hours',
            'd': 'days'
        }
        
        normalized = time_str.lower()
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        return normalized
    
    def _merge_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Merge duplicate entities, keeping highest confidence"""
        merged = {}
        
        for entity in entities:
            key = (entity.entity_type, entity.normalized_value)
            
            if key not in merged or entity.confidence > merged[key].confidence:
                merged[key] = entity
        
        return list(merged.values())
    
    def _apply_context(self, entities: List[ExtractedEntity], context: Dict[str, Any]) -> List[ExtractedEntity]:
        """Apply context to improve entity extraction"""
        # If context provides default values, add them if not found
        if 'default_device' in context:
            has_device = any(e.entity_type == EntityType.DEVICE_NAME for e in entities)
            if not has_device:
                entities.append(ExtractedEntity(
                    entity_type=EntityType.DEVICE_NAME,
                    value=context['default_device'],
                    normalized_value=context['default_device'].lower(),
                    confidence=0.7,
                    context="Added from context"
                ))
        
        return entities
    
    def _get_word_context(self, words: List[str], index: int, window: int = 2) -> str:
        """Get context words around a position"""
        start = max(0, index - window)
        end = min(len(words), index + window + 1)
        return ' '.join(words[start:end])
    
    def validate_entities(self, entities: List[ExtractedEntity]) -> Tuple[List[ExtractedEntity], List[str]]:
        """Validate extracted entities and return errors"""
        valid_entities = []
        errors = []
        
        for entity in entities:
            if entity.entity_type == EntityType.IP_ADDRESS:
                try:
                    ipaddress.ip_address(entity.value)
                    valid_entities.append(entity)
                except:
                    errors.append(f"Invalid IP address: {entity.value}")
            
            elif entity.entity_type == EntityType.IP_RANGE:
                try:
                    ipaddress.ip_network(entity.value, strict=False)
                    valid_entities.append(entity)
                except:
                    errors.append(f"Invalid IP range: {entity.value}")
            
            elif entity.entity_type == EntityType.PORT:
                port = entity.normalized_value
                if isinstance(port, int) and 0 < port <= 65535:
                    valid_entities.append(entity)
                else:
                    errors.append(f"Invalid port number: {entity.value}")
            
            else:
                # Other entities assumed valid
                valid_entities.append(entity)
        
        return valid_entities, errors