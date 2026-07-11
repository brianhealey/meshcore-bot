#!/usr/bin/env python3
"""
Tool Registry for LLM Tool Calling

Discovers available commands and generates OpenAI-compatible tool schemas
for use with Ollama's function calling feature.
"""

from typing import Any

from .commands.base_command import BaseCommand


class ToolRegistry:
    """Registry for discovering and converting bot commands into LLM tool schemas.

    This class bridges the gap between the bot's command system and LLM tool calling
    by generating OpenAI-compatible function schemas from command metadata.
    """

    def __init__(self, bot: Any, command_manager: Any) -> None:
        """Initialize the tool registry.

        Args:
            bot: The MeshCoreBot instance.
            command_manager: The CommandManager instance with loaded commands.
        """
        self.bot = bot
        self.command_manager = command_manager
        self.logger = bot.logger

        # Load whitelist from config
        self.available_tools = self._load_available_tools()

    def _load_available_tools(self) -> set[str]:
        """Load the list of whitelisted tools from config.

        Returns:
            Set of command names that are enabled for LLM tool calling.
        """
        tools_str = self.bot.config.get('LLM_Command', 'available_tools', fallback='wx,airplanes,satpass,path,stats,moon,sun,aurora')
        # Parse comma-separated list and strip whitespace
        tools = {tool.strip() for tool in tools_str.split(',') if tool.strip()}
        self.logger.debug(
            f"[TOOL_REGISTRY] Loaded available tools from config: {sorted(tools)}"
        )
        return tools

    def get_available_commands(self) -> dict[str, BaseCommand]:
        """Get all commands that are whitelisted for tool calling.

        Returns:
            Dictionary mapping command names to command instances.
        """
        available = {}
        for cmd_name, cmd_instance in self.command_manager.commands.items():
            if cmd_name in self.available_tools:
                available[cmd_name] = cmd_instance
        return available

    def generate_tool_schema(self, command: BaseCommand) -> dict[str, Any]:
        """Generate OpenAI-compatible function schema for a command.

        Args:
            command: The command instance to generate schema for.

        Returns:
            Dictionary in OpenAI function schema format.
        """
        # Start with basic schema structure
        schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": command.name,
                "description": command.short_description or command.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }

        # Build parameters from command.parameters metadata
        for param in command.parameters:
            param_name = param.get("name", "")
            param_desc = param.get("description", "")
            param_required = param.get("required", False)
            param_type = param.get("type", "string")
            param_enum = param.get("enum", None)

            if param_name:
                prop: dict[str, Any] = {
                    "type": param_type,
                    "description": param_desc
                }

                # Add enum if specified
                if param_enum:
                    prop["enum"] = param_enum

                schema["function"]["parameters"]["properties"][param_name] = prop

                # Track required parameters
                if param_required:
                    schema["function"]["parameters"]["required"].append(param_name)

        return schema

    def get_all_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible schemas for all available tools.

        Returns:
            List of tool schemas in OpenAI function format.
        """
        schemas = []
        available_cmds = self.get_available_commands()
        self.logger.debug(
            f"[TOOL_REGISTRY] Generating schemas for {len(available_cmds)} tools: "
            f"{list(available_cmds.keys())}"
        )
        for cmd_name, cmd_instance in available_cmds.items():
            schema = self.generate_tool_schema(cmd_instance)
            schemas.append(schema)
            self.logger.debug(
                f"[TOOL_REGISTRY] Generated schema for '{cmd_name}': "
                f"desc='{schema.get('function', {}).get('description', '')[:50]}...'"
            )
        return schemas
