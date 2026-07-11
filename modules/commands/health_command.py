#!/usr/bin/env python3
"""
Health command for the MeshCore Bot.

Provides mesh network connectivity health metrics based on repeater
advertisement observations. Uses the ConnectivityMetrics module to
calculate statistics about known and heard repeaters.
"""

from ..connectivity_metrics import ConnectivityMetrics
from ..models import MeshMessage
from .base_command import BaseCommand


class HealthCommand(BaseCommand):
    """Handles the health command.

    Reports mesh network connectivity statistics including:
    - Total repeaters known in the contact database
    - Repeaters heard in the last 48 hours
    - Repeaters heard in the last 24 hours
    - Connectivity percentage (heard/known * 100)
    """

    # Plugin metadata
    name = "health"
    keywords = ['health', 'connectivity']
    description = "Check mesh network connectivity health"
    category = "info"

    # Documentation
    short_description = "View mesh network connectivity health metrics"
    usage = "health"
    examples = ["health", "connectivity"]

    def __init__(self, bot):
        """Initialize the health command.

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)
        self.health_enabled = self.get_config_value(
            'Health_Command', 'enabled', fallback=True, value_type='bool'
        )

    def can_execute(self, message: MeshMessage, skip_channel_check: bool = False) -> bool:
        """Check if this command can be executed with the given message.

        Args:
            message: The message triggering the command.
            skip_channel_check: If True, skip channel check.

        Returns:
            bool: True if command is enabled and checks pass, False otherwise.
        """
        if not self.health_enabled:
            return False
        return super().can_execute(message, skip_channel_check)

    def get_help_text(self) -> str:
        """Get help text for the health command.

        Returns:
            str: The help text for this command.
        """
        return self.description

    async def execute(self, message: MeshMessage) -> bool:
        """Execute the health command.

        Gathers connectivity metrics and sends a formatted response showing:
        - Repeaters known (total in database)
        - Repeaters heard in 48h and 24h windows
        - Connectivity percentage for 24h window

        Args:
            message: The message that triggered the command.

        Returns:
            bool: True if the response was sent successfully, False otherwise.
        """
        try:
            metrics = ConnectivityMetrics(self.bot)

            known = metrics.get_repeaters_known()
            heard_48h = metrics.get_repeaters_heard(hours=48)
            heard_24h = metrics.get_repeaters_heard(hours=24)
            connectivity_pct = metrics.get_connectivity_percentage(hours=24)

            # Format: "Mesh Health: X known / Y heard (48h) / Z heard (24h), N% connectivity"
            response = (
                f"Mesh Health: {known} known / {heard_48h} heard (48h) / "
                f"{heard_24h} heard (24h), {connectivity_pct:.0f}% connectivity"
            )

            return await self.send_response(message, response)

        except Exception as e:
            self.logger.error(f"[HEALTH] Error getting connectivity metrics: {e}")
            return await self.send_response(message, "Error retrieving health metrics")
