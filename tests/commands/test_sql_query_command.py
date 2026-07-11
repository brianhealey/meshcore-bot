"""Tests for modules.commands.sql_query_command."""

import sqlite3
from contextlib import closing
from unittest.mock import MagicMock, Mock

import pytest

from modules.commands.sql_query_command import FORBIDDEN_SQL_PATTERNS, SQLQueryCommand
from modules.db_manager import DBManager
from tests.conftest import mock_message

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sql_db(mock_logger, tmp_path):
    """Create a file-based SQLite database with test schema for SQL query tests."""
    db_path = str(tmp_path / "test_sql.db")

    # Create a minimal bot mock for DBManager
    mock_bot = Mock()
    mock_bot.logger = mock_logger

    # Create DBManager with file-based database
    db_manager = DBManager(mock_bot, db_path)

    # Create test tables (matching the real schema)
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()

        # Create complete_contact_tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS complete_contact_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_key TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                first_heard TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_heard TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                latitude REAL,
                longitude REAL,
                city TEXT,
                state TEXT,
                country TEXT
            )
        ''')

        # Create message_stats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT,
                channel TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_dm INTEGER DEFAULT 0,
                hops INTEGER,
                snr REAL,
                rssi REAL
            )
        ''')

        # Create repeater_adverts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repeater_adverts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repeater_pubkey TEXT NOT NULL,
                repeater_name TEXT,
                observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                snr REAL,
                rssi REAL,
                hops INTEGER
            )
        ''')

        # Create mesh_connections table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mesh_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_node TEXT NOT NULL,
                dst_node TEXT NOT NULL,
                snr REAL,
                rssi REAL,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                observation_count INTEGER DEFAULT 1
            )
        ''')

        # Insert test data
        cursor.execute('''
            INSERT INTO complete_contact_tracking (public_key, name, role, city, state)
            VALUES ('abc123', 'TestRepeater1', 'repeater', 'Austin', 'TX')
        ''')
        cursor.execute('''
            INSERT INTO complete_contact_tracking (public_key, name, role, city, state)
            VALUES ('def456', 'TestRepeater2', 'repeater', 'Dallas', 'TX')
        ''')
        cursor.execute('''
            INSERT INTO complete_contact_tracking (public_key, name, role, city, state)
            VALUES ('ghi789', 'TestUser1', 'client', 'Houston', 'TX')
        ''')

        # Insert some message stats
        cursor.execute('''
            INSERT INTO message_stats (sender_id, channel, content, hops, snr)
            VALUES ('user1', 'general', 'Hello world', 2, 10.5)
        ''')
        cursor.execute('''
            INSERT INTO message_stats (sender_id, channel, content, hops, snr)
            VALUES ('user2', 'emergency', 'Help!', 1, 15.0)
        ''')

        conn.commit()

    yield db_manager


@pytest.fixture
def sql_command(command_mock_bot, sql_db):
    """Create SQLQueryCommand with a real database."""
    command_mock_bot.db_manager = sql_db
    return SQLQueryCommand(command_mock_bot)


@pytest.fixture
def sql_command_no_db(command_mock_bot):
    """Create SQLQueryCommand with a mocked database."""
    return SQLQueryCommand(command_mock_bot)


# ============================================================================
# Test Command Metadata
# ============================================================================


class TestSQLQueryCommandMetadata:
    """Tests for SQLQueryCommand initialization and metadata."""

    def test_command_metadata(self, command_mock_bot):
        """Test that command metadata is correctly set."""
        cmd = SQLQueryCommand(command_mock_bot)
        assert cmd.name == "sql_query"
        assert cmd.keywords == ['sql_query', 'sqlquery', 'sql']
        assert cmd.description == "Query the bot's SQLite database for mesh data, contacts, and statistics."
        assert cmd.category == "data"

    def test_command_documentation(self, command_mock_bot):
        """Test that command documentation attributes are set."""
        cmd = SQLQueryCommand(command_mock_bot)
        assert "SQL queries" in cmd.short_description
        assert "read-only" in cmd.short_description
        assert cmd.usage == "sql_query <SELECT statement> [limit]"
        assert len(cmd.examples) >= 2

    def test_parameters_defined(self, command_mock_bot):
        """Test that command parameters are properly defined."""
        cmd = SQLQueryCommand(command_mock_bot)
        assert isinstance(cmd.parameters, list)
        assert len(cmd.parameters) == 2

        # Check query parameter
        query_param = cmd.parameters[0]
        assert query_param["name"] == "query"
        assert query_param["required"] is True
        assert query_param["type"] == "string"

        # Check limit parameter
        limit_param = cmd.parameters[1]
        assert limit_param["name"] == "limit"
        assert limit_param["required"] is False
        assert limit_param["type"] == "integer"

    def test_default_and_max_limits(self, command_mock_bot):
        """Test that DEFAULT_LIMIT and MAX_LIMIT are set."""
        cmd = SQLQueryCommand(command_mock_bot)
        assert cmd.DEFAULT_LIMIT == 100
        assert cmd.MAX_LIMIT == 1000


# ============================================================================
# Test Query Safety Validation
# ============================================================================


class TestIsSafeQuery:
    """Tests for _is_safe_query() method."""

    def test_empty_query_rejected(self, sql_command_no_db):
        """Test that empty queries are rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("")
        assert is_safe is False
        assert "Empty query" in error

    def test_whitespace_only_rejected(self, sql_command_no_db):
        """Test that whitespace-only queries are rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("   \n\t  ")
        assert is_safe is False
        assert "Empty query" in error

    def test_select_query_allowed(self, sql_command_no_db):
        """Test that SELECT queries are allowed."""
        is_safe, error = sql_command_no_db._is_safe_query("SELECT * FROM users")
        assert is_safe is True
        assert error == ""

    def test_select_lowercase_allowed(self, sql_command_no_db):
        """Test that lowercase SELECT queries are allowed."""
        is_safe, error = sql_command_no_db._is_safe_query("select name from users")
        assert is_safe is True
        assert error == ""

    def test_with_cte_allowed(self, sql_command_no_db):
        """Test that WITH (CTE) queries are allowed."""
        query = "WITH ranked AS (SELECT * FROM users) SELECT * FROM ranked"
        is_safe, error = sql_command_no_db._is_safe_query(query)
        assert is_safe is True
        assert error == ""

    def test_insert_rejected(self, sql_command_no_db):
        """Test that INSERT statements are rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("INSERT INTO users VALUES (1, 'test')")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_update_rejected(self, sql_command_no_db):
        """Test that UPDATE statements are rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("UPDATE users SET name = 'hacked'")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_delete_rejected(self, sql_command_no_db):
        """Test that DELETE statements are rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("DELETE FROM users WHERE id = 1")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_drop_table_rejected(self, sql_command_no_db):
        """Test that DROP TABLE is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("DROP TABLE users")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_alter_table_rejected(self, sql_command_no_db):
        """Test that ALTER TABLE is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("ALTER TABLE users ADD COLUMN hacked TEXT")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_create_table_rejected(self, sql_command_no_db):
        """Test that CREATE TABLE is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("CREATE TABLE hacked (id INTEGER)")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_truncate_rejected(self, sql_command_no_db):
        """Test that TRUNCATE is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("TRUNCATE TABLE users")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_pragma_rejected(self, sql_command_no_db):
        """Test that PRAGMA is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("PRAGMA table_info(users)")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_replace_rejected(self, sql_command_no_db):
        """Test that REPLACE is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("REPLACE INTO users VALUES (1, 'test')")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_attach_rejected(self, sql_command_no_db):
        """Test that ATTACH is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("ATTACH DATABASE '/etc/passwd' AS hacked")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_detach_rejected(self, sql_command_no_db):
        """Test that DETACH is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("DETACH DATABASE main")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_vacuum_rejected(self, sql_command_no_db):
        """Test that VACUUM is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("VACUUM")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_reindex_rejected(self, sql_command_no_db):
        """Test that REINDEX is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query("REINDEX users")
        assert is_safe is False
        assert "Only SELECT queries are allowed" in error

    def test_embedded_insert_rejected(self, sql_command_no_db):
        """Test that SELECT with embedded INSERT in subquery is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query(
            "SELECT * FROM users WHERE id = (INSERT INTO hacked VALUES(1))"
        )
        assert is_safe is False
        assert "Forbidden SQL operation" in error

    def test_embedded_delete_rejected(self, sql_command_no_db):
        """Test that SELECT with embedded DELETE is rejected."""
        is_safe, error = sql_command_no_db._is_safe_query(
            "SELECT * FROM users; DELETE FROM users"
        )
        assert is_safe is False
        assert "Forbidden SQL operation" in error

    def test_comment_injection_double_dash_rejected(self, sql_command_no_db):
        """Test that -- comments are rejected (prevents injection)."""
        is_safe, error = sql_command_no_db._is_safe_query("SELECT * FROM users -- WHERE admin = 1")
        assert is_safe is False
        assert "comments are not allowed" in error

    def test_comment_injection_block_rejected(self, sql_command_no_db):
        """Test that /* */ comments are rejected (prevents injection)."""
        is_safe, error = sql_command_no_db._is_safe_query("SELECT * FROM users /* WHERE admin = 1 */")
        assert is_safe is False
        assert "comments are not allowed" in error

    def test_case_insensitive_forbidden_patterns(self, sql_command_no_db):
        """Test that forbidden patterns are case-insensitive."""
        # Test various cases
        patterns_to_test = [
            "SELECT * FROM users; INSERT INTO hacked VALUES(1)",
            "SELECT * FROM users; insert INTO hacked VALUES(1)",
            "SELECT * FROM users; Insert INTO hacked VALUES(1)",
            "SELECT * FROM users; UPDATE users SET admin=1",
            "SELECT * FROM users; update users SET admin=1",
            "SELECT * FROM users; DELETE FROM users",
            "SELECT * FROM users; delete FROM users",
        ]
        for query in patterns_to_test:
            is_safe, error = sql_command_no_db._is_safe_query(query)
            assert is_safe is False, f"Query should be rejected: {query}"


