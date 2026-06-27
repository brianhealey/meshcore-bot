#!/usr/bin/env python3
"""
Unit tests for command prefix functionality
Tests that all commands properly handle command prefixes when enabled
"""

from configparser import ConfigParser
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from modules.command_manager import CommandManager
from modules.commands.base_command import BaseCommand
from modules.commands.hello_command import HelloCommand
from modules.commands.ping_command import PingCommand
from modules.models import MeshMessage


class MockTestCommand(BaseCommand):
    """Mock command for testing prefix functionality"""
    name = "test"
    keywords = ['test', 't']
    description = "Test command"
    category = "test"

    async def execute(self, message: MeshMessage) -> bool:
        """Execute the test command (required by abstract base class)"""
        return True


@pytest.fixture
def mock_bot():
    """Create a mock bot instance"""
    bot = Mock()
    bot.logger = Mock()
    bot.logger.debug = Mock()
    bot.logger.info = Mock()
    bot.logger.warning = Mock()
    bot.logger.error = Mock()
    bot.config = ConfigParser()
    bot.config.add_section('Bot')
    bot.config.add_section('Channels')
    bot.config.set('Channels', 'monitor_channels', 'general')
    bot.config.set('Channels', 'respond_to_dms', 'true')
    bot.meshcore = None
    bot.translator = None
    bot.rate_limiter = Mock()
    bot.rate_limiter.can_send = Mock(return_value=True)
    bot.bot_tx_rate_limiter = Mock()
    bot.bot_tx_rate_limiter.wait_for_tx = Mock()
    bot.tx_delay_ms = 0
    bot.bot_root = Path("/tmp")
    bot._local_root = None  # CommandManager uses bot_root / local / commands
    return bot


@pytest.fixture
def mock_message():
    """Create a mock message"""
    return MeshMessage(
        content="test",
        sender_id="TestUser",
        channel="general",
        is_dm=False
    )


def _make_manager(mock_bot, commands=None):
    with patch('modules.command_manager.PluginLoader') as mock_loader_class:
        mock_loader = Mock()
        mock_loader.load_all_plugins = Mock(return_value=commands or {})
        mock_loader_class.return_value = mock_loader
        return CommandManager(mock_bot)


def _msg(content: str) -> MeshMessage:
    return MeshMessage(
        content=content,
        sender_id="TestUser",
        channel="general",
        is_dm=False,
    )


class ExecuteOnlyCommand(BaseCommand):
    """Command that handles its own response via execute() (no response format)."""

    name = "path"
    keywords = ['path', 'p']
    description = "Path command for prefix regression tests"
    category = "test"

    async def execute(self, message: MeshMessage) -> bool:
        return True


