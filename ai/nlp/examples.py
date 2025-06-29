"""
Example usage of the NLP command processing system
"""

import asyncio
from datetime import datetime

from langchain_openai import ChatOpenAI

from .command_parser import CommandParser, ValidationContext
from .command_executor import CommandExecutor, ExecutionContext


def progress_callback(message: str, progress: float):
    """Example progress callback"""
    print(f"[{progress:.0%}] {message}")


async def example_basic_usage():
    """Basic usage example"""
    print("=== Basic NLP Command Processing Example ===\n")
    
    # Initialize with LLM
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    parser = CommandParser(llm)
    executor = CommandExecutor()
    
    # Example commands
    commands = [
        "scan network 192.168.1.0/24",
        "check status of web-server",
        "restart nginx service",
        "ping google.com",
        "analyze CPU performance for last 24 hours",
        "create a full backup of database server"
    ]
    
    for command in commands:
        print(f"\n📝 Command: '{command}'")
        
        # Parse command
        result = parser.parse_command(command)
        
        # Display formatted result
        print(parser.format_response(result))
        
        # If successful and executable, show preview
        if result.success and result.command.executable:
            preview = parser.get_command_preview(result.command)
            print(f"\n🔍 Preview: {preview}")


async def example_with_context():
    """Example with context and validation"""
    print("\n=== Context-Aware Command Processing ===\n")
    
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    parser = CommandParser(llm)
    
    # Set up context
    context = {
        'default_device': 'server-01',
        'user_role': 'operator',
        'production': True
    }
    
    validation_context = ValidationContext(
        user_role='operator',
        time_of_day=datetime.now(),
        production_environment=True,
        maintenance_window=False
    )
    
    # Command that needs context
    command = "check CPU usage"  # No device specified
    
    print(f"📝 Command: '{command}'")
    print(f"📋 Context: default_device='{context['default_device']}'")
    
    result = parser.parse_command(command, context, validation_context)
    print(parser.format_response(result))


async def example_high_risk_command():
    """Example of high-risk command handling"""
    print("\n=== High-Risk Command Handling ===\n")
    
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    parser = CommandParser(llm)
    executor = CommandExecutor()
    
    # High-risk command during business hours
    command = "restart mysql service on production-db"
    
    validation_context = ValidationContext(
        user_role='operator',
        time_of_day=datetime(2024, 1, 15, 14, 30),  # 2:30 PM
        production_environment=True,
        maintenance_window=False
    )
    
    print(f"📝 Command: '{command}'")
    print(f"⏰ Time: Business hours (2:30 PM)")
    print(f"🏭 Environment: Production")
    
    result = parser.parse_command(command, validation_context=validation_context)
    print(parser.format_response(result))
    
    # Show what happens with confirmation
    if result.success and result.command.confirmation_required:
        print("\n✅ User provides confirmation...")
        
        # Execute with dry run first
        exec_context = ExecutionContext(
            dry_run=True,
            progress_callback=progress_callback
        )
        
        exec_result = await executor.execute_command(result.command, exec_context)
        print(f"\n🔧 Dry Run Result: {exec_result.output}")


async def example_blocked_command():
    """Example of blocked command"""
    print("\n=== Blocked Command Example ===\n")
    
    parser = CommandParser()  # No LLM needed for this example
    
    # Dangerous command
    command = "rm -rf /"
    
    print(f"📝 Command: '{command}'")
    
    result = parser.parse_command(command)
    print(parser.format_response(result))


async def example_full_execution():
    """Full execution example"""
    print("\n=== Full Command Execution ===\n")
    
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    parser = CommandParser(llm)
    executor = CommandExecutor()
    
    # Safe command for execution
    command = "check network connectivity to 8.8.8.8"
    
    print(f"📝 Command: '{command}'")
    
    # Parse
    parse_result = parser.parse_command(command)
    print(parser.format_response(parse_result))
    
    if parse_result.success and parse_result.command.executable:
        print("\n🚀 Executing command...")
        
        # Execute with progress tracking
        exec_context = ExecutionContext(
            progress_callback=progress_callback,
            timeout=30
        )
        
        exec_result = await executor.execute_command(
            parse_result.command, 
            exec_context
        )
        
        print(f"\n✅ Execution {'succeeded' if exec_result.success else 'failed'}")
        print(f"⏱️  Time: {exec_result.execution_time:.2f}s")
        
        if exec_result.success:
            print(f"\n📤 Output:\n{exec_result.output}")
        else:
            print(f"\n❌ Error: {exec_result.error}")
        
        # Show audit log
        print(f"\n📋 Audit Log:")
        print(f"   Timestamp: {exec_result.audit_log['timestamp']}")
        print(f"   Risk Level: {exec_result.audit_log['risk_level']}")
        print(f"   Intent: {exec_result.audit_log['intent']}")


async def example_help_system():
    """Example of help system"""
    print("\n=== Help System Example ===\n")
    
    parser = CommandParser()
    
    # General help
    print("📚 General Help:")
    print(parser.get_help())
    
    # Topic-specific help
    print("\n📚 Network Operations Help:")
    print(parser.get_help('network'))
    
    print("\n📚 Safety Features Help:")
    print(parser.get_help('safety'))


async def example_ambiguous_command():
    """Example of handling ambiguous commands"""
    print("\n=== Ambiguous Command Handling ===\n")
    
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    parser = CommandParser(llm)
    
    # Ambiguous command
    command = "check the server"  # What to check? Which server?
    
    print(f"📝 Command: '{command}'")
    
    result = parser.parse_command(command)
    print(parser.format_response(result))


async def main():
    """Run all examples"""
    examples = [
        example_basic_usage,
        example_with_context,
        example_high_risk_command,
        example_blocked_command,
        example_full_execution,
        example_help_system,
        example_ambiguous_command
    ]
    
    for example in examples:
        await example()
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    # Note: Requires OpenAI API key to be set
    asyncio.run(main())