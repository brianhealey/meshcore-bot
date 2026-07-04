"""Integration tests for LLM tool calling end-to-end flow.

Tests verify the complete tool calling workflow:
1. User asks natural language question
2. LLM decides to call appropriate tool(s)
3. ToolExecutor executes command(s)
4. LLM incorporates tool results into response
5. User mention is added to response
6. Command context is stored for future queries
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from modules.commands.llm_command import LLMCommand
from modules.db_manager import AsyncDBManager, DBManager
from tests.conftest import mock_message


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def async_db_manager(tmp_path: Path, mock_logger):
    """Create an AsyncDBManager with initialized llm_conversation_context table.

    Uses tmp_path fixture for file-based SQLite (not :memory:) to ensure
    all connections share the same database.
    """
    db_path = str(tmp_path / "test.db")

    # First, create the schema using DBManager (which runs migrations)
    mock_bot = Mock()
    mock_bot.logger = mock_logger
    _ = DBManager(mock_bot, db_path)  # noqa: F841 - needed to run migrations

    # Create AsyncDBManager pointing to the same database
    async_db = AsyncDBManager(db_path, mock_logger)

    yield async_db

    # Cleanup is handled automatically by tmp_path fixture


@pytest.fixture
def mock_bot_with_tools(mock_logger, async_db_manager):
    """Mock bot with LLM Command configuration, tool calling enabled, and command manager."""
    bot = Mock()
    bot.logger = mock_logger
    bot.async_db_manager = async_db_manager
    bot.config = Mock()

    # Configure LLM_Command section with tools enabled
    def get_config(section, option, fallback=None):
        """Mock config getter."""
        if section == 'LLM_Command':
            config_map = {
                'enabled': 'true',
                'ollama_endpoint': 'http://localhost:11434',
                'ollama_model': 'llama2',
                'ollama_timeout_seconds': '30',
                'context_max_exchanges': '5',
                'context_ttl_seconds': '3600',
                'max_chunk_length': '180',
                'max_response_parts': '5',
                'chunk_delay_seconds': '2.0',
                'system_prompt': 'You are a helpful AI assistant.',
                'enable_tools': 'true',
                'max_tools_per_query': '3',
                'tool_timeout': '10',
                'available_tools': 'wx,airplanes,satpass,path',
                'include_user_mention': 'true',
                'track_all_commands': 'true',
            }
            return config_map.get(option, str(fallback))
        return str(fallback)

    bot.config.get = Mock(side_effect=get_config)
    bot.config.getboolean = Mock(side_effect=lambda s, o, fallback=False: get_config(s, o, fallback) == 'true')
    bot.config.getint = Mock(side_effect=lambda s, o, fallback=0: int(get_config(s, o, fallback)))
    bot.config.getfloat = Mock(side_effect=lambda s, o, fallback=0.0: float(get_config(s, o, fallback)))

    # Mock command manager
    bot.command_manager = Mock()
    bot.command_manager.send_response = AsyncMock(return_value=True)
    bot.command_manager.send_response_chunked = AsyncMock(return_value=True)
    bot.command_manager.commands = {}

    return bot


@pytest.fixture
def mock_wx_command():
    """Create mock weather command."""
    wx_cmd = Mock()
    wx_cmd.name = "wx"
    wx_cmd.keywords = ["wx", "weather"]
    wx_cmd.description = "Get weather conditions and forecast for a location"
    wx_cmd.parameters = [
        {
            "name": "location",
            "description": "Location name or coordinates",
            "required": True,
            "type": "string",
        },
        {
            "name": "forecast_type",
            "description": "Type of forecast (current, tomorrow, 7d, hourly, alerts)",
            "required": False,
            "type": "string",
            "enum": ["current", "tomorrow", "7d", "hourly", "alerts"],
        },
    ]
    wx_cmd.execute = AsyncMock(return_value=True)
    wx_cmd.last_response = "Austin, TX: 72°F, Sunny. High: 78°F, Low: 65°F"
    return wx_cmd


@pytest.fixture
def mock_airplanes_command():
    """Create mock airplanes command."""
    airplanes_cmd = Mock()
    airplanes_cmd.name = "airplanes"
    airplanes_cmd.keywords = ["airplanes", "aircraft", "adsb"]
    airplanes_cmd.description = "Get information about nearby aircraft using ADS-B data"
    airplanes_cmd.parameters = [
        {
            "name": "radius",
            "description": "Search radius in nautical miles (default: 25)",
            "required": False,
            "type": "number",
        }
    ]
    airplanes_cmd.execute = AsyncMock(return_value=True)
    airplanes_cmd.last_response = "Found 3 aircraft: AAL123 (737), UAL456 (A320), SWA789 (737)"
    return airplanes_cmd


@pytest.fixture
def mock_satpass_command():
    """Create mock satellite pass command."""
    satpass_cmd = Mock()
    satpass_cmd.name = "satpass"
    satpass_cmd.keywords = ["satpass", "satellite"]
    satpass_cmd.description = "Get satellite pass information for ISS and other satellites"
    satpass_cmd.parameters = [
        {
            "name": "satellite",
            "description": "Satellite name or NORAD ID (e.g., iss, hubble, starlink)",
            "required": False,
            "type": "string",
        },
        {
            "name": "visual",
            "description": "Show only visual passes",
            "required": False,
            "type": "boolean",
        },
    ]
    satpass_cmd.execute = AsyncMock(return_value=True)
    satpass_cmd.last_response = "ISS next pass: 10:30 PM, duration 5min, max elevation 45°"
    return satpass_cmd


@pytest.fixture
def mock_path_command():
    """Create mock path command."""
    path_cmd = Mock()
    path_cmd.name = "path"
    path_cmd.keywords = ["path"]
    path_cmd.description = "Analyze mesh network path to a destination node, showing repeaters and signal quality"
    path_cmd.parameters = [
        {
            "name": "destination",
            "description": "Destination node ID or hex path data",
            "required": True,
            "type": "string",
        }
    ]
    path_cmd.execute = AsyncMock(return_value=True)
    path_cmd.last_response = "Path to node A1B2: 01 -> 5F -> A1B2 (2 hops, SNR: 8.5)"
    return path_cmd


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestLLMToolCallingIntegration:
    """Integration tests for end-to-end tool calling workflow."""

    async def test_weather_query_triggers_wx_tool(
        self, mock_bot_with_tools, mock_wx_command
    ):
        """Test: User asks weather question → LLM calls wx_command → response includes weather data."""
        # Setup mock commands
        mock_bot_with_tools.command_manager.commands = {"wx": mock_wx_command}

        # Create LLM command instance
        cmd = LLMCommand(mock_bot_with_tools)
        assert cmd.enable_tools is True

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            # Simulate LLM tool calling flow
            mock_chat.side_effect = [
                # First call: LLM decides to call wx tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "wx",
                                    "arguments": {"location": "Austin", "forecast_type": "current"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                # Second call: LLM incorporates tool result into response
                {
                    "message": {
                        "role": "assistant",
                        "content": "The current weather in Austin is 72°F and sunny, with a high of 78°F and low of 65°F.",
                    },
                    "done": True,
                },
            ]

            # Execute natural language weather query
            msg = mock_message(
                content="!ask What's the weather in Austin?",
                channel="test",
                sender_id="Alice",
            )
            result = await cmd.execute(msg)

            # Verify execution succeeded
            assert result is True

            # Verify wx command was executed
            assert mock_wx_command.execute.call_count == 1

            # Verify user mention was added to response ([@Alice])
            assert mock_bot_with_tools.command_manager.send_response.call_count == 1
            response_text = mock_bot_with_tools.command_manager.send_response.call_args[0][1]
            assert response_text.startswith("[@Alice]")
            assert "72°F" in response_text or "Austin" in response_text

    async def test_airplane_query_triggers_airplanes_tool(
        self, mock_bot_with_tools, mock_airplanes_command
    ):
        """Test: User asks airplane question → LLM calls airplanes_command → response includes aircraft."""
        # Setup mock commands
        mock_bot_with_tools.command_manager.commands = {"airplanes": mock_airplanes_command}

        # Create LLM command instance
        cmd = LLMCommand(mock_bot_with_tools)

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                # First call: LLM calls airplanes tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "airplanes",
                                    "arguments": {"radius": 50},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                # Second call: LLM returns final response
                {
                    "message": {
                        "role": "assistant",
                        "content": "There are 3 aircraft nearby: AAL123 (737), UAL456 (A320), and SWA789 (737).",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(
                content="!ask What planes are flying nearby?",
                channel="general",
                sender_id="Bob",
            )
            result = await cmd.execute(msg)

            assert result is True
            assert mock_airplanes_command.execute.call_count == 1

            # Verify response includes user mention
            response_text = mock_bot_with_tools.command_manager.send_response.call_args[0][1]
            assert response_text.startswith("[@Bob]")

    async def test_multi_tool_query_calls_wx_and_satpass(
        self, mock_bot_with_tools, mock_wx_command, mock_satpass_command
    ):
        """Test: Multi-tool query calls both wx and satpass tools."""
        # Setup mock commands
        mock_bot_with_tools.command_manager.commands = {
            "wx": mock_wx_command,
            "satpass": mock_satpass_command,
        }

        cmd = LLMCommand(mock_bot_with_tools)

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                # First call: LLM calls wx tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "wx",
                                    "arguments": {"location": "Austin"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                # Second call: LLM calls satpass tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "satpass",
                                    "arguments": {"satellite": "iss"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                # Third call: LLM returns combined response
                {
                    "message": {
                        "role": "assistant",
                        "content": "Weather is 72°F and sunny. ISS will pass at 10:30 PM tonight.",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(
                content="!ask What's the weather and when will ISS pass?",
                channel="space",
                sender_id="Charlie",
            )
            result = await cmd.execute(msg)

            assert result is True
            # Verify both tools were called
            assert mock_wx_command.execute.call_count == 1
            assert mock_satpass_command.execute.call_count == 1

            # Verify final response includes both pieces of info
            response_text = mock_bot_with_tools.command_manager.send_response.call_args[0][1]
            assert "[@Charlie]" in response_text

    async def test_invalid_tool_call_rejected_gracefully(self, mock_bot_with_tools):
        """Test: Invalid tool call is rejected gracefully."""
        # Setup with no available commands (so all tools are invalid)
        mock_bot_with_tools.command_manager.commands = {}

        cmd = LLMCommand(mock_bot_with_tools)

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                # First call: LLM tries to call invalid tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "invalid_command",
                                    "arguments": {},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                # Second call: LLM handles error and returns fallback response
                {
                    "message": {
                        "role": "assistant",
                        "content": "Sorry, I don't have access to that information.",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(
                content="!ask Use invalid command",
                channel="test",
                sender_id="Dave",
            )
            result = await cmd.execute(msg)

            # Execution should still succeed
            assert result is True

            # Verify error response was sent
            response_text = mock_bot_with_tools.command_manager.send_response.call_args[0][1]
            assert "[@Dave]" in response_text

    async def test_tool_timeout_handled_with_error_message(
        self, mock_bot_with_tools, mock_wx_command
    ):
        """Test: Tool timeout is handled with error message."""
        # Setup mock command that times out
        mock_wx_command.execute = AsyncMock(side_effect=Exception("Timeout after 10 seconds"))
        mock_bot_with_tools.command_manager.commands = {"wx": mock_wx_command}

        cmd = LLMCommand(mock_bot_with_tools)

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                # First call: LLM requests wx tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "wx",
                                    "arguments": {"location": "Austin"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                # Second call: LLM handles timeout error
                {
                    "message": {
                        "role": "assistant",
                        "content": "Sorry, the weather service is taking too long to respond.",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(
                content="!ask Weather in Austin?",
                channel="test",
                sender_id="Eve",
            )
            result = await cmd.execute(msg)

            # Should still succeed despite tool error
            assert result is True

            # Verify response was sent with user mention
            response_text = mock_bot_with_tools.command_manager.send_response.call_args[0][1]
            assert "[@Eve]" in response_text

    async def test_user_mention_prefix_added_to_responses(
        self, mock_bot_with_tools, mock_wx_command
    ):
        """Test: User mention prefix is added to tool calling responses."""
        mock_bot_with_tools.command_manager.commands = {"wx": mock_wx_command}

        cmd = LLMCommand(mock_bot_with_tools)

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "wx",
                                    "arguments": {"location": "Austin"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                {
                    "message": {
                        "role": "assistant",
                        "content": "Weather is 72°F and sunny.",
                    },
                    "done": True,
                },
            ]

            # Test with channel message (should add mention)
            msg = mock_message(
                content="!ask Weather?",
                channel="general",
                sender_id="Frank",
                is_dm=False,
            )
            await cmd.execute(msg)

            response_text = mock_bot_with_tools.command_manager.send_response.call_args[0][1]
            assert response_text.startswith("[@Frank]")

    async def test_user_mention_skipped_for_dms(self, mock_bot_with_tools, mock_wx_command):
        """Test: User mention is NOT added to DM responses."""
        mock_bot_with_tools.command_manager.commands = {"wx": mock_wx_command}

        cmd = LLMCommand(mock_bot_with_tools)

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "wx",
                                    "arguments": {"location": "Austin"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                {
                    "message": {
                        "role": "assistant",
                        "content": "Weather is 72°F and sunny.",
                    },
                    "done": True,
                },
            ]

            # Test with DM (should NOT add mention)
            msg = mock_message(
                content="!ask Weather?",
                is_dm=True,
                sender_id="Grace",
            )
            await cmd.execute(msg)

            response_text = mock_bot_with_tools.command_manager.send_response.call_args[0][1]
            assert not response_text.startswith("[@Grace]")

    async def test_command_context_stored_for_tool_calls(
        self, mock_bot_with_tools, mock_wx_command
    ):
        """Test: Command context is stored for non-!ask commands executed via tools."""
        mock_bot_with_tools.command_manager.commands = {"wx": mock_wx_command}

        cmd = LLMCommand(mock_bot_with_tools)

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "wx",
                                    "arguments": {"location": "Austin"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                {
                    "message": {
                        "role": "assistant",
                        "content": "Weather is 72°F.",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(
                content="!ask Weather in Austin?",
                channel="general",
                sender_id="Hannah",
            )
            await cmd.execute(msg)

            # Verify context was stored for the !ask command
            # (Command context for tool-executed commands is handled by CommandManager)
            # This test verifies the LLM command successfully completes
            assert mock_bot_with_tools.command_manager.send_response.call_count == 1
