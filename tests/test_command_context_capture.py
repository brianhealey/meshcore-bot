"""Tests for command context capture in CommandManager.

Tests that CommandManager properly captures command execution context
for LLM conversation history when track_all_commands is enabled.
"""

from configparser import ConfigParser
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from modules.command_manager import CommandManager
from modules.models import MeshMessage


@pytest.fixture
def mock_bot(mock_logger):
    """Create mock bot with minimal config for testing."""
    bot = Mock()
    bot.logger = mock_logger
    bot.bot_root = Path("/tmp")
    bot._local_root = None
    bot.config = ConfigParser()
    bot.config.add_section("Bot")
    bot.config.set("Bot", "bot_name", "TestBot")
    bot.config.add_section("Channels")
    bot.config.set("Channels", "monitor_channels", "general")
    bot.config.set("Channels", "respond_to_dms", "true")
    bot.translator = Mock()
    bot.translator.translate = Mock(side_effect=lambda key, **kw: f"{key}")
    bot.meshcore = None
    bot.rate_limiter = Mock()
    bot.rate_limiter.can_send = Mock(return_value=True)
    bot.bot_tx_rate_limiter = Mock()
    bot.bot_tx_rate_limiter.wait_for_tx = AsyncMock()
    bot.tx_delay_ms = 0
    bot.is_radio_zombie = False
    bot.is_radio_offline = False
    return bot


@pytest.fixture
def mock_llm_command():
    """Create mock LLM command with context_manager."""
    llm_cmd = Mock()
    llm_cmd.name = "ask"
    llm_cmd.keywords = ["ask", "clear-context"]
    llm_cmd.track_all_commands = True
    llm_cmd.context_manager = Mock()
    llm_cmd.context_manager.add_command_context = AsyncMock(return_value=True)
    return llm_cmd


@pytest.fixture
def mock_wx_command():
    """Create mock weather command."""
    wx_cmd = Mock()
    wx_cmd.name = "wx"
    wx_cmd.keywords = ["wx", "weather"]
    wx_cmd.cooldown_seconds = 0  # No cooldown
    wx_cmd.can_execute = Mock(return_value=True)
    wx_cmd.is_channel_allowed = Mock(return_value=True)
    wx_cmd.should_execute = Mock(return_value=True)
    wx_cmd.get_response_format = Mock(return_value=None)  # No response format = self-handling
    wx_cmd.execute = AsyncMock(return_value=True)
    wx_cmd.last_response = "Austin: 72°F, Sunny"
    return wx_cmd


def make_command_manager(bot, commands):
    """Create CommandManager with mocked PluginLoader."""
    with patch("modules.command_manager.PluginLoader") as mock_loader_class:
        mock_loader = Mock()
        mock_loader.load_all_plugins = Mock(return_value=commands)
        mock_loader_class.return_value = mock_loader
        return CommandManager(bot)


