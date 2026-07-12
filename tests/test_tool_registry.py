#!/usr/bin/env python3
"""Tests for modules/tool_registry.py — ToolRegistry."""

import configparser
from unittest.mock import MagicMock, Mock

import pytest

from modules.tool_registry import ToolRegistry


@pytest.fixture
def mock_bot():
    """Create a mock bot with config."""
    bot = MagicMock()
    bot.logger = Mock()
    bot.config = configparser.ConfigParser()
    bot.config.add_section('LLM_Command')
    bot.config.set('LLM_Command', 'available_tools', 'wx,airplanes,satpass,path,stats')
    return bot


@pytest.fixture
def mock_command_manager():
    """Create a mock CommandManager with test commands."""
    manager = MagicMock()

    # Create mock commands with proper metadata
    wx_command = MagicMock()
    wx_command.name = "wx"
    wx_command.description = "Get weather information"
    wx_command.short_description = "Get weather for a location"
    wx_command.parameters = [
        {"name": "location", "description": "US zip code or city name", "required": True, "type": "string"},
        {"name": "forecast_type", "description": "Forecast type: current, tomorrow, 7d, hourly", "required": False, "type": "string", "enum": ["current", "tomorrow", "7d", "hourly"]}
    ]

    airplanes_command = MagicMock()
    airplanes_command.name = "airplanes"
    airplanes_command.description = "Get aircraft overhead"
    airplanes_command.short_description = "Get information about nearby aircraft using ADS-B data"
    airplanes_command.parameters = [
        {"name": "radius", "description": "Search radius in nautical miles", "required": False, "type": "number"}
    ]

    path_command = MagicMock()
    path_command.name = "path"
    path_command.description = "Analyze mesh network path"
    path_command.short_description = "Analyze mesh network path to a destination node"
    path_command.parameters = [
        {"name": "destination", "description": "Destination node ID or name", "required": True, "type": "string"}
    ]

    # Command not in whitelist
    help_command = MagicMock()
    help_command.name = "help"
    help_command.description = "Get help"
    help_command.short_description = "Get help on bot commands"
    help_command.parameters = []

    manager.commands = {
        "wx": wx_command,
        "airplanes": airplanes_command,
        "path": path_command,
        "help": help_command
    }

    return manager


@pytest.fixture
def tool_registry(mock_bot, mock_command_manager):
    """Create a ToolRegistry instance."""
    return ToolRegistry(mock_bot, mock_command_manager)


class TestToolRegistryInit:
    """Tests for ToolRegistry initialization."""

    def test_loads_available_tools_from_config(self, mock_bot, mock_command_manager):
        """Test that available_tools is loaded from config."""
        registry = ToolRegistry(mock_bot, mock_command_manager)
        assert registry.available_tools == {"wx", "airplanes", "satpass", "path", "stats"}

    def test_handles_empty_config(self, mock_bot, mock_command_manager):
        """Test that empty config falls back to default tools."""
        mock_bot.config.set('LLM_Command', 'available_tools', '')
        registry = ToolRegistry(mock_bot, mock_command_manager)
        assert registry.available_tools == set()

    def test_strips_whitespace_from_tool_names(self, mock_bot, mock_command_manager):
        """Test that tool names are stripped of whitespace."""
        mock_bot.config.set('LLM_Command', 'available_tools', ' wx , airplanes , path ')
        registry = ToolRegistry(mock_bot, mock_command_manager)
        assert registry.available_tools == {"wx", "airplanes", "path"}


class TestGetAvailableCommands:
    """Tests for get_available_commands method."""

    def test_returns_only_whitelisted_commands(self, tool_registry, mock_command_manager):
        """Test that only whitelisted commands are returned."""
        available = tool_registry.get_available_commands()
        assert "wx" in available
        assert "airplanes" in available
        assert "path" in available
        assert "help" not in available  # Not in whitelist

    def test_returns_command_instances(self, tool_registry, mock_command_manager):
        """Test that actual command instances are returned."""
        available = tool_registry.get_available_commands()
        assert available["wx"] is mock_command_manager.commands["wx"]
        assert available["airplanes"] is mock_command_manager.commands["airplanes"]

    def test_returns_empty_dict_when_no_commands_match(self, tool_registry, mock_command_manager):
        """Test that empty dict is returned when no commands match whitelist."""
        tool_registry.available_tools = {"nonexistent"}
        available = tool_registry.get_available_commands()
        assert available == {}


