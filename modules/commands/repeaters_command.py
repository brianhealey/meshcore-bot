#!/usr/bin/env python3
"""
Repeaters Query command for LLM Tool Calling.

This command allows the LLM to query repeater/contact data directly to answer
questions about repeaters, contacts, distances, and mesh network nodes.

Features:
- Query complete_contact_tracking table for repeater data
- Filter by is_repeater, has_location, distance from bot
- Sort by distance, name, or last_seen
- Calculate distance from bot location when available
- Return JSON-formatted data for LLM consumption
"""

import json
from typing import Any

from ..models import MeshMessage
from ..utils import calculate_distance
from .base_command import BaseCommand

# Default and maximum limits for query results
DEFAULT_LIMIT = 10
MAX_LIMIT = 50


class RepeatersCommand(BaseCommand):
    """Command for LLM to query repeater/contact data.

    This is an LLM-callable tool that provides filtered and sorted
    repeater data with distance calculations from the bot location.
    """

    # Plugin metadata
    name = "repeaters"
    keywords = ['repeaters', 'repeater', 'nodes', 'contacts']
    description = "Query repeater and contact data from the mesh network database."
    category = "data"

    # Documentation for LLM tool calling
    short_description = (
        "Query repeater and contact data from the mesh network. "
        "Use to answer questions about nearby repeaters, contacts with locations, "
        "recently heard nodes, or closest/farthest repeaters from the bot. "
        "Returns structured data with name, location, distance, and last seen info."
    )
    usage = "repeaters [filter] [sort_by] [limit]"
    examples = [
        "repeaters is_repeater=true sort_by=distance limit=10",
        "repeaters has_location=true sort_by=last_seen limit=20",
        "repeaters sort_by=name limit=50",
    ]
    parameters: list[dict[str, Any]] = [
        {
            "name": "is_repeater",
            "description": (
                "Filter to only repeaters (role='repeater') when true, "
                "or only non-repeaters when false. Omit to include all contacts."
            ),
            "required": False,
            "type": "boolean"
        },
        {
            "name": "has_location",
            "description": (
                "Filter to contacts with GPS location (latitude/longitude) when true, "
                "or contacts without location when false. Omit to include all."
            ),
            "required": False,
            "type": "boolean"
        },
        {
            "name": "sort_by",
            "description": (
                "Sort results by: 'distance' (closest first, requires bot location), "
                "'name' (alphabetical), or 'last_seen' (most recent first). "
                "Default: 'last_seen'."
            ),
            "required": False,
            "type": "string",
            "enum": ["distance", "name", "last_seen"]
        },
        {
            "name": "limit",
            "description": (
                f"Maximum number of results to return. Default: {DEFAULT_LIMIT}, Max: {MAX_LIMIT}."
            ),
            "required": False,
            "type": "integer",
            "default": DEFAULT_LIMIT,
            "minimum": 1,
            "maximum": MAX_LIMIT
        }
    ]

    def __init__(self, bot: Any) -> None:
        """Initialize the repeaters command.

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration settings."""
        self.enabled = self.get_config_value(
            'Repeaters_Command', 'enabled', fallback=True, value_type='bool'
        )

    def _get_bot_location(self) -> tuple[float | None, float | None]:
        """Get the bot's current GPS location.

        Returns:
            Tuple of (latitude, longitude) or (None, None) if not available.
        """
        try:
            # Try to get location from meshcore self_info
            if hasattr(self.bot, 'meshcore') and self.bot.meshcore:
                if hasattr(self.bot.meshcore, 'self_info') and self.bot.meshcore.self_info:
                    self_info = self.bot.meshcore.self_info
                    if isinstance(self_info, dict):
                        lat = self_info.get('latitude') or self_info.get('lat')
                        lon = self_info.get('longitude') or self_info.get('lon')
                        if lat is not None and lon is not None:
                            return float(lat), float(lon)
                    elif hasattr(self_info, 'latitude') and hasattr(self_info, 'longitude'):
                        if self_info.latitude is not None and self_info.longitude is not None:
                            return float(self_info.latitude), float(self_info.longitude)

            # Fallback to config
            lat = self.bot.config.getfloat('Bot', 'latitude', fallback=None)
            lon = self.bot.config.getfloat('Bot', 'longitude', fallback=None)
            if lat is not None and lon is not None:
                return lat, lon

        except Exception as e:
            self.logger.debug(f"[REPEATERS] Error getting bot location: {e}")

        return None, None

    def _query_repeaters(
        self,
        is_repeater: bool | None = None,
        has_location: bool | None = None,
        sort_by: str = "last_seen",
        limit: int = DEFAULT_LIMIT
    ) -> tuple[list[dict[str, Any]], str]:
        """Query repeater data from complete_contact_tracking table.

        Args:
            is_repeater: Filter by role='repeater' if True, role!='repeater' if False.
            has_location: Filter by has location if True, no location if False.
            sort_by: Sort field: 'distance', 'name', or 'last_seen'.
            limit: Maximum number of results.

        Returns:
            Tuple of (results list, error message). Error is empty on success.
        """
        try:
            # Enforce limit bounds
            limit = max(1, min(limit, MAX_LIMIT))

            # Build query with filters
            conditions = []
            params: list[Any] = []

            if is_repeater is True:
                conditions.append("role = 'repeater'")
            elif is_repeater is False:
                conditions.append("role != 'repeater'")

            if has_location is True:
                conditions.append("latitude IS NOT NULL AND longitude IS NOT NULL")
            elif has_location is False:
                conditions.append("(latitude IS NULL OR longitude IS NULL)")

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Determine sort order (distance sorting done in Python)
            if sort_by == "name":
                order_clause = "ORDER BY name ASC"
            elif sort_by == "distance":
                # For distance sorting, fetch all with locations and sort in Python
                order_clause = "ORDER BY last_heard DESC"  # Secondary sort
            else:  # last_seen
                order_clause = "ORDER BY last_heard DESC"

            # For distance sorting, we need to fetch more and sort in Python
            # For other sorts, we can limit at DB level
            fetch_limit = limit * 5 if sort_by == "distance" else limit

            query = f"""
                SELECT
                    public_key,
                    name,
                    role,
                    device_type,
                    latitude,
                    longitude,
                    city,
                    state,
                    country,
                    last_heard,
                    first_heard,
                    advert_count,
                    snr,
                    hop_count
                FROM complete_contact_tracking
                {where_clause}
                {order_clause}
                LIMIT ?
            """
            params.append(fetch_limit)

            self.logger.debug(f"[REPEATERS] Executing query: {query[:200]}...")

            with self.bot.db_manager.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()

                if not rows:
                    return [], ""

                # Convert to list of dicts
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row, strict=False)) for row in rows]

            # Calculate distance from bot if available and requested
            bot_lat, bot_lon = self._get_bot_location()

            for result in results:
                result['distance_km'] = None
                lat = result.get('latitude')
                lon = result.get('longitude')
                if bot_lat is not None and bot_lon is not None and lat is not None and lon is not None:
                    try:
                        result['distance_km'] = round(
                            calculate_distance(bot_lat, bot_lon, float(lat), float(lon)), 2
                        )
                    except (ValueError, TypeError):
                        pass

            # Sort by distance if requested
            if sort_by == "distance":
                # Contacts with distance first (sorted), then contacts without distance
                with_distance = [r for r in results if r.get('distance_km') is not None]
                without_distance = [r for r in results if r.get('distance_km') is None]
                with_distance.sort(key=lambda x: x['distance_km'])
                results = with_distance + without_distance

            # Apply final limit
            results = results[:limit]

            return results, ""

        except Exception as e:
            self.logger.error(f"[REPEATERS] Query error: {e}")
            return [], f"Query error: {str(e)}"

    def _format_results_json(self, results: list[dict[str, Any]]) -> str:
        """Format results as JSON for LLM consumption.

        Args:
            results: List of result dictionaries.

        Returns:
            JSON-formatted string.
        """
        if not results:
            return json.dumps({"count": 0, "repeaters": []})

        # Simplify output for LLM
        simplified = []
        for r in results:
            entry: dict[str, Any] = {
                "name": r.get("name"),
                "role": r.get("role"),
            }

            # Add location if available
            if r.get("city") or r.get("state"):
                location_parts = []
                if r.get("city"):
                    location_parts.append(r["city"])
                if r.get("state"):
                    location_parts.append(r["state"])
                entry["location"] = ", ".join(location_parts)

            # Add distance if calculated
            if r.get("distance_km") is not None:
                entry["distance_km"] = r["distance_km"]

            # Add coordinates if present
            if r.get("latitude") is not None and r.get("longitude") is not None:
                entry["latitude"] = r["latitude"]
                entry["longitude"] = r["longitude"]

            # Add last seen
            if r.get("last_heard"):
                entry["last_seen"] = r["last_heard"]

            # Add signal info if present
            if r.get("snr") is not None:
                entry["snr"] = r["snr"]
            if r.get("hop_count") is not None:
                entry["hops"] = r["hop_count"]

            simplified.append(entry)

        return json.dumps({"count": len(simplified), "repeaters": simplified}, indent=2)

    def _format_results_text(self, results: list[dict[str, Any]], message: MeshMessage) -> str:
        """Format results as text for human display.

        Args:
            results: List of result dictionaries.
            message: The message for max length calculation.

        Returns:
            Formatted text string.
        """
        if not results:
            return "No repeaters found matching criteria."

        max_len = self.get_max_message_length(message)
        lines = [f"Found {len(results)} repeaters:"]

        for i, r in enumerate(results, 1):
            name = r.get("name", "Unknown")[:15]
            parts = [f"{i}. {name}"]

            # Add distance if available
            if r.get("distance_km") is not None:
                parts.append(f"{r['distance_km']}km")

            # Add location if available
            if r.get("city"):
                parts.append(r["city"][:10])

            line = " - ".join(parts)
            if len("\n".join(lines) + "\n" + line) > max_len - 20:
                lines.append(f"...[{len(results) - i + 1} more]")
                break
            lines.append(line)

        return "\n".join(lines)

    async def execute(self, message: MeshMessage) -> bool:
        """Execute the repeaters command.

        Args:
            message: The message triggering the command.

        Returns:
            bool: True if executed successfully, False otherwise.
        """
        if not self.enabled:
            await self.send_response(message, "Repeaters command is disabled.")
            return False

        # Parse command content
        content = message.content.strip()

        # Remove command prefix and command name
        if content.lower().startswith('!'):
            content = content[1:].strip()

        for keyword in self.keywords:
            if content.lower().startswith(keyword.lower()):
                content = content[len(keyword):].strip()
                break

        # Parse parameters
        is_repeater: bool | None = None
        has_location: bool | None = None
        sort_by = "last_seen"
        limit = DEFAULT_LIMIT

        # Parse key=value pairs
        for part in content.split():
            part_lower = part.lower()

            if part_lower.startswith("is_repeater="):
                value = part_lower.split("=", 1)[1]
                is_repeater = value in ("true", "1", "yes")

            elif part_lower.startswith("has_location="):
                value = part_lower.split("=", 1)[1]
                has_location = value in ("true", "1", "yes")

            elif part_lower.startswith("sort_by=") or part_lower.startswith("sort="):
                value = part_lower.split("=", 1)[1]
                if value in ("distance", "name", "last_seen"):
                    sort_by = value

            elif part_lower.startswith("limit="):
                try:
                    limit = int(part_lower.split("=", 1)[1])
                except ValueError:
                    pass

        # Execute query
        results, error_msg = self._query_repeaters(
            is_repeater=is_repeater,
            has_location=has_location,
            sort_by=sort_by,
            limit=limit
        )

        if error_msg:
            await self.send_response(message, f"Error: {error_msg}")
            return False

        # Format response - use JSON for LLM, text for humans
        # For simplicity, always use text for mesh responses (constrained length)
        response = self._format_results_text(results, message)
        await self.send_response(message, response)
        return True

    def query(
        self,
        is_repeater: bool | None = None,
        has_location: bool | None = None,
        sort_by: str = "last_seen",
        limit: int = DEFAULT_LIMIT
    ) -> tuple[list[dict[str, Any]], str]:
        """Public method for programmatic query access.

        Used for LLM tool calling and testing.

        Args:
            is_repeater: Filter to repeaters only when True.
            has_location: Filter to contacts with location when True.
            sort_by: Sort field: 'distance', 'name', or 'last_seen'.
            limit: Maximum results (default 10, max 50).

        Returns:
            Tuple of (results list, error message).
        """
        return self._query_repeaters(
            is_repeater=is_repeater,
            has_location=has_location,
            sort_by=sort_by,
            limit=limit
        )

    def get_results_json(
        self,
        is_repeater: bool | None = None,
        has_location: bool | None = None,
        sort_by: str = "last_seen",
        limit: int = DEFAULT_LIMIT
    ) -> str:
        """Get query results as JSON string.

        Convenience method for LLM tool responses.

        Args:
            is_repeater: Filter to repeaters only when True.
            has_location: Filter to contacts with location when True.
            sort_by: Sort field: 'distance', 'name', or 'last_seen'.
            limit: Maximum results (default 10, max 50).

        Returns:
            JSON-formatted string with results.
        """
        results, error = self._query_repeaters(
            is_repeater=is_repeater,
            has_location=has_location,
            sort_by=sort_by,
            limit=limit
        )
        if error:
            return json.dumps({"error": error, "count": 0, "repeaters": []})
        return self._format_results_json(results)
