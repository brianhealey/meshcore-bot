#!/usr/bin/env python3
"""
Ding command for the MeshCore Bot.

A fun command that responds with "Dong!" when triggered.
Response text is configurable via config.ini.
"""

from ..models import MeshMessage
from .base_command import BaseCommand


class DingCommand(BaseCommand):
    """Handles the ding command.

    Responds with "Dong!" (or a custom configured response) when triggered.
    This is a fun, lighthearted command requested by the community.
    """

    # Plugin metadata
    name = "ding"
    keywords = ['ding']
    description = "Responds with Dong!"
    category = "fun"

    # Documentation
    short_description = "Fun command - responds with Dong!"
    usage = "ding"
    examples = ["ding"]

    def __init__(self, bot):
        """Initialize the ding command.

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)
        self.ding_enabled = self.get_config_value(
            'Ding_Command', 'enabled', fallback=True, value_type='bool'
        )
        self.response_text = self.get_config_value(
            'Ding_Command', 'response', fallback='Dong!'
        )

    def can_execute(self, message: MeshMessage, skip_channel_check: bool = False) -> bool:
        """Check if this command can be executed with the given message.

        Args:
            message: The message triggering the command.
            skip_channel_check: If True, skip channel check.

        Returns:
            bool: True if command is enabled and checks pass, False otherwise.
        """
        if not self.ding_enabled:
            return False
        return super().can_execute(message, skip_channel_check)

    def get_help_text(self) -> str:
        """Get help text for the ding command.

        Returns:
            str: The help text for this command.
        """
        return self.description

    async def execute(self, message: MeshMessage) -> bool:
        """Execute the ding command.

        Sends the configured response (default: "Dong!").

        Args:
            message: The message that triggered the command.

        Returns:
            bool: True if the response was sent successfully, False otherwise.
        """
        return await self.send_response(message, self.response_text)
