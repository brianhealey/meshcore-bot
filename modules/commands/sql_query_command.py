#!/usr/bin/env python3
"""
SQL Query command for LLM Tool Calling.

This command allows the LLM to query the SQLite database directly to answer
questions about repeaters, contacts, mesh data, and other bot statistics.

Security:
- Only SELECT queries are allowed
- INSERT/UPDATE/DELETE/DROP/ALTER statements are rejected
- Limit parameter caps maximum rows returned (default 100, max 1000)
"""

import re
from typing import Any

from ..models import MeshMessage
from .base_command import BaseCommand

# Forbidden SQL statement patterns (case-insensitive)
FORBIDDEN_SQL_PATTERNS = [
    r'\bINSERT\b',
    r'\bUPDATE\b',
    r'\bDELETE\b',
    r'\bDROP\b',
    r'\bALTER\b',
    r'\bCREATE\b',
    r'\bTRUNCATE\b',
    r'\bREPLACE\b',
    r'\bATTACH\b',
    r'\bDETACH\b',
    r'\bVACUUM\b',
    r'\bREINDEX\b',
    r'\bPRAGMA\b',  # Prevent schema/setting changes
]


class SQLQueryCommand(BaseCommand):
    """Command for LLM to query the SQLite database.

    This is an LLM-callable tool that provides schema introspection
    and read-only query execution against the bot's SQLite database.
    """

    # Plugin metadata
    name = "sql_query"
    keywords = ['sql_query', 'sqlquery', 'sql']
    description = "Query the bot's SQLite database for mesh data, contacts, and statistics."
    category = "data"

    # Documentation for LLM tool calling
    short_description = (
        "Execute read-only SQL queries against the mesh network database. "
        "Use to answer questions about repeaters, contacts, message stats, "
        "paths, advertisements, and network connectivity. "
        "Tables: complete_contact_tracking (all contacts/repeaters), "
        "message_stats (message history), repeater_adverts (advertisement observations), "
        "mesh_connections (network topology), daily_stats (daily aggregates). "
        "Always use LIMIT to avoid large result sets."
    )
    usage = "sql_query <SELECT statement> [limit]"
    examples = [
        "sql_query SELECT name, last_heard FROM complete_contact_tracking WHERE role='repeater' ORDER BY last_heard DESC LIMIT 10",
        "sql_query SELECT COUNT(*) as total FROM repeater_adverts WHERE observed_at > datetime('now', '-24 hours')",
    ]
    parameters: list[dict[str, Any]] = [
        {
            "name": "query",
            "description": (
                "SQL SELECT query to execute. Must be a read-only SELECT statement. "
                "Available tables: complete_contact_tracking (public_key, name, role, "
                "first_heard, last_heard, latitude, longitude, city, state, country), "
                "message_stats (sender_id, channel, content, timestamp, is_dm, hops, snr, rssi), "
                "repeater_adverts (repeater_pubkey, repeater_name, observed_at, snr, rssi, hops), "
                "mesh_connections (src_node, dst_node, snr, rssi, last_seen, observation_count), "
                "daily_stats (date, public_key, advert_count). "
                "Use datetime('now', '-24 hours') for time filtering."
            ),
            "required": True,
            "type": "string"
        },
        {
            "name": "limit",
            "description": (
                "Maximum number of rows to return. Default: 100, Max: 1000. "
                "Use smaller limits for exploratory queries."
            ),
            "required": False,
            "type": "integer"
        }
    ]

    # Default and maximum limits
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 1000

    def __init__(self, bot: Any) -> None:
        """Initialize the SQL query command.

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration settings."""
        self.enabled = self.get_config_value(
            'SQL_Query_Command', 'enabled', fallback=True, value_type='bool'
        )

    def _is_safe_query(self, sql: str) -> tuple[bool, str]:
        """Check if SQL query is safe (read-only SELECT).

        Args:
            sql: The SQL query to validate.

        Returns:
            Tuple of (is_safe, error_message). If safe, error_message is empty.
        """
        if not sql or not sql.strip():
            return False, "Empty query"

        sql_upper = sql.upper().strip()

        # Must start with SELECT or WITH (for CTEs)
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
            return False, "Only SELECT queries are allowed"

        # Check for forbidden patterns
        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, "Forbidden SQL operation detected"

        # Check for comment injection attempts
        if '--' in sql or '/*' in sql:
            return False, "SQL comments are not allowed"

        return True, ""

    def _get_schema_ddl(self) -> str:
        """Get DDL statements for all tables in the database.

        Returns:
            String containing CREATE TABLE statements for all tables.
        """
        try:
            with self.bot.db_manager.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, sql FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
                tables = cursor.fetchall()

                if not tables:
                    return "No tables found in database."

                ddl_statements = []
                for name, sql in tables:
                    if sql:
                        ddl_statements.append(f"-- Table: {name}\n{sql};")

                return "\n\n".join(ddl_statements)

        except Exception as e:
            self.logger.error(f"Error getting schema DDL: {e}")
            return f"Error retrieving schema: {str(e)}"

    def _execute_query(self, sql: str, limit: int) -> tuple[list[dict], str]:
        """Execute a SELECT query with limit.

        Args:
            sql: The SQL SELECT query to execute.
            limit: Maximum number of rows to return.

        Returns:
            Tuple of (results, error_message). If successful, error_message is empty.
        """
        # Validate query safety
        is_safe, error_msg = self._is_safe_query(sql)
        if not is_safe:
            return [], error_msg

        # Enforce limit
        limit = max(1, min(limit, self.MAX_LIMIT))

        try:
            # Add or modify LIMIT clause
            sql_upper = sql.upper().strip()

            # Check if query already has a LIMIT
            if ' LIMIT ' in sql_upper:
                # Extract existing limit and ensure it doesn't exceed max
                # We'll let the query run with its limit but cap results
                pass
            else:
                # Append LIMIT clause
                sql = f"{sql.rstrip(';')} LIMIT {limit}"

            self.logger.debug(f"[SQL_QUERY] Executing: {sql[:200]}...")

            with self.bot.db_manager.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()

                # Convert to list of dicts
                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    results = [dict(zip(columns, row, strict=False)) for row in rows]
                    # Apply limit even if query had its own (in case it was higher)
                    return results[:limit], ""
                return [], ""

        except Exception as e:
            self.logger.error(f"[SQL_QUERY] Query error: {e}")
            return [], f"Query error: {str(e)}"

    async def execute(self, message: MeshMessage) -> bool:
        """Execute the SQL query command.

        This command is primarily designed for LLM tool calling, but can also
        be invoked directly via !sql_query for testing/debugging.

        Args:
            message: The message triggering the command.

        Returns:
            bool: True if executed successfully, False otherwise.
        """
        if not self.enabled:
            await self.send_response(message, "SQL query command is disabled.")
            return False

        # Parse command content
        content = message.content.strip()

        # Remove command prefix and command name
        if content.lower().startswith('!'):
            content = content[1:].strip()

        # Remove command name variants
        for keyword in self.keywords:
            if content.lower().startswith(keyword.lower()):
                content = content[len(keyword):].strip()
                break

        # Check for schema request
        if content.lower() in ['schema', 'tables', 'ddl', '']:
            schema_ddl = self._get_schema_ddl()
            # Truncate if too long for mesh message
            max_len = self.get_max_message_length(message)
            if len(schema_ddl) > max_len:
                schema_ddl = schema_ddl[:max_len - 50] + "\n...[truncated]"
            await self.send_response(message, schema_ddl)
            return True

        # Parse query and optional limit
        # Format: <SQL query> [limit=N]
        sql_query = content
        limit = self.DEFAULT_LIMIT

        # Check for limit parameter at end
        limit_match = re.search(r'\s+limit\s*=\s*(\d+)\s*$', content, re.IGNORECASE)
        if limit_match:
            limit = int(limit_match.group(1))
            sql_query = content[:limit_match.start()].strip()

        # Execute query
        results, error_msg = self._execute_query(sql_query, limit)

        if error_msg:
            await self.send_response(message, f"Error: {error_msg}")
            return False

        if not results:
            await self.send_response(message, "Query returned no results.")
            return True

        # Format results for response
        response = self._format_results(results, message)
        await self.send_response(message, response)
        return True

    def _format_results(self, results: list[dict], message: MeshMessage) -> str:
        """Format query results for display.

        Args:
            results: List of result dictionaries.
            message: The message (for max length calculation).

        Returns:
            Formatted string representation of results.
        """
        if not results:
            return "No results."

        max_len = self.get_max_message_length(message)

        # For LLM consumption, return JSON-like format
        # For human readability, format as simple table
        lines = []
        lines.append(f"Results ({len(results)} rows):")

        # Get column names from first row
        columns = list(results[0].keys())

        for i, row in enumerate(results):
            row_parts = []
            for col in columns:
                value = row.get(col)
                if value is not None:
                    # Truncate long values
                    str_value = str(value)
                    if len(str_value) > 50:
                        str_value = str_value[:47] + "..."
                    row_parts.append(f"{col}={str_value}")
            row_str = f"{i + 1}. " + ", ".join(row_parts)
            lines.append(row_str)

            # Check if we're approaching max length
            current_len = len("\n".join(lines))
            if current_len > max_len - 50:
                lines.append(f"...[{len(results) - i - 1} more rows]")
                break

        response = "\n".join(lines)
        if len(response) > max_len:
            response = response[:max_len - 20] + "\n...[truncated]"

        return response

    def get_schema(self) -> str:
        """Public method to get database schema DDL.

        Used by ToolRegistry to include schema in tool description.

        Returns:
            DDL statements for all tables.
        """
        return self._get_schema_ddl()

    def query(self, sql: str, limit: int | None = None) -> tuple[list[dict], str]:
        """Public method to execute a query.

        Used for programmatic access and testing.

        Args:
            sql: The SQL SELECT query to execute.
            limit: Maximum number of rows (default: 100, max: 1000).

        Returns:
            Tuple of (results, error_message).
        """
        if limit is None:
            limit = self.DEFAULT_LIMIT
        return self._execute_query(sql, limit)