class TestGenerateToolSchema:
    """Tests for generate_tool_schema method."""

    def test_generates_basic_schema_structure(self, tool_registry, mock_command_manager):
        """Test that schema has correct OpenAI function format."""
        wx_cmd = mock_command_manager.commands["wx"]
        schema = tool_registry.generate_tool_schema(wx_cmd)

        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "wx"
        assert schema["function"]["description"] == "Get weather for a location"

    def test_includes_required_parameters(self, tool_registry, mock_command_manager):
        """Test that required parameters are marked correctly."""
        wx_cmd = mock_command_manager.commands["wx"]
        schema = tool_registry.generate_tool_schema(wx_cmd)

        params = schema["function"]["parameters"]
        assert "location" in params["properties"]
        assert "location" in params["required"]
        assert params["properties"]["location"]["type"] == "string"
        assert params["properties"]["location"]["description"] == "US zip code or city name"

    def test_includes_optional_parameters(self, tool_registry, mock_command_manager):
        """Test that optional parameters are included but not required."""
        wx_cmd = mock_command_manager.commands["wx"]
        schema = tool_registry.generate_tool_schema(wx_cmd)

        params = schema["function"]["parameters"]
        assert "forecast_type" in params["properties"]
        assert "forecast_type" not in params["required"]
        assert params["properties"]["forecast_type"]["type"] == "string"

    def test_includes_enum_for_parameters(self, tool_registry, mock_command_manager):
        """Test that enum values are included when specified."""
        wx_cmd = mock_command_manager.commands["wx"]
        schema = tool_registry.generate_tool_schema(wx_cmd)

        forecast_type = schema["function"]["parameters"]["properties"]["forecast_type"]
        assert "enum" in forecast_type
        assert forecast_type["enum"] == ["current", "tomorrow", "7d", "hourly"]

    def test_handles_command_with_no_parameters(self, tool_registry):
        """Test schema generation for command with no parameters."""
        cmd = MagicMock()
        cmd.name = "test"
        cmd.description = "Test command"
        cmd.short_description = "Test"
        cmd.parameters = []

        schema = tool_registry.generate_tool_schema(cmd)

        assert schema["function"]["parameters"]["properties"] == {}
        assert schema["function"]["parameters"]["required"] == []

    def test_uses_short_description_over_description(self, tool_registry, mock_command_manager):
        """Test that short_description is preferred over description."""
        wx_cmd = mock_command_manager.commands["wx"]
        schema = tool_registry.generate_tool_schema(wx_cmd)

        # short_description should be used, not description
        assert schema["function"]["description"] == "Get weather for a location"
        assert schema["function"]["description"] != "Get weather information"

    def test_falls_back_to_description_if_no_short_description(self, tool_registry):
        """Test fallback to description when short_description is empty."""
        cmd = MagicMock()
        cmd.name = "test"
        cmd.description = "Test command"
        cmd.short_description = ""
        cmd.parameters = []

        schema = tool_registry.generate_tool_schema(cmd)
        assert schema["function"]["description"] == "Test command"


class TestGetAllToolSchemas:
    """Tests for get_all_tool_schemas method."""

    def test_returns_schemas_for_all_available_commands(self, tool_registry):
        """Test that schemas are generated for all whitelisted commands."""
        schemas = tool_registry.get_all_tool_schemas()

        # Should return 3 schemas: wx, airplanes, path (help is not whitelisted)
        assert len(schemas) == 3

        schema_names = {s["function"]["name"] for s in schemas}
        assert "wx" in schema_names
        assert "airplanes" in schema_names
        assert "path" in schema_names
        assert "help" not in schema_names

    def test_returns_empty_list_when_no_commands_available(self, tool_registry):
        """Test that empty list is returned when no commands match."""
        tool_registry.available_tools = {"nonexistent"}
        schemas = tool_registry.get_all_tool_schemas()
        assert schemas == []

    def test_logs_schema_generation(self, tool_registry, mock_bot):
        """Test that schema generation is logged."""
        tool_registry.get_all_tool_schemas()

        # Should have logged for each command
        assert mock_bot.logger.debug.call_count >= 3


