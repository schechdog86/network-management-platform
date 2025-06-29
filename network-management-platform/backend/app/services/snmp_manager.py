"""
SNMP manager for network device monitoring
This is a wrapper/alias for snmp_service for backward compatibility
"""

from .snmp_service import *

# Create an alias for the global service instance
snmp_manager = snmp_service