#!/usr/bin/env python3
"""
Tool Executor for LLM Tool Calling

Executes tool calls from LLM by creating synthetic MeshMessages and
executing commands via CommandManager.
"""

import asyncio
from typing import Any

from .models import MeshMessage


class ToolExecutor:
    """Executor for LLM tool calls.

    This class parses tool calls from LLM responses and executes commands
    by creating synthetic MeshMessages and routing through CommandManager.
    """

    def __init__(self, bot: Any, command_manager: Any, tool_registry: Any) -> None:
        """Initialize the tool executor.

        Args:
            bot: The MeshCoreBot instance.
            command_manager: The CommandManager instance with loaded commands.
            tool_registry: The ToolRegistry instance for validation.
        """
        self.bot = bot
        self.command_manager = command_manager
        self.tool_registry = tool_registry
        self.logger = bot.logger

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        original_message: MeshMessage,
        timeout: int = 10
    ) -> str:
        """Execute a tool call by routing through command system.

        Args:
            tool_name: Name of the command to execute.
            arguments: Dictionary of command arguments from LLM.
            original_message: The original MeshMessage that triggered the LLM query.
            timeout: Maximum execution time in seconds (default: 10).

        Returns:
            str: Command output, or error message if execution failed.
        """
        # Validate tool is in whitelist
        if tool_name not in self.tool_registry.available_tools:
            error_msg = f"Tool '{tool_name}' is not available. Available tools: {', '.join(sorted(self.tool_registry.available_tools))}"
            self.logger.warning(error_msg)
            return error_msg

        # Get the command instance
        command = self.command_manager.commands.get(tool_name)
        if not command:
            error_msg = f"Command '{tool_name}' not found in command registry"
            self.logger.error(error_msg)
            return error_msg

        # Build synthetic message content from arguments
        # For most commands, we just need to construct the command line from arguments
        message_content = self._build_message_content(tool_name, arguments)

        # Create synthetic MeshMessage from original message + synthetic content
        synthetic_message = MeshMessage(
            content=message_content,
            sender_id=original_message.sender_id,
            sender_pubkey=original_message.sender_pubkey,
            channel=original_message.channel,
            is_dm=original_message.is_dm,
            hops=original_message.hops,
            path=original_message.path,
            timestamp=original_message.timestamp,
            snr=original_message.snr,
            rssi=original_message.rssi,
            elapsed=original_message.elapsed,
            routing_info=original_message.routing_info,
            reply_scope=original_message.reply_scope,
            content_lower=message_content.lower()
        )

        # Execute command with timeout
        try:
            self.logger.info(f"Executing tool '{tool_name}' with arguments: {arguments}")

            # Clear last_response before execution
            if hasattr(command, 'last_response'):
                command.last_response = None
            if hasattr(self.command_manager, '_last_response'):
                self.command_manager._last_response = None

            # Execute with timeout
            success = await asyncio.wait_for(
                command.execute(synthetic_message),
                timeout=timeout
            )

            # Small delay to ensure send_response has completed
            await asyncio.sleep(0.1)

            # Capture command output from last_response
            output = None
            if hasattr(command, 'last_response') and command.last_response:
                output = command.last_response
            elif hasattr(self.command_manager, '_last_response') and self.command_manager._last_response:
                output = self.command_manager._last_response

            if output:
                self.logger.debug(f"Tool '{tool_name}' returned: {output[:100]}...")
                return str(output)
            elif success:
                # Command succeeded but no output captured
                return f"Command '{tool_name}' executed successfully (no output)"
            else:
                return f"Command '{tool_name}' failed to execute"

        except asyncio.TimeoutError:
            error_msg = f"Tool '{tool_name}' execution timed out after {timeout} seconds"
            self.logger.warning(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error executing tool '{tool_name}': {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return error_msg

    def _build_message_content(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Build message content from tool name and arguments.

        Args:
            tool_name: Name of the command.
            arguments: Dictionary of command arguments.

        Returns:
            str: Message content string (e.g., "!wx seattle").
        """
        # Get command prefix from config
        prefix = self.bot.config.get('Bot', 'command_prefix', fallback='!')

        # Start with command name
        parts = [f"{prefix}{tool_name}"]

        # Get command instance to check parameter metadata
        command = self.command_manager.commands.get(tool_name)
        if command and hasattr(command, 'parameters') and command.parameters:
            # Use parameter metadata to order arguments correctly
            for param in command.parameters:
                param_name = param.get('name', '')
                if param_name in arguments:
                    value = arguments[param_name]
                    # Add value to parts (handle different types)
                    if isinstance(value, (list, tuple)):
                        parts.extend(str(v) for v in value)
                    else:
                        parts.append(str(value))
        else:
            # No parameter metadata - just append all argument values in order
            for key, value in arguments.items():
                if isinstance(value, (list, tuple)):
                    parts.extend(str(v) for v in value)
                else:
                    parts.append(str(value))

        return ' '.join(parts)
