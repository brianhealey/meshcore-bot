#!/usr/bin/env python3
"""
Tool Registry for LLM Tool Calling

Discovers available commands and generates OpenAI-compatible tool schemas
for use with Ollama's function calling feature.

Includes keyword-based intent filtering to prevent incorrect tool invocations.
"""

import re
from typing import Any

from .commands.base_command import BaseCommand

# Tool-specific trigger keywords for intent detection.
# Tools will only be offered to the LLM if the query contains at least one trigger keyword.
# This prevents false positives like "are dolphins intelligent" triggering weather.
# NOTE: Use specific, unambiguous keywords. Avoid generic terms like "hot" or "cold"
# that could match non-weather contexts (e.g., "hot dog", "cold pizza").
TOOL_TRIGGER_KEYWORDS: dict[str, set[str]] = {
    "wx": {
        "weather", "forecast", "temperature", "rain", "raining", "snow", "snowing",
        "snowy", "wind", "windy", "humidity", "precipitation", "storm", "stormy",
        "sunny", "cloudy", "clouds", "freezing", "climate", "wx", "celsius",
        "fahrenheit", "degrees outside", "thunderstorm", "hail", "fog", "foggy",
        "mist", "misty", "overcast", "clear skies", "high today", "low tonight",
    },
    "airplanes": {
        "airplane", "aircraft", "plane", "flight", "flying", "aviation",
        "overhead", "adsb", "ads-b", "airline", "jet", "helicopter",
        "chopper", "airspace", "altitude", "squawk",
    },
    "satpass": {
        "satellite", "iss", "space station", "orbit", "pass", "visible",
        "starlink", "norad", "satpass", "hubble", "tiangong",
    },
    "path": {
        "path", "route", "hop", "hops", "routing", "mesh path", "relay",
        "repeater path", "how to reach", "connection path",
    },
    "stats": {
        "stats", "statistics", "activity", "usage", "messages", "channels",
        "network activity", "traffic", "volume", "busy", "active nodes",
    },
    "moon": {
        "moon", "lunar", "moonrise", "moonset", "moon phase", "full moon",
        "new moon", "crescent", "waxing", "waning", "moonlight",
    },
    "sun": {
        "sun", "sunrise", "sunset", "solar", "daylight", "dusk", "dawn",
        "golden hour", "blue hour", "sunlight",
    },
    "aurora": {
        "aurora", "northern lights", "southern lights", "borealis",
        "australis", "geomagnetic", "kp index", "solar wind",
    },
    "sql_query": {
        "repeater", "repeaters", "contact", "contacts", "node", "nodes",
        "closest", "nearest", "farthest", "distance", "heard", "seen",
        "database", "query", "count", "total", "average", "statistics",
        "message", "messages", "sent", "received", "advertisement",
        "advertisements", "adverts", "how many", "list all", "show all",
        "connection", "connections", "topology", "mesh data",
    },
}


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

    def get_tools_matching_query(self, query: str) -> set[str]:
        """Determine which tools are relevant to the user's query.

        Uses keyword matching to identify which tools should be offered to the LLM.
        This prevents incorrect tool invocations for unrelated queries.

        Args:
            query: The user's query text.

        Returns:
            Set of tool names that match the query's intent.
        """
        query_lower = query.lower()
        matching_tools: set[str] = set()

        for tool_name, keywords in TOOL_TRIGGER_KEYWORDS.items():
            # Skip tools that aren't in the available tools list
            if tool_name not in self.available_tools:
                continue

            # Check if any keyword matches the query
            for keyword in keywords:
                # Use word boundary matching for single words,
                # substring matching for multi-word phrases
                if ' ' in keyword:
                    # Multi-word phrase: use substring match
                    if keyword in query_lower:
                        matching_tools.add(tool_name)
                        self.logger.debug(
                            f"[TOOL_REGISTRY] Query matches tool '{tool_name}' "
                            f"via phrase '{keyword}'"
                        )
                        break
                else:
                    # Single word: use word boundary match to avoid false positives
                    # e.g., "hot dog" should not match "hot" for weather
                    pattern = rf'\b{re.escape(keyword)}\b'
                    if re.search(pattern, query_lower):
                        matching_tools.add(tool_name)
                        self.logger.debug(
                            f"[TOOL_REGISTRY] Query matches tool '{tool_name}' "
                            f"via keyword '{keyword}'"
                        )
                        break

        return matching_tools

    def get_tool_schemas_for_query(self, query: str) -> list[dict[str, Any]]:
        """Get tool schemas filtered by query intent.

        Only returns schemas for tools that are relevant to the user's query,
        based on keyword matching. This prevents the LLM from being offered
        irrelevant tools.

        Args:
            query: The user's query text.

        Returns:
            List of tool schemas in OpenAI function format, filtered by relevance.
        """
        matching_tools = self.get_tools_matching_query(query)

        if not matching_tools:
            self.logger.info(
                f"[TOOL_REGISTRY] No tools match query '{query[:50]}...' - "
                "LLM will respond directly without tool options"
            )
            return []

        self.logger.info(
            f"[TOOL_REGISTRY] Query '{query[:50]}...' matches tools: {sorted(matching_tools)}"
        )

        schemas = []
        available_cmds = self.get_available_commands()

        for cmd_name, cmd_instance in available_cmds.items():
            if cmd_name in matching_tools:
                schema = self.generate_tool_schema(cmd_instance)
                schemas.append(schema)
                self.logger.debug(
                    f"[TOOL_REGISTRY] Including schema for '{cmd_name}': "
                    f"desc='{schema.get('function', {}).get('description', '')[:50]}...'"
                )

        return schemas

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