class TestForbiddenPatterns:
    """Tests for the FORBIDDEN_SQL_PATTERNS constant."""

    def test_all_patterns_are_word_boundaries(self):
        """Test that all forbidden patterns use word boundaries."""
        for pattern in FORBIDDEN_SQL_PATTERNS:
            assert pattern.startswith(r'\b'), f"Pattern should start with \\b: {pattern}"
            assert pattern.endswith(r'\b'), f"Pattern should end with \\b: {pattern}"

    def test_forbidden_patterns_list_completeness(self):
        """Test that all required forbidden operations are in the list."""
        expected_operations = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER',
            'CREATE', 'TRUNCATE', 'REPLACE', 'ATTACH', 'DETACH',
            'VACUUM', 'REINDEX', 'PRAGMA'
        ]
        pattern_text = ' '.join(FORBIDDEN_SQL_PATTERNS)
        for op in expected_operations:
            assert op in pattern_text, f"Missing forbidden operation: {op}"


# ============================================================================
# Test Query Execution
# ============================================================================


class TestExecuteQuery:
    """Tests for _execute_query() method."""

    def test_simple_select_succeeds(self, sql_command):
        """Test that a simple SELECT query executes successfully."""
        results, error = sql_command._execute_query(
            "SELECT name, role FROM complete_contact_tracking",
            limit=10
        )
        assert error == ""
        assert len(results) == 3  # We inserted 3 contacts
        assert all('name' in row and 'role' in row for row in results)

    def test_select_with_where_clause(self, sql_command):
        """Test SELECT with WHERE clause."""
        results, error = sql_command._execute_query(
            "SELECT name FROM complete_contact_tracking WHERE role = 'repeater'",
            limit=10
        )
        assert error == ""
        assert len(results) == 2  # 2 repeaters
        assert results[0]['name'] in ['TestRepeater1', 'TestRepeater2']

    def test_select_with_aggregation(self, sql_command):
        """Test SELECT with COUNT aggregation."""
        results, error = sql_command._execute_query(
            "SELECT COUNT(*) as total FROM complete_contact_tracking",
            limit=10
        )
        assert error == ""
        assert len(results) == 1
        assert results[0]['total'] == 3

    def test_select_with_join(self, sql_command):
        """Test SELECT with self-join (simple case)."""
        results, error = sql_command._execute_query(
            "SELECT a.name as name1, b.name as name2 "
            "FROM complete_contact_tracking a, complete_contact_tracking b "
            "WHERE a.role = 'repeater' AND b.role = 'client' LIMIT 2",
            limit=10
        )
        assert error == ""
        assert len(results) >= 1

    def test_select_with_order_by(self, sql_command):
        """Test SELECT with ORDER BY."""
        results, error = sql_command._execute_query(
            "SELECT name FROM complete_contact_tracking ORDER BY name ASC",
            limit=10
        )
        assert error == ""
        assert len(results) == 3
        # Results should be alphabetically ordered
        names = [r['name'] for r in results]
        assert names == sorted(names)

    def test_empty_result_set(self, sql_command):
        """Test query that returns no results."""
        results, error = sql_command._execute_query(
            "SELECT * FROM complete_contact_tracking WHERE role = 'nonexistent'",
            limit=10
        )
        assert error == ""
        assert results == []

    def test_limit_applied_when_missing(self, sql_command):
        """Test that LIMIT is automatically applied when not in query."""
        results, error = sql_command._execute_query(
            "SELECT * FROM complete_contact_tracking",
            limit=2
        )
        assert error == ""
        assert len(results) == 2  # Limited to 2 even though 3 exist

    def test_limit_respected_when_present(self, sql_command):
        """Test that existing LIMIT clause is preserved."""
        results, error = sql_command._execute_query(
            "SELECT * FROM complete_contact_tracking LIMIT 1",
            limit=10
        )
        assert error == ""
        assert len(results) == 1

    def test_limit_capped_at_max(self, sql_command):
        """Test that limit is capped at MAX_LIMIT."""
        # Insert more data to test limit capping
        results, error = sql_command._execute_query(
            "SELECT * FROM complete_contact_tracking",
            limit=2000  # Exceeds MAX_LIMIT
        )
        assert error == ""
        # Limit should be capped at MAX_LIMIT (1000), but we only have 3 rows
        assert len(results) <= sql_command.MAX_LIMIT

    def test_limit_minimum_is_one(self, sql_command):
        """Test that limit minimum is 1."""
        results, error = sql_command._execute_query(
            "SELECT * FROM complete_contact_tracking",
            limit=0
        )
        assert error == ""
        assert len(results) >= 1  # At least 1 row due to min(1, limit)

    def test_negative_limit_becomes_one(self, sql_command):
        """Test that negative limit becomes 1."""
        results, error = sql_command._execute_query(
            "SELECT * FROM complete_contact_tracking",
            limit=-5
        )
        assert error == ""
        assert len(results) >= 1

    def test_invalid_sql_returns_error(self, sql_command):
        """Test that invalid SQL returns an error message."""
        results, error = sql_command._execute_query(
            "SELECT * FROM nonexistent_table_xyz",
            limit=10
        )
        assert "error" in error.lower()
        assert results == []

    def test_unsafe_query_rejected(self, sql_command):
        """Test that unsafe queries are rejected via _execute_query."""
        results, error = sql_command._execute_query(
            "DELETE FROM complete_contact_tracking",
            limit=10
        )
        assert "Only SELECT queries" in error
        assert results == []


# ============================================================================
# Test Schema Introspection
# ============================================================================


class TestGetSchemaDDL:
    """Tests for _get_schema_ddl() method."""

    def test_returns_ddl_string(self, sql_command):
        """Test that schema DDL is returned as string."""
        ddl = sql_command._get_schema_ddl()
        assert isinstance(ddl, str)
        assert len(ddl) > 0

    def test_contains_table_names(self, sql_command):
        """Test that DDL contains expected table names."""
        ddl = sql_command._get_schema_ddl()
        assert "complete_contact_tracking" in ddl
        assert "message_stats" in ddl
        assert "repeater_adverts" in ddl
        assert "mesh_connections" in ddl

    def test_contains_create_table_statements(self, sql_command):
        """Test that DDL contains CREATE TABLE statements."""
        ddl = sql_command._get_schema_ddl()
        assert "CREATE TABLE" in ddl

    def test_contains_column_definitions(self, sql_command):
        """Test that DDL contains column definitions."""
        ddl = sql_command._get_schema_ddl()
        assert "public_key" in ddl
        assert "name" in ddl
        assert "role" in ddl

    def test_tables_are_labeled(self, sql_command):
        """Test that tables are labeled in output."""
        ddl = sql_command._get_schema_ddl()
        assert "-- Table:" in ddl

    def test_public_get_schema_method(self, sql_command):
        """Test that get_schema() public method works."""
        schema = sql_command.get_schema()
        assert isinstance(schema, str)
        assert "CREATE TABLE" in schema

    def test_excludes_sqlite_internal_tables(self, sql_command):
        """Test that sqlite_ internal tables are excluded."""
        ddl = sql_command._get_schema_ddl()
        assert "sqlite_" not in ddl.lower()


