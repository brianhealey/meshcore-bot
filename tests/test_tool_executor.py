#!/usr/bin/env python3
"""Tests for modules/tool_executor.py — ToolExecutor class."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from modules.models import MeshMessage
from modules.tool_executor import ToolExecutor


@pytest.fixture
def mock_bot(mock_logger):
    """Create a mock bot instance."""
    bot = Mock()
    bot.logger = mock_logger
    bot.config = MagicMock()
    bot.config.get.return_value = '!'
    return bot


@pytest.fixture
def mock_tool_registry():
    """Create a mock ToolRegistry instance."""
    registry = Mock()
    registry.available_tools = {'wx', 'airplanes', 'satpass', 'path', 'stats'}
    return registry


@pytest.fixture
def mock_command_manager():
    """Create a mock CommandManager instance."""
    manager = Mock()
    manager.commands = {}
    return manager


@pytest.fixture
def tool_executor(mock_bot, mock_command_manager, mock_tool_registry):
    """Create a ToolExecutor instance."""
    return ToolExecutor(mock_bot, mock_command_manager, mock_tool_registry)


@pytest.fixture
def sample_message():
    """Create a sample MeshMessage for testing."""
    return MeshMessage(
        content="!ask what's the weather",
        sender_id="alice",
        sender_pubkey="!abc123",
        channel="beeboopbot",
        is_dm=False,
        hops=1,
        path="abc,def",
        timestamp=1234567890,
        snr=5.5,
        rssi=-80,
        elapsed="1m",
        content_lower="!ask what's the weather"
    )


class TestToolExecutorInit:
    """Test ToolExecutor initialization."""

    def test_init(self, mock_bot, mock_command_manager, mock_tool_registry):
        executor = ToolExecutor(mock_bot, mock_command_manager, mock_tool_registry)
        assert executor.bot is mock_bot
        assert executor.command_manager is mock_command_manager
        assert executor.tool_registry is mock_tool_registry
        assert executor.logger is mock_bot.logger


class TestBuildMessageContent:
    """Test _build_message_content helper method."""

    def test_simple_command_no_args(self, tool_executor):
        content = tool_executor._build_message_content('stats', {})
        assert content == '!stats'

    def test_command_with_single_arg(self, tool_executor):
        content = tool_executor._build_message_content('wx', {'location': 'seattle'})
        assert 'seattle' in content
        assert content.startswith('!wx')

    def test_command_with_multiple_args(self, tool_executor):
        content = tool_executor._build_message_content('wx', {'location': 'seattle', 'forecast_type': 'tomorrow'})
        assert 'seattle' in content
        assert 'tomorrow' in content
        assert content.startswith('!wx')

    def test_command_with_list_arg(self, tool_executor):
        content = tool_executor._build_message_content('test', {'items': ['foo', 'bar', 'baz']})
        assert 'foo' in content
        assert 'bar' in content
        assert 'baz' in content

    def test_respects_command_prefix_from_config(self, tool_executor, mock_bot):
        mock_bot.config.get.return_value = '/'
        content = tool_executor._build_message_content('wx', {'location': 'seattle'})
        assert content.startswith('/wx')

    def test_uses_parameter_metadata_for_ordering(self, tool_executor, mock_command_manager):
        # Create mock command with parameter metadata
        mock_command = Mock()
        mock_command.parameters = [
            {'name': 'location', 'description': 'Location', 'required': True},
            {'name': 'forecast_type', 'description': 'Forecast type', 'required': False}
        ]
        mock_command_manager.commands = {'wx': mock_command}

        content = tool_executor._build_message_content('wx', {
            'forecast_type': 'tomorrow',
            'location': 'seattle'  # Should come first due to parameter order
        })

        # Location should come before forecast_type
        assert content == '!wx seattle tomorrow'


class TestExecuteTool:
    """Test execute_tool method."""

    async def test_validates_tool_whitelist(self, tool_executor, sample_message):
        result = await tool_executor.execute_tool('invalid_tool', {}, sample_message)
        assert 'not available' in result.lower()
        assert 'invalid_tool' in result

    async def test_returns_error_if_command_not_found(self, tool_executor, sample_message, mock_command_manager):
        # Tool is in whitelist but not in command registry
        result = await tool_executor.execute_tool('wx', {}, sample_message)
        assert 'not found' in result.lower()
        assert 'wx' in result

    async def test_executes_command_successfully(self, tool_executor, sample_message, mock_command_manager):
        # Create mock command that sets last_response during execution
        mock_command = AsyncMock()

        async def set_response(msg):
            mock_command.last_response = "Temperature: 72°F"
            return True

        mock_command.execute = set_response
        mock_command.last_response = None  # Initial state
        mock_command_manager.commands = {'wx': mock_command}

        result = await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message)

        # Verify result contains command output
        assert result == "Temperature: 72°F"

    async def test_creates_synthetic_message_with_correct_fields(self, tool_executor, sample_message, mock_command_manager):
        # Create mock command that captures the message
        received_msg = None

        async def capture_message(msg):
            nonlocal received_msg
            received_msg = msg
            return True

        mock_command = AsyncMock()
        mock_command.execute = capture_message
        mock_command.last_response = None
        mock_command.parameters = []  # No parameter metadata
        mock_command_manager.commands = {'wx': mock_command}

        await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message)

        # Verify execute was called with a MeshMessage
        assert received_msg is not None
        assert isinstance(received_msg, MeshMessage)
        assert received_msg.sender_id == sample_message.sender_id
        assert received_msg.sender_pubkey == sample_message.sender_pubkey
        assert received_msg.channel == sample_message.channel
        assert received_msg.is_dm == sample_message.is_dm
        assert 'wx' in received_msg.content
        assert 'seattle' in received_msg.content

    async def test_handles_timeout(self, tool_executor, sample_message, mock_command_manager):
        # Create mock command that never completes
        mock_command = AsyncMock()

        async def slow_execute(msg):
            await asyncio.sleep(20)  # Will timeout before this completes
            return True

        mock_command.execute = slow_execute
        mock_command_manager.commands = {'wx': mock_command}

        result = await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message, timeout=1)

        assert 'timed out' in result.lower()
        assert 'wx' in result

    async def test_handles_command_exception(self, tool_executor, sample_message, mock_command_manager):
        # Create mock command that raises exception
        mock_command = AsyncMock()
        mock_command.execute = AsyncMock(side_effect=ValueError("Test error"))
        mock_command_manager.commands = {'wx': mock_command}

        result = await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message)

        assert 'error' in result.lower()
        assert 'test error' in result.lower()

    async def test_returns_fallback_if_no_output_captured(self, tool_executor, sample_message, mock_command_manager):
        # Create mock command that succeeds but has no last_response
        mock_command = AsyncMock()
        mock_command.execute = AsyncMock(return_value=True)
        mock_command.last_response = None
        mock_command_manager.commands = {'wx': mock_command}

        result = await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message)

        assert 'executed successfully' in result.lower()
        assert 'wx' in result

    async def test_returns_error_if_command_fails(self, tool_executor, sample_message, mock_command_manager):
        # Create mock command that returns False
        mock_command = AsyncMock()
        mock_command.execute = AsyncMock(return_value=False)
        mock_command.last_response = None
        mock_command_manager.commands = {'wx': mock_command}

        result = await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message)

        assert 'failed' in result.lower()

    async def test_captures_output_from_command_manager_last_response(self, tool_executor, sample_message, mock_command_manager):
        # Create mock command that sets manager's last_response during execution
        async def set_manager_response(msg):
            mock_command_manager._last_response = "Temperature: 68°F (from manager)"
            return True

        mock_command = AsyncMock()
        mock_command.execute = set_manager_response
        mock_command.last_response = None  # No last_response on command
        mock_command_manager.commands = {'wx': mock_command}
        mock_command_manager._last_response = None  # Initial state

        result = await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message)

        assert result == "Temperature: 68°F (from manager)"

    async def test_clears_last_response_before_execution(self, tool_executor, sample_message, mock_command_manager):
        # Create mock command with stale last_response
        mock_command = AsyncMock()
        mock_command.execute = AsyncMock(return_value=True)
        mock_command.last_response = "Stale response"
        mock_command_manager.commands = {'wx': mock_command}
        mock_command_manager._last_response = "Stale manager response"

        # After execute, set a new response
        async def set_new_response(msg):
            mock_command.last_response = "Fresh response"
            return True

        mock_command.execute = set_new_response

        result = await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message)

        # Should get the fresh response, not the stale one
        assert result == "Fresh response"

    async def test_logs_execution_info(self, tool_executor, sample_message, mock_command_manager, mock_bot):
        # Create mock command
        mock_command = AsyncMock()
        mock_command.execute = AsyncMock(return_value=True)
        mock_command.last_response = "Done"
        mock_command_manager.commands = {'wx': mock_command}

        await tool_executor.execute_tool('wx', {'location': 'seattle'}, sample_message)

        # Verify logging
        mock_bot.logger.info.assert_called()
        log_call = str(mock_bot.logger.info.call_args)
        assert 'wx' in log_call.lower()


class TestToolExecutorWithRealCommands:
    """Integration-style tests with command structure."""

    async def test_wx_command_with_location(self, tool_executor, sample_message, mock_command_manager):
        # Create realistic wx command mock that sets response during execution
        async def set_wx_response(msg):
            mock_wx.last_response = "Seattle, WA: Partly cloudy, 72°F"
            return True

        mock_wx = AsyncMock()
        mock_wx.execute = set_wx_response
        mock_wx.last_response = None
        mock_wx.parameters = [
            {'name': 'location', 'description': 'Location', 'required': True},
            {'name': 'forecast_type', 'description': 'Type', 'required': False}
        ]
        mock_command_manager.commands = {'wx': mock_wx}

        result = await tool_executor.execute_tool(
            'wx',
            {'location': 'seattle', 'forecast_type': 'tomorrow'},
            sample_message
        )

        assert "Seattle" in result or "72°F" in result

    async def test_path_command_with_destination(self, tool_executor, sample_message, mock_command_manager, mock_tool_registry):
        # Add path to whitelist
        mock_tool_registry.available_tools.add('path')

        # Create realistic path command mock that sets response during execution
        async def set_path_response(msg):
            mock_path.last_response = "Path to !abc123: Direct (1 hop), SNR: 8.5"
            return True

        mock_path = AsyncMock()
        mock_path.execute = set_path_response
        mock_path.last_response = None
        mock_path.parameters = [
            {'name': 'destination', 'description': 'Destination node', 'required': True}
        ]
        mock_command_manager.commands = {'path': mock_path}

        result = await tool_executor.execute_tool(
            'path',
            {'destination': '!abc123'},
            sample_message
        )

        assert "Path" in result or "hop" in result
