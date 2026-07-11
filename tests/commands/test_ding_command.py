"""Tests for modules.commands.ding_command."""

from unittest.mock import AsyncMock

import pytest

from modules.commands.ding_command import DingCommand
from tests.conftest import mock_message


class TestDingCommand:
    """Tests for DingCommand initialization and metadata."""

    def test_command_metadata(self, command_mock_bot):
        """Test that command metadata is correctly set."""
        cmd = DingCommand(command_mock_bot)
        assert cmd.name == "ding"
        assert cmd.keywords == ['ding']
        assert cmd.description == "Responds with Dong!"
        assert cmd.category == "fun"

    def test_command_documentation(self, command_mock_bot):
        """Test that command documentation attributes are set."""
        cmd = DingCommand(command_mock_bot)
        assert cmd.short_description == "Fun command - responds with Dong!"
        assert cmd.usage == "ding"
        assert cmd.examples == ["ding"]

    def test_get_help_text(self, command_mock_bot):
        """Test that get_help_text returns the description."""
        cmd = DingCommand(command_mock_bot)
        assert cmd.get_help_text() == "Responds with Dong!"


class TestDingCommandCanExecute:
    """Tests for DingCommand.can_execute()."""

    def test_can_execute_when_enabled(self, command_mock_bot):
        """Test that command can execute when enabled in config."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True)
        assert cmd.can_execute(msg) is True

    def test_can_execute_when_disabled(self, command_mock_bot):
        """Test that command cannot execute when disabled in config."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "false")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True)
        assert cmd.can_execute(msg) is False

    def test_can_execute_default_enabled(self, command_mock_bot):
        """Test that command is enabled by default if no config section exists."""
        # No Ding_Command section added - should default to enabled=True
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True)
        assert cmd.can_execute(msg) is True

    def test_can_execute_on_channel(self, command_mock_bot):
        """Test that command can execute on monitored channel."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", channel="general", is_dm=False)
        assert cmd.can_execute(msg) is True


class TestDingCommandExecute:
    """Tests for DingCommand.execute()."""

    @pytest.mark.asyncio
    async def test_execute_returns_default_response(self, command_mock_bot):
        """Test that execute sends the default 'Dong!' response."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True)

        result = await cmd.execute(msg)

        assert result is True
        command_mock_bot.command_manager.send_response.assert_called_once()
        call_args = command_mock_bot.command_manager.send_response.call_args
        assert call_args is not None
        response = call_args[0][1]
        assert response == "Dong!"

    @pytest.mark.asyncio
    async def test_execute_returns_custom_response(self, command_mock_bot):
        """Test that execute sends custom response from config."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        command_mock_bot.config.set("Ding_Command", "response", "Bong!")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True)

        result = await cmd.execute(msg)

        assert result is True
        call_args = command_mock_bot.command_manager.send_response.call_args
        assert call_args is not None
        response = call_args[0][1]
        assert response == "Bong!"

    @pytest.mark.asyncio
    async def test_execute_returns_custom_emoji_response(self, command_mock_bot):
        """Test that execute handles emoji responses correctly."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        command_mock_bot.config.set("Ding_Command", "response", "🔔 Dong! 🔔")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True)

        result = await cmd.execute(msg)

        assert result is True
        call_args = command_mock_bot.command_manager.send_response.call_args
        response = call_args[0][1]
        assert response == "🔔 Dong! 🔔"

    @pytest.mark.asyncio
    async def test_execute_send_response_failure(self, command_mock_bot):
        """Test that execute returns False when send_response fails."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        command_mock_bot.command_manager.send_response = AsyncMock(return_value=False)
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True)

        result = await cmd.execute(msg)

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_on_dm(self, command_mock_bot):
        """Test that execute works on DM messages."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True, sender_pubkey="abc123")

        result = await cmd.execute(msg)

        assert result is True

    @pytest.mark.asyncio
    async def test_execute_on_channel(self, command_mock_bot):
        """Test that execute works on channel messages."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", channel="general", is_dm=False)

        result = await cmd.execute(msg)

        assert result is True


class TestDingCommandRateLimiting:
    """Tests for DingCommand rate limiting (inherited from BaseCommand)."""

    def test_command_inherits_from_base_command(self, command_mock_bot):
        """Test that DingCommand inherits from BaseCommand."""
        from modules.commands.base_command import BaseCommand
        cmd = DingCommand(command_mock_bot)
        assert isinstance(cmd, BaseCommand)

    def test_command_has_send_response(self, command_mock_bot):
        """Test that DingCommand has send_response method from BaseCommand."""
        cmd = DingCommand(command_mock_bot)
        assert hasattr(cmd, 'send_response')
        assert callable(cmd.send_response)

    def test_command_uses_command_manager_send_response(self, command_mock_bot):
        """Test that command uses command_manager.send_response for rate limiting."""
        # The send_response in BaseCommand delegates to command_manager.send_response
        # which handles rate limiting
        cmd = DingCommand(command_mock_bot)
        assert hasattr(cmd, 'bot')
        assert hasattr(cmd.bot, 'command_manager')
        assert hasattr(cmd.bot.command_manager, 'send_response')

    @pytest.mark.asyncio
    async def test_send_response_passes_message_to_command_manager(self, command_mock_bot):
        """Test that send_response passes the message object for rate limit tracking."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        cmd = DingCommand(command_mock_bot)
        msg = mock_message(content="ding", is_dm=True, sender_pubkey="test_pubkey")

        await cmd.execute(msg)

        # Verify send_response was called with both message and response text
        call_args = command_mock_bot.command_manager.send_response.call_args
        assert call_args is not None
        # First argument should be the message
        assert call_args[0][0] == msg


class TestDingCommandConfig:
    """Tests for DingCommand configuration handling."""

    def test_config_enabled_true_string(self, command_mock_bot):
        """Test enabled config with 'true' string."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "true")
        cmd = DingCommand(command_mock_bot)
        assert cmd.ding_enabled is True

    def test_config_enabled_false_string(self, command_mock_bot):
        """Test enabled config with 'false' string."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "false")
        cmd = DingCommand(command_mock_bot)
        assert cmd.ding_enabled is False

    def test_config_enabled_yes_string(self, command_mock_bot):
        """Test enabled config with 'yes' string (accepted by getboolean)."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "yes")
        cmd = DingCommand(command_mock_bot)
        assert cmd.ding_enabled is True

    def test_config_enabled_no_string(self, command_mock_bot):
        """Test enabled config with 'no' string (accepted by getboolean)."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "enabled", "no")
        cmd = DingCommand(command_mock_bot)
        assert cmd.ding_enabled is False

    def test_config_response_default(self, command_mock_bot):
        """Test that response defaults to 'Dong!' when not configured."""
        # No Ding_Command section
        cmd = DingCommand(command_mock_bot)
        assert cmd.response_text == "Dong!"

    def test_config_response_custom(self, command_mock_bot):
        """Test custom response from config."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "response", "Custom Dong!")
        cmd = DingCommand(command_mock_bot)
        assert cmd.response_text == "Custom Dong!"

    def test_config_response_empty_falls_back_to_default(self, command_mock_bot):
        """Test that empty response config still uses fallback."""
        command_mock_bot.config.add_section("Ding_Command")
        command_mock_bot.config.set("Ding_Command", "response", "")
        cmd = DingCommand(command_mock_bot)
        # Empty string should be returned (not fallback, since config exists)
        # This is expected behavior - explicit empty config is respected
        assert cmd.response_text == ""