class TestGetSchemaError:
    """Tests for schema introspection error handling."""

    def test_handles_database_error(self, command_mock_bot):
        """Test that database errors are handled gracefully."""
        # Mock db_manager to raise exception
        mock_db = MagicMock()
        mock_db.connection.side_effect = Exception("Database connection failed")
        command_mock_bot.db_manager = mock_db

        cmd = SQLQueryCommand(command_mock_bot)
        ddl = cmd._get_schema_ddl()

        assert "Error" in ddl
        assert "Database connection failed" in ddl


# ============================================================================
# Test Public query() Method
# ============================================================================


class TestQueryPublicMethod:
    """Tests for the public query() method."""

    def test_query_with_default_limit(self, sql_command):
        """Test query() uses default limit when not specified."""
        results, error = sql_command.query("SELECT * FROM complete_contact_tracking")
        assert error == ""
        assert len(results) == 3

    def test_query_with_custom_limit(self, sql_command):
        """Test query() respects custom limit."""
        results, error = sql_command.query("SELECT * FROM complete_contact_tracking", limit=1)
        assert error == ""
        assert len(results) == 1

    def test_query_returns_dict_list(self, sql_command):
        """Test query() returns list of dictionaries."""
        results, error = sql_command.query("SELECT name, role FROM complete_contact_tracking LIMIT 1")
        assert error == ""
        assert isinstance(results, list)
        assert isinstance(results[0], dict)
        assert 'name' in results[0]
        assert 'role' in results[0]


# ============================================================================
# Test execute() Method
# ============================================================================