class TestCommandContextCapture:
    """Tests for command context capture functionality."""

    async def test_captures_context_when_enabled(self, mock_bot, mock_llm_command, mock_wx_command):
        """Test that command context is captured when track_all_commands is enabled."""
        commands = {"ask": mock_llm_command, "wx": mock_wx_command}
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="Alice",
            sender_pubkey="abc123",
            channel="general",
            is_dm=False,
        )

        # Execute the wx command
        await manager.execute_commands(message)

        # Verify context was captured
        mock_llm_command.context_manager.add_command_context.assert_called_once()
        call_args = mock_llm_command.context_manager.add_command_context.call_args
        assert call_args[1]["context_key"] == "general"
        assert call_args[1]["command_name"] == "wx"
        assert call_args[1]["user_input"] == "!wx austin"
        assert call_args[1]["bot_response"] == "Austin: 72°F, Sunny"
        assert call_args[1]["sender_name"] == "Alice"

    async def test_uses_channel_name_for_context_key(self, mock_bot, mock_llm_command, mock_wx_command):
        """Test that channel messages use channel name as context_key."""
        commands = {"ask": mock_llm_command, "wx": mock_wx_command}
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="Bob",
            channel="test-channel",
            is_dm=False,
        )

        await manager.execute_commands(message)

        call_args = mock_llm_command.context_manager.add_command_context.call_args
        assert call_args[1]["context_key"] == "test-channel"

    async def test_uses_pubkey_for_dm_context_key(self, mock_bot, mock_llm_command, mock_wx_command):
        """Test that DMs use sender pubkey as context_key."""
        commands = {"ask": mock_llm_command, "wx": mock_wx_command}
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="Charlie",
            sender_pubkey="xyz789",
            is_dm=True,
        )

        await manager.execute_commands(message)

        call_args = mock_llm_command.context_manager.add_command_context.call_args
        assert call_args[1]["context_key"] == "xyz789"

    async def test_fallback_to_sender_id_for_dm_without_pubkey(
        self, mock_bot, mock_llm_command, mock_wx_command
    ):
        """Test that DMs fall back to sender_id when pubkey is unavailable."""
        commands = {"ask": mock_llm_command, "wx": mock_wx_command}
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="David",
            sender_pubkey=None,
            is_dm=True,
        )

        await manager.execute_commands(message)

        call_args = mock_llm_command.context_manager.add_command_context.call_args
        assert call_args[1]["context_key"] == "David"

    async def test_skips_ask_command(self, mock_bot, mock_llm_command):
        """Test that !ask command is skipped from context capture."""
        mock_ask = Mock()
        mock_ask.name = "ask"
        mock_ask.keywords = ["ask"]
        mock_ask.cooldown_seconds = 0
        mock_ask.can_execute = Mock(return_value=True)
        mock_ask.is_channel_allowed = Mock(return_value=True)
        mock_ask.should_execute = Mock(return_value=True)
        mock_ask.get_response_format = Mock(return_value=None)
        mock_ask.execute = AsyncMock(return_value=True)
        mock_ask.last_response = "The capital of Texas is Austin."

        commands = {"ask": mock_llm_command}
        # Override with actual ask command instance
        commands["ask"] = mock_ask
        commands["ask"].context_manager = mock_llm_command.context_manager
        commands["ask"].track_all_commands = True

        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!ask what is the capital of texas",
            sender_id="Eve",
            channel="general",
            is_dm=False,
        )

        await manager.execute_commands(message)

        # Verify context was NOT captured for !ask command
        mock_llm_command.context_manager.add_command_context.assert_not_called()

    async def test_skips_clear_context_command(self, mock_bot, mock_llm_command):
        """Test that !clear-context command is skipped from context capture."""
        mock_clear = Mock()
        mock_clear.name = "ask"  # clear-context is part of ask command
        mock_clear.keywords = ["ask", "clear-context"]
        mock_clear.cooldown_seconds = 0
        mock_clear.can_execute = Mock(return_value=True)
        mock_clear.is_channel_allowed = Mock(return_value=True)
        mock_clear.should_execute = Mock(return_value=True)
        mock_clear.get_response_format = Mock(return_value=None)
        mock_clear.execute = AsyncMock(return_value=True)
        mock_clear.last_response = "Context cleared."

        commands = {"ask": mock_llm_command}
        # Override with actual clear-context command instance
        commands["ask"] = mock_clear
        commands["ask"].context_manager = mock_llm_command.context_manager
        commands["ask"].track_all_commands = True

        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!clear-context",
            sender_id="Frank",
            channel="general",
            is_dm=False,
        )

        await manager.execute_commands(message)

        # Verify context was NOT captured for !clear-context command
        mock_llm_command.context_manager.add_command_context.assert_not_called()

    async def test_skips_when_track_all_commands_disabled(
        self, mock_bot, mock_llm_command, mock_wx_command
    ):
        """Test that context is not captured when track_all_commands is disabled."""
        mock_llm_command.track_all_commands = False
        commands = {"ask": mock_llm_command, "wx": mock_wx_command}
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="Grace",
            channel="general",
            is_dm=False,
        )

        await manager.execute_commands(message)

        # Verify context was NOT captured
        mock_llm_command.context_manager.add_command_context.assert_not_called()

    async def test_skips_when_llm_command_not_available(self, mock_bot, mock_wx_command):
        """Test that context capture is skipped when LLM command is not loaded."""
        commands = {"wx": mock_wx_command}  # No 'ask' command
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="Henry",
            channel="general",
            is_dm=False,
        )

        # Should not raise exception
        await manager.execute_commands(message)

    async def test_skips_when_response_not_sent(self, mock_bot, mock_llm_command, mock_wx_command):
        """Test that context is not captured when command response was not sent."""
        mock_wx_command.last_response = None  # No response
        commands = {"ask": mock_llm_command, "wx": mock_wx_command}
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="Ivy",
            channel="general",
            is_dm=False,
        )

        await manager.execute_commands(message)

        # Verify context was NOT captured
        mock_llm_command.context_manager.add_command_context.assert_not_called()

    async def test_skips_when_command_execution_fails(
        self, mock_bot, mock_llm_command, mock_wx_command
    ):
        """Test that context is not captured when command execution fails."""
        mock_wx_command.execute = AsyncMock(return_value=False)  # Command failed
        commands = {"ask": mock_llm_command, "wx": mock_wx_command}
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="Jack",
            channel="general",
            is_dm=False,
        )

        await manager.execute_commands(message)

        # Verify context was NOT captured
        mock_llm_command.context_manager.add_command_context.assert_not_called()

    async def test_handles_context_capture_errors_gracefully(
        self, mock_bot, mock_llm_command, mock_wx_command
    ):
        """Test that context capture errors don't break command execution."""
        mock_llm_command.context_manager.add_command_context = AsyncMock(
            side_effect=Exception("Database error")
        )
        commands = {"ask": mock_llm_command, "wx": mock_wx_command}
        manager = make_command_manager(mock_bot, commands)

        message = MeshMessage(
            content="!wx austin",
            sender_id="Kate",
            channel="general",
            is_dm=False,
        )

        # Should not raise exception
        await manager.execute_commands(message)

        # Verify error was logged but execution continued
        assert mock_bot.logger.debug.called
