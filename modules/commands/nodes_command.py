#!/usr/bin/env python3
"""
Nodes Command - List known mesh network nodes/repeaters
Provides a list of recently seen nodes for LLM tool calling
"""

from ..models import MeshMessage
from .base_command import BaseCommand


class NodesCommand(BaseCommand):
    """Lists known mesh network nodes and repeaters."""

    name = "nodes"
    keywords = ["nodes", "nodelist"]
    description = "List recently seen mesh network nodes and repeaters"
    category = "meshcore_info"
    cooldown_seconds = 5
    requires_dm = False

    # Documentation for LLM tool calling
    short_description = "Get list of known mesh network nodes, repeaters, and their IDs. Use this when user asks about available nodes, distant nodes, or which nodes to test connectivity to."
    usage = "nodes [limit]"
    examples = ["nodes", "nodes 10"]
    parameters = [
        {
            "name": "limit",
            "description": "Maximum number of nodes to return (default: 10, max: 20). Use lower numbers for concise lists.",
            "required": False,
            "type": "integer"
        }
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.nodes_enabled = self.get_config_value('Nodes_Command', 'enabled', fallback=True, value_type='bool')

    def can_execute(self, message: MeshMessage, skip_channel_check: bool = False) -> bool:
        if not self.nodes_enabled:
            return False
        return super().can_execute(message)

    async def execute(self, message: MeshMessage) -> bool:
        """Execute nodes list command."""
        # Parse limit from command
        parts = message.content.strip().split()
        limit = 10  # default
        if len(parts) > 1:
            try:
                requested_limit = int(parts[1])
                limit = min(max(1, requested_limit), 20)  # Clamp between 1 and 20
            except ValueError:
                pass

        try:
            # Query database for recent contacts
            with self.bot.db_manager.connection() as conn:
                cursor = conn.cursor()
                
                # Get repeaters and companions with their node IDs
                cursor.execute("""
                    SELECT 
                        name,
                        node_id,
                        role,
                        last_seen,
                        total_hops
                    FROM repeater_contacts
                    WHERE last_seen > datetime('now', '-7 days')
                    ORDER BY last_seen DESC
                    LIMIT ?
                """, (limit,))
                
                results = cursor.fetchall()

            if not results:
                await self.send_response(message, "No nodes found in database.")
                return True

            # Format response
            response_lines = []
            for row in results:
                name, node_id, role, last_seen, hops = row
                # Shorten role names
                role_short = role[0].upper() if role else "?"  # R for repeater, C for companion
                # Format: Name (ID) R/C Hops
                response_lines.append(f"{name} ({node_id}) {role_short} {hops}h")

            # Join with separator
            response = "Nodes: " + " | ".join(response_lines)

            await self.send_response(message, response)
            return True

        except Exception as e:
            self.logger.error(f"Error listing nodes: {e}")
            await self.send_response(message, f"Error: {e}")
            return False