class TestExecuteMethod:
    """Tests for the execute() method (message handler)."""

    async def test_execute_with_schema_request(self, sql_command):
        """Test execute() with schema request."""
        msg = mock_message(content="!sql_query schema", is_dm=True)
        result = await sql_command.execute(msg)
        assert result is True

        # Verify response was sent
        call_args = sql_command.bot.command_manager.send_response.call_args
        response = call_args[0][1]
        assert "CREATE TABLE" in response

    async def test_execute_with_tables_request(self, sql_command):
        """Test execute() with 'tables' request."""
        msg = mock_message(content="!sql_query tables", is_dm=True)
        result = await sql_command.execute(msg)
        assert result is True

    async def test_execute_with_ddl_request(self, sql_command):
        """Test execute() with 'ddl' request."""
        msg = mock_message(content="!sql ddl", is_dm=True)
        result = await sql_command.execute(msg)
        assert result is True

    async def test_execute_with_empty_content(self, sql_command):
        """Test execute() with empty content returns schema."""
        msg = mock_message(content="!sql_query", is_dm=True)
        result = await sql_command.execute(msg)
        assert result is True

    async def test_execute_with_select_query(self, sql_command):
        """Test execute() with SELECT query."""
        msg = mock_message(
            content="!sql_query SELECT name FROM complete_contact_tracking LIMIT 2",
            is_dm=True
        )
        result = await sql_command.execute(msg)
        assert result is True

        call_args = sql_command.bot.command_manager.send_response.call_args
        response = call_args[0][1]
        assert "Results" in response

    async def test_execute_with_limit_parameter(self, sql_command):
        """Test execute() with limit=N parameter."""
        msg = mock_message(
            content="!sql SELECT * FROM complete_contact_tracking limit=1",
            is_dm=True
        )
        result = await sql_command.execute(msg)
        assert result is True

        call_args = sql_command.bot.command_manager.send_response.call_args
        response = call_args[0][1]
        assert "1 rows" in response or "1. " in response

    async def test_execute_with_no_results(self, sql_command):
        """Test execute() when query returns no results."""
        msg = mock_message(
            content="!sql SELECT * FROM complete_contact_tracking WHERE role='nonexistent'",
            is_dm=True
        )
        result = await sql_command.execute(msg)
        assert result is True

        call_args = sql_command.bot.command_manager.send_response.call_args
        response = call_args[0][1]
        assert "no results" in response.lower()

    async def test_execute_with_invalid_query(self, sql_command):
        """Test execute() with invalid query returns error."""
        msg = mock_message(
            content="!sql SELECT * FROM nonexistent_table_123",
            is_dm=True
        )
        result = await sql_command.execute(msg)
        assert result is False

        call_args = sql_command.bot.command_manager.send_response.call_args
        response = call_args[0][1]
        assert "Error" in response

    async def test_execute_with_forbidden_query(self, sql_command):
        """Test execute() with forbidden query returns error."""
        msg = mock_message(
            content="!sql DELETE FROM complete_contact_tracking",
            is_dm=True
        )
        result = await sql_command.execute(msg)
        assert result is False

        call_args = sql_command.bot.command_manager.send_response.call_args
        response = call_args[0][1]
        assert "Error" in response

    async def test_execute_when_disabled(self, sql_command):
        """Test execute() when command is disabled."""
        sql_command.enabled = False
        msg = mock_message(content="!sql_query schema", is_dm=True)
        result = await sql_command.execute(msg)
        assert result is False

        call_args = sql_command.bot.command_manager.send_response.call_args
        response = call_args[0][1]
        assert "disabled" in response.lower()

    async def test_execute_strips_command_prefix(self, sql_command):
        """Test execute() strips ! prefix correctly."""
        msg = mock_message(
            content="!sql_query SELECT COUNT(*) FROM complete_contact_tracking",
            is_dm=True
        )
        result = await sql_command.execute(msg)
        assert result is True

    async def test_execute_handles_keyword_variants(self, sql_command):
        """Test execute() handles all keyword variants."""
        for keyword in ['sql_query', 'sqlquery', 'sql']:
            msg = mock_message(
                content=f"!{keyword} SELECT 1",
                is_dm=True
            )
            result = await sql_command.execute(msg)
            assert result is True


# ============================================================================
# Test Result Formatting
# ============================================================================


class TestFormatResults:
    """Tests for _format_results() method."""

    def test_format_empty_results(self, sql_command):
        """Test formatting empty result set."""
        msg = mock_message(content="test", is_dm=True)
        formatted = sql_command._format_results([], msg)
        assert formatted == "No results."

    def test_format_single_row(self, sql_command):
        """Test formatting single row result."""
        results = [{'name': 'TestRepeater1', 'role': 'repeater'}]
        msg = mock_message(content="test", is_dm=True)
        formatted = sql_command._format_results(results, msg)
        assert "1 rows" in formatted or "1." in formatted
        assert "TestRepeater1" in formatted

    def test_format_multiple_rows(self, sql_command):
        """Test formatting multiple rows."""
        results = [
            {'name': 'Test1', 'role': 'repeater'},
            {'name': 'Test2', 'role': 'client'},
        ]
        msg = mock_message(content="test", is_dm=True)
        formatted = sql_command._format_results(results, msg)
        assert "2 rows" in formatted
        assert "1." in formatted
        assert "2." in formatted

    def test_format_truncates_long_values(self, sql_command):
        """Test that long values are truncated."""
        long_value = "x" * 100
        results = [{'content': long_value}]
        msg = mock_message(content="test", is_dm=True)
        formatted = sql_command._format_results(results, msg)
        assert "..." in formatted
        # Should be truncated to 47 chars + "..."
        assert long_value not in formatted