class TestWxCommandToolSchema:
    """Tests for wx_command tool schema generation (US-009)."""

    def test_wx_command_has_location_parameter_required(self):
        """Test that wx command has location as required parameter."""
        # Import actual wx_command to verify parameter metadata
        from modules.commands.wx_command import WxCommand

        params = WxCommand.parameters
        location_param = next((p for p in params if p["name"] == "location"), None)

        assert location_param is not None
        assert location_param["required"] is True
        assert location_param["type"] == "string"
        assert "zip code" in location_param["description"].lower() or "city" in location_param["description"].lower()

    def test_wx_command_has_forecast_type_parameter_optional(self):
        """Test that wx command has forecast_type as optional parameter."""
        from modules.commands.wx_command import WxCommand

        params = WxCommand.parameters
        forecast_param = next((p for p in params if p["name"] == "forecast_type"), None)

        assert forecast_param is not None
        assert forecast_param["required"] is False
        assert forecast_param["type"] == "string"

    def test_wx_command_forecast_type_has_enum(self):
        """Test that forecast_type parameter has enum values."""
        from modules.commands.wx_command import WxCommand

        params = WxCommand.parameters
        forecast_param = next((p for p in params if p["name"] == "forecast_type"), None)

        assert forecast_param is not None
        assert "enum" in forecast_param
        assert "current" in forecast_param["enum"]
        assert "tomorrow" in forecast_param["enum"]
        assert "7d" in forecast_param["enum"]
        assert "hourly" in forecast_param["enum"]
        assert "alerts" in forecast_param["enum"]

    def test_wx_command_generates_valid_tool_schema(self, tool_registry, mock_bot, mock_command_manager):
        """Test that ToolRegistry generates valid schema for wx_command."""
        # Create a real-like wx command with updated parameters
        wx_cmd = MagicMock()
        wx_cmd.name = "wx"
        wx_cmd.short_description = "Get weather for a US location using NOAA weather data"
        wx_cmd.parameters = [
            {
                "name": "location",
                "description": "US zip code or city name",
                "required": True,
                "type": "string"
            },
            {
                "name": "forecast_type",
                "description": "Forecast type: current (default), tomorrow, 7d, hourly, or alerts",
                "required": False,
                "type": "string",
                "enum": ["current", "tomorrow", "7d", "hourly", "alerts"]
            }
        ]

        schema = tool_registry.generate_tool_schema(wx_cmd)

        # Verify schema structure
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "wx"
        assert schema["function"]["description"] == "Get weather for a US location using NOAA weather data"

        # Verify parameters
        params = schema["function"]["parameters"]
        assert "location" in params["properties"]
        assert "forecast_type" in params["properties"]

        # Verify location is required
        assert "location" in params["required"]
        assert params["properties"]["location"]["type"] == "string"

        # Verify forecast_type is optional
        assert "forecast_type" not in params["required"]
        assert params["properties"]["forecast_type"]["type"] == "string"
        assert params["properties"]["forecast_type"]["enum"] == ["current", "tomorrow", "7d", "hourly", "alerts"]


class TestAirplanesCommandToolSchema:
    """Tests for airplanes_command tool schema generation (US-010)."""

    def test_airplanes_command_has_radius_parameter_optional(self):
        """Test that airplanes command has radius as optional parameter."""
        from modules.commands.airplanes_command import AirplanesCommand

        params = AirplanesCommand.parameters
        radius_param = next((p for p in params if p["name"] == "radius"), None)

        assert radius_param is not None
        assert radius_param["required"] is False
        assert radius_param["type"] == "number"
        assert "radius" in radius_param["description"].lower()

    def test_airplanes_command_description(self):
        """Test that airplanes command has correct description."""
        from modules.commands.airplanes_command import AirplanesCommand

        assert AirplanesCommand.short_description == "Get aircraft overhead using ADS-B data"

    def test_airplanes_command_generates_valid_tool_schema(self, tool_registry, mock_bot, mock_command_manager):
        """Test that ToolRegistry generates valid schema for airplanes_command."""
        # Create a real-like airplanes command with updated parameters
        airplanes_cmd = MagicMock()
        airplanes_cmd.name = "airplanes"
        airplanes_cmd.short_description = "Get information about nearby aircraft using ADS-B data"
        airplanes_cmd.parameters = [
            {
                "name": "radius",
                "description": "Search radius in nautical miles (default: 25)",
                "required": False,
                "type": "number"
            }
        ]

        schema = tool_registry.generate_tool_schema(airplanes_cmd)

        # Verify schema structure
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "airplanes"
        assert schema["function"]["description"] == "Get information about nearby aircraft using ADS-B data"

        # Verify parameters
        params = schema["function"]["parameters"]
        assert "radius" in params["properties"]

        # Verify radius is optional
        assert "radius" not in params["required"]
        assert params["properties"]["radius"]["type"] == "number"

    def test_airplanes_command_schema_in_available_tools(self, tool_registry):
        """Test that airplanes appears in get_all_tool_schemas when available."""
        schemas = tool_registry.get_all_tool_schemas()

        # Find airplanes schema
        airplanes_schema = next((s for s in schemas if s["function"]["name"] == "airplanes"), None)
        assert airplanes_schema is not None
        assert airplanes_schema["function"]["description"] == "Get information about nearby aircraft using ADS-B data"