class TestCommandPrefix:
    """Test command prefix functionality"""

    def test_no_prefix_allows_commands(self, mock_bot, mock_message):
        """Test that without prefix configured, commands work normally"""
        mock_bot.config.set('Bot', 'command_prefix', '')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        assert manager.normalize_command_content(mock_message) is True
        assert command.matches_keyword(mock_message) is True

        prefixed = _msg("!test")
        assert manager.normalize_command_content(prefixed) is True
        assert command.matches_keyword(prefixed) is True

    def test_prefix_required_when_configured(self, mock_bot, mock_message):
        """Test that when prefix is configured, it's required"""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        prefixed = _msg("!test")
        assert manager.normalize_command_content(prefixed) is True
        assert command.matches_keyword(prefixed) is True

        unprefixed = _msg("test")
        assert manager.normalize_command_content(unprefixed) is False

    def test_dot_prefix(self, mock_bot, mock_message):
        """Test dot prefix (e.g., .ping)"""
        mock_bot.config.set('Bot', 'command_prefix', '.')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        prefixed = _msg(".test")
        assert manager.normalize_command_content(prefixed) is True
        assert command.matches_keyword(prefixed) is True

        unprefixed = _msg("test")
        assert manager.normalize_command_content(unprefixed) is False

    def test_single_char_prefix(self, mock_bot, mock_message):
        """Test single character prefix (e.g., bping)"""
        mock_bot.config.set('Bot', 'command_prefix', 'b')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        prefixed = _msg("btest")
        assert manager.normalize_command_content(prefixed) is True
        assert command.matches_keyword(prefixed) is True

        unprefixed = _msg("test")
        assert manager.normalize_command_content(unprefixed) is False

    def test_multi_char_prefix(self, mock_bot, mock_message):
        """Test multi-character prefix (e.g., abcping)"""
        mock_bot.config.set('Bot', 'command_prefix', 'abc')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        prefixed = _msg("abctest")
        assert manager.normalize_command_content(prefixed) is True
        assert command.matches_keyword(prefixed) is True

        assert manager.normalize_command_content(_msg("test")) is False
        assert manager.normalize_command_content(_msg("abtest")) is False

    def test_prefix_with_whitespace(self, mock_bot, mock_message):
        """Test that prefix works with whitespace after it"""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        spaced = _msg("! test")
        assert manager.normalize_command_content(spaced) is True
        assert command.matches_keyword(spaced) is True

        tight = _msg("!test")
        assert manager.normalize_command_content(tight) is True
        assert command.matches_keyword(tight) is True

    def test_prefix_with_keyword_variations(self, mock_bot, mock_message):
        """Test prefix with different keyword variations"""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        for content in ("!test", "!t", "!test arg1 arg2"):
            msg = _msg(content)
            assert manager.normalize_command_content(msg) is True
            assert command.matches_keyword(msg) is True

    def test_hello_command_with_prefix(self, mock_bot, mock_message):
        """Test hello command specifically with prefix"""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        mock_bot.config.set('Bot', 'bot_name', 'TestBot')
        mock_bot.config.add_section('Hello_Command')
        mock_bot.config.set('Hello_Command', 'enabled', 'true')
        manager = _make_manager(mock_bot)
        command = HelloCommand(mock_bot)

        prefixed = _msg("!hello")
        assert manager.normalize_command_content(prefixed) is True
        assert command.matches_keyword(prefixed) is True

        assert manager.normalize_command_content(_msg("hello")) is False

    def test_ping_command_with_prefix(self, mock_bot, mock_message):
        """Test ping command with prefix"""
        mock_bot.config.set('Bot', 'command_prefix', '.')
        mock_bot.config.add_section('Ping_Command')
        mock_bot.config.set('Ping_Command', 'enabled', 'true')
        manager = _make_manager(mock_bot)
        command = PingCommand(mock_bot)

        prefixed = _msg(".ping")
        assert manager.normalize_command_content(prefixed) is True
        assert command.matches_keyword(prefixed) is True

        assert manager.normalize_command_content(_msg("ping")) is False

    def test_command_manager_with_prefix(self, mock_bot, mock_message):
        """Test CommandManager handles prefix correctly"""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        mock_bot.config.add_section('Keywords')
        mock_bot.config.set('Keywords', 'keywords', '')
        mock_bot.config.add_section('Custom_Syntax')
        mock_bot.config.set('Custom_Syntax', 'custom_syntax', '')

        manager = _make_manager(mock_bot)

        assert manager.check_keywords(_msg("test")) == []
        assert isinstance(manager.check_keywords(_msg("!test")), list)

    def test_prefix_with_mentions(self, mock_bot, mock_message):
        """Test that prefix works correctly with @[username] mentions"""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        mock_bot.config.set('Bot', 'bot_name', 'TestBot')
        mock_bot.config.set('Bot', 'respond_to_mentions', 'also')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        mock_bot.meshcore = Mock()
        mock_bot.meshcore.self_info = {'name': 'TestBot'}

        bot_mention = _msg("! test")
        assert manager.normalize_command_content(bot_mention) is True
        assert command.matches_keyword(bot_mention) is True

        other_mention = _msg("!@[OtherUser] test")
        assert manager.normalize_command_content(other_mention) is True
        assert command.matches_keyword(other_mention) is False

    def test_different_prefixes_dont_match(self, mock_bot, mock_message):
        """Test that wrong prefix doesn't match"""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        manager = _make_manager(mock_bot)

        for content in (".test", "btest", "abctest"):
            assert manager.normalize_command_content(_msg(content)) is False

    def test_prefix_case_sensitive(self, mock_bot, mock_message):
        """Test that prefix matching is case-sensitive"""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        for content in ("!test", "!TEST"):
            msg = _msg(content)
            assert manager.normalize_command_content(msg) is True
            assert command.matches_keyword(msg) is True

        mock_bot.config.set('Bot', 'command_prefix', 'b')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)
        assert manager.normalize_command_content(_msg("Btest")) is False

    def test_empty_prefix_string(self, mock_bot, mock_message):
        """Test that empty string prefix means no prefix required"""
        mock_bot.config.set('Bot', 'command_prefix', '')
        manager = _make_manager(mock_bot)
        command = MockTestCommand(mock_bot)

        plain = _msg("test")
        assert manager.normalize_command_content(plain) is True
        assert command.matches_keyword(plain) is True

        legacy = _msg("!test")
        assert manager.normalize_command_content(legacy) is True
        assert command.matches_keyword(legacy) is True

    def test_normalize_is_idempotent(self, mock_bot, mock_message):
        mock_bot.config.set('Bot', 'command_prefix', '!')
        manager = _make_manager(mock_bot)

        mock_message.content = "!path ab"
        assert manager.normalize_command_content(mock_message) is True
        assert mock_message.content == "path ab"
        assert manager.normalize_command_content(mock_message) is True
        assert mock_message.content == "path ab"

    @pytest.mark.asyncio
    async def test_execute_command_runs_after_check_keywords_with_prefix(self, mock_bot, mock_message):
        """Regression: execute()-based commands must run when command_prefix is set."""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        mock_bot.config.set('Bot', 'respond_to_mentions', 'false')
        manager = _make_manager(mock_bot)
        mock_bot.command_manager = manager
        path_cmd = ExecuteOnlyCommand(mock_bot)
        path_cmd.execute = AsyncMock(return_value=True)
        path_cmd.send_response = AsyncMock(return_value=True)
        manager.commands['path'] = path_cmd
        mock_message.content = "!path ab"

        matches = manager.check_keywords(mock_message)
        assert ('path', None) in matches

        await manager.execute_commands(mock_message)
        path_cmd.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_format_command_still_works_with_prefix(self, mock_bot, mock_message):
        """Commands with response formats are handled in check_keywords."""
        mock_bot.config.set('Bot', 'command_prefix', '!')
        mock_bot.config.add_section('Ping_Command')
        mock_bot.config.set('Ping_Command', 'enabled', 'true')
        mock_bot.config.add_section('Keywords')
        mock_bot.config.set('Keywords', 'ping', 'Pong!')

        ping_cmd = PingCommand(mock_bot)
        manager = _make_manager(mock_bot, commands={'ping': ping_cmd})
        mock_bot.command_manager = manager
        mock_message.content = "!ping"

        matches = manager.check_keywords(mock_message)
        assert any(name == 'ping' and response == 'Pong!' for name, response in matches)