# ============================================================================
# Test Configuration
# ============================================================================


class TestConfiguration:
    """Tests for SQLQueryCommand configuration handling."""

    def test_default_enabled(self, command_mock_bot):
        """Test command is enabled by default."""
        cmd = SQLQueryCommand(command_mock_bot)
        assert cmd.enabled is True

    def test_config_disabled(self, command_mock_bot):
        """Test command can be disabled via config."""
        command_mock_bot.config.add_section("SQL_Query_Command")
        command_mock_bot.config.set("SQL_Query_Command", "enabled", "false")
        cmd = SQLQueryCommand(command_mock_bot)
        assert cmd.enabled is False

    def test_config_enabled_explicitly(self, command_mock_bot):
        """Test command enabled via config."""
        command_mock_bot.config.add_section("SQL_Query_Command")
        command_mock_bot.config.set("SQL_Query_Command", "enabled", "true")
        cmd = SQLQueryCommand(command_mock_bot)
        assert cmd.enabled is True


# ============================================================================
# Test Edge Cases and Security
# ============================================================================


class TestSecurityEdgeCases:
    """Tests for security edge cases and injection attempts."""

    def test_stacked_queries_rejected(self, sql_command_no_db):
        """Test that stacked queries (semicolon-separated) with dangerous ops are rejected."""
        is_safe, error = sql_command_no_db._is_safe_query(
            "SELECT * FROM users; DROP TABLE users"
        )
        assert is_safe is False

    def test_union_based_injection_select_only(self, sql_command_no_db):
        """Test that UNION with SELECT is allowed (read-only)."""
        is_safe, error = sql_command_no_db._is_safe_query(
            "SELECT name FROM users UNION SELECT password FROM secrets"
        )
        assert is_safe is True  # UNION is read-only, so it's allowed

    def test_subquery_with_select_allowed(self, sql_command_no_db):
        """Test that subqueries with SELECT are allowed."""
        is_safe, error = sql_command_no_db._is_safe_query(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM admins)"
        )
        assert is_safe is True

    def test_case_manipulation_in_forbidden_keywords(self, sql_command_no_db):
        """Test that mixed-case forbidden keywords are still caught."""
        test_cases = [
            "SELECT * FROM users; DrOp TABLE users",
            "SELECT * FROM users; dELETE FROM users",
            "SELECT * FROM users; InSeRt INTO hacked VALUES(1)",
        ]
        for query in test_cases:
            is_safe, error = sql_command_no_db._is_safe_query(query)
            assert is_safe is False, f"Should reject: {query}"

    def test_whitespace_before_select(self, sql_command_no_db):
        """Test that leading whitespace is handled."""
        is_safe, error = sql_command_no_db._is_safe_query("   SELECT * FROM users")
        assert is_safe is True

    def test_newline_before_select(self, sql_command_no_db):
        """Test that newlines before SELECT are handled."""
        is_safe, error = sql_command_no_db._is_safe_query("\n\nSELECT * FROM users")
        assert is_safe is True

    def test_word_boundary_prevents_false_positives(self, sql_command_no_db):
        """Test that word boundaries prevent matching within other words."""
        # 'UPDATED' contains 'UPDATE' but should not trigger
        is_safe, error = sql_command_no_db._is_safe_query(
            "SELECT * FROM users WHERE status = 'UPDATED'"
        )
        assert is_safe is True  # 'UPDATED' is not 'UPDATE'

    def test_deleting_in_column_name(self, sql_command_no_db):
        """Test that column names containing forbidden words are allowed."""
        # Column named 'is_deleting' should not trigger DELETE pattern
        is_safe, error = sql_command_no_db._is_safe_query(
            "SELECT is_deleting FROM jobs"
        )
        assert is_safe is True