class TestSatpassCommandToolSchema:
    """Tests for satpass_command tool schema generation (US-011)."""

    def test_satpass_command_has_satellite_parameter_optional(self):
        """Test that satpass command has satellite as optional parameter."""
        from modules.commands.satpass_command import SatpassCommand

        params = SatpassCommand.parameters
        satellite_param = next((p for p in params if p["name"] == "satellite"), None)

        assert satellite_param is not None
        assert satellite_param["required"] is False
        assert satellite_param["type"] == "string"
        assert "NORAD" in satellite_param["description"] or "shortcut" in satellite_param["description"]

    def test_satpass_command_has_visual_parameter_optional(self):
        """Test that satpass command has visual as optional boolean parameter."""
        from modules.commands.satpass_command import SatpassCommand

        params = SatpassCommand.parameters
        visual_param = next((p for p in params if p["name"] == "visual"), None)

        assert visual_param is not None
        assert visual_param["required"] is False
        assert visual_param["type"] == "boolean"

    def test_satpass_command_description(self):
        """Test that satpass command has correct description."""
        from modules.commands.satpass_command import SatpassCommand

        assert SatpassCommand.short_description == "Get satellite pass predictions"

    def test_satpass_command_generates_valid_tool_schema(self, tool_registry, mock_bot, mock_command_manager):
        """Test that ToolRegistry generates valid schema for satpass_command."""
        # Create a real-like satpass command with updated parameters
        satpass_cmd = MagicMock()
        satpass_cmd.name = "satpass"
        satpass_cmd.short_description = "Get satellite pass information for ISS and other satellites"
        satpass_cmd.parameters = [
            {
                "name": "satellite",
                "description": "NORAD ID or shortcut (iss, hst, starlink, hubble, tiangong, goes18)",
                "required": False,
                "type": "string"
            },
            {
                "name": "visual",
                "description": "Filter for visible passes only",
                "required": False,
                "type": "boolean"
            }
        ]

        schema = tool_registry.generate_tool_schema(satpass_cmd)

        # Verify schema structure
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "satpass"
        assert schema["function"]["description"] == "Get satellite pass information for ISS and other satellites"

        # Verify parameters
        params = schema["function"]["parameters"]
        assert "satellite" in params["properties"]
        assert "visual" in params["properties"]

        # Verify both parameters are optional
        assert "satellite" not in params["required"]
        assert "visual" not in params["required"]
        assert params["properties"]["satellite"]["type"] == "string"
        assert params["properties"]["visual"]["type"] == "boolean"


class TestPathCommandToolSchema:
    """Tests for path_command tool schema generation (US-012)."""

    def test_path_command_has_path_hex_parameter_optional(self):
        """Test that path command has path_hex as optional parameter.

        The path command should be used without parameters to automatically
        analyze the sender's incoming message path. Explicit hex paths are
        for advanced users only.
        """
        from modules.commands.path_command import PathCommand

        params = PathCommand.parameters
        path_hex_param = next((p for p in params if p["name"] == "path_hex"), None)

        assert path_hex_param is not None
        assert path_hex_param["required"] is False
        assert path_hex_param["type"] == "string"
        assert "path" in path_hex_param["description"].lower()

    def test_path_command_description(self):
        """Test that path command has correct description."""
        from modules.commands.path_command import PathCommand

        assert "repeater" in PathCommand.short_description.lower() or "path" in PathCommand.short_description.lower()

    def test_path_command_generates_valid_tool_schema(self, tool_registry, mock_bot, mock_command_manager):
        """Test that ToolRegistry generates valid schema for path_command."""
        # Create a real-like path command with updated parameters
        path_cmd = MagicMock()
        path_cmd.name = "path"
        path_cmd.short_description = "Analyze mesh network path to a destination node, showing repeaters and signal quality"
        path_cmd.parameters = [
            {
                "name": "destination",
                "description": "Node ID or hex path data to analyze (e.g., '01,5f' or destination node ID)",
                "required": True,
                "type": "string"
            }
        ]

        # Add to mock command manager
        mock_command_manager.commands = {"path": path_cmd}

        # Generate schema
        schema = tool_registry.generate_tool_schema(path_cmd)

        # Verify schema structure
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "path"
        assert schema["function"]["description"] == path_cmd.short_description

        # Verify parameters
        params = schema["function"]["parameters"]
        assert "destination" in params["properties"]

        # Verify destination is required
        assert "destination" in params["required"]
        assert params["properties"]["destination"]["type"] == "string"

    def test_path_command_in_all_tool_schemas(self, tool_registry, mock_bot, mock_command_manager):
        """Test that path_command is included when available_tools contains 'path'."""
        # Create a real-like path command
        path_cmd = MagicMock()
        path_cmd.name = "path"
        path_cmd.short_description = "Analyze mesh network path to a destination node"
        path_cmd.parameters = [
            {
                "name": "destination",
                "description": "Node ID or hex path data",
                "required": True,
                "type": "string"
            }
        ]

        # Add to mock command manager
        mock_command_manager.commands = {"path": path_cmd}

        # Get all schemas
        schemas = tool_registry.get_all_tool_schemas()

        # Verify path is included
        path_schema = next((s for s in schemas if s["function"]["name"] == "path"), None)
        assert path_schema is not None
        assert "destination" in path_schema["function"]["parameters"]["required"]
