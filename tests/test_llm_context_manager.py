"""Tests for modules/llm_context_manager.py — LLMContextManager."""

import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from modules.db_manager import AsyncDBManager, DBManager
from modules.llm_context_manager import LLMContextManager

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
async def async_db_manager(tmp_path: Path, mock_logger):
    """Create an AsyncDBManager with initialized llm_conversation_context table.

    Uses tmp_path fixture for file-based SQLite (not :memory:) to ensure
    all connections share the same database.
    """
    db_path = str(tmp_path / "test.db")

    # First, create the schema using DBManager (which runs migrations)
    mock_bot = Mock()
    mock_bot.logger = mock_logger
    _ = DBManager(mock_bot, db_path)  # noqa: F841 - needed to run migrations

    # Create AsyncDBManager pointing to the same database
    async_db = AsyncDBManager(db_path, mock_logger)

    yield async_db

    # Cleanup is handled automatically by tmp_path fixture


@pytest.fixture
async def context_manager(async_db_manager, mock_logger):
    """Create an LLMContextManager instance for testing."""
    return LLMContextManager(async_db_manager, mock_logger)


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------


class TestInit:
    """Test LLMContextManager initialization."""

    async def test_async_db_stored(self, async_db_manager, mock_logger):
        """Test that async_db is stored correctly."""
        manager = LLMContextManager(async_db_manager, mock_logger)
        assert manager.async_db is async_db_manager

    async def test_logger_stored(self, async_db_manager, mock_logger):
        """Test that logger is stored correctly."""
        manager = LLMContextManager(async_db_manager, mock_logger)
        assert manager.logger is mock_logger

    async def test_logger_default(self, async_db_manager):
        """Test that logger is created if not provided."""
        manager = LLMContextManager(async_db_manager)
        assert manager.logger is not None


# ---------------------------------------------------------------------------
# TestGetContext
# ---------------------------------------------------------------------------


class TestGetContext:
    """Test LLMContextManager.get_context()."""

    async def test_empty_context(self, context_manager):
        """Test get_context() returns empty list when no history exists."""
        result = await context_manager.get_context("test_key")
        assert result == []

    async def test_populated_context(self, context_manager):
        """Test get_context() retrieves existing messages."""
        # Add some messages
        await context_manager.add_message("test_key", "user", "Hello")
        await context_manager.add_message("test_key", "assistant", "Hi there!")

        # Retrieve context
        result = await context_manager.get_context("test_key")

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Hi there!"

    async def test_chronological_order(self, context_manager):
        """Test that messages are returned in chronological order (oldest first)."""
        # Add messages with slight delay to ensure timestamp ordering
        await context_manager.add_message("test_key", "user", "First")
        time.sleep(0.01)
        await context_manager.add_message("test_key", "assistant", "Second")
        time.sleep(0.01)
        await context_manager.add_message("test_key", "user", "Third")

        result = await context_manager.get_context("test_key")

        assert len(result) == 3
        assert result[0]["content"] == "First"
        assert result[1]["content"] == "Second"
        assert result[2]["content"] == "Third"

    async def test_max_exchanges_limit(self, context_manager):
        """Test that max_exchanges limits the number of messages returned."""
        # Add 6 messages (3 exchanges)
        for i in range(3):
            await context_manager.add_message("test_key", "user", f"User {i}")
            await context_manager.add_message("test_key", "assistant", f"Assistant {i}")

        # Request only 2 exchanges (4 messages)
        result = await context_manager.get_context("test_key", max_exchanges=2)

        assert len(result) == 4
        # Should get the most recent 2 exchanges
        assert result[0]["content"] == "User 1"
        assert result[1]["content"] == "Assistant 1"
        assert result[2]["content"] == "User 2"
        assert result[3]["content"] == "Assistant 2"

    async def test_context_key_isolation(self, context_manager):
        """Test that different context keys are isolated."""
        await context_manager.add_message("key1", "user", "Message for key1")
        await context_manager.add_message("key2", "user", "Message for key2")

        result1 = await context_manager.get_context("key1")
        result2 = await context_manager.get_context("key2")

        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0]["content"] == "Message for key1"
        assert result2[0]["content"] == "Message for key2"

    async def test_message_fields(self, context_manager):
        """Test that all expected fields are present in returned messages."""
        await context_manager.add_message("test_key", "user", "Test message")

        result = await context_manager.get_context("test_key")

        assert len(result) == 1
        msg = result[0]

        # Check all expected fields exist
        assert "id" in msg
        assert "context_key" in msg
        assert "role" in msg
        assert "content" in msg
        assert "timestamp" in msg
        assert "created_at" in msg

        # Check field values
        assert msg["context_key"] == "test_key"
        assert msg["role"] == "user"
        assert msg["content"] == "Test message"
        assert isinstance(msg["timestamp"], float)


# ---------------------------------------------------------------------------
# TestAddMessage
# ---------------------------------------------------------------------------


class TestAddMessage:
    """Test LLMContextManager.add_message()."""

    async def test_add_user_message(self, context_manager):
        """Test adding a user message."""
        result = await context_manager.add_message("test_key", "user", "Hello")
        assert result is True

        # Verify it was stored
        context = await context_manager.get_context("test_key")
        assert len(context) == 1
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "Hello"

    async def test_add_assistant_message(self, context_manager):
        """Test adding an assistant message."""
        result = await context_manager.add_message("test_key", "assistant", "Hi there!")
        assert result is True

        # Verify it was stored
        context = await context_manager.get_context("test_key")
        assert len(context) == 1
        assert context[0]["role"] == "assistant"
        assert context[0]["content"] == "Hi there!"

    async def test_timestamp_generated(self, context_manager):
        """Test that timestamp is automatically generated."""
        before = time.time()
        await context_manager.add_message("test_key", "user", "Test")
        after = time.time()

        context = await context_manager.get_context("test_key")
        timestamp = context[0]["timestamp"]

        # Timestamp should be between before and after
        assert before <= timestamp <= after

    async def test_multiple_messages(self, context_manager):
        """Test adding multiple messages to same context."""
        await context_manager.add_message("test_key", "user", "First")
        await context_manager.add_message("test_key", "assistant", "Second")
        await context_manager.add_message("test_key", "user", "Third")

        context = await context_manager.get_context("test_key")
        assert len(context) == 3


# ---------------------------------------------------------------------------
# TestPruneContext
# ---------------------------------------------------------------------------


class TestPruneContext:
    """Test LLMContextManager.prune_context()."""

    async def test_prune_by_max_exchanges(self, context_manager):
        """Test pruning based on max_exchanges limit."""
        # Add 6 messages (3 exchanges)
        for i in range(3):
            await context_manager.add_message("test_key", "user", f"User {i}")
            await context_manager.add_message("test_key", "assistant", f"Assistant {i}")

        # Prune to keep only 2 exchanges (4 messages)
        await context_manager.prune_context("test_key", max_exchanges=2)

        # Verify only 4 messages remain
        context = await context_manager.get_context("test_key")
        assert len(context) == 4

        # Should keep the most recent 2 exchanges
        assert context[0]["content"] == "User 1"
        assert context[1]["content"] == "Assistant 1"
        assert context[2]["content"] == "User 2"
        assert context[3]["content"] == "Assistant 2"

    async def test_prune_by_ttl(self, context_manager):
        """Test pruning based on TTL (time-to-live)."""
        # Add old message
        old_timestamp = time.time() - 3600  # 1 hour ago
        async with context_manager.async_db.connection() as conn:
            await conn.execute(
                '''INSERT INTO llm_conversation_context (context_key, role, content, timestamp)
                   VALUES (?, ?, ?, ?)''',
                ("test_key", "user", "Old message", old_timestamp),
            )
            await conn.commit()

        # Add recent message
        await context_manager.add_message("test_key", "user", "Recent message")

        # Prune with TTL of 30 minutes (1800 seconds)
        await context_manager.prune_context("test_key", max_exchanges=10, ttl_seconds=1800)

        # Verify only recent message remains
        context = await context_manager.get_context("test_key")
        assert len(context) == 1
        assert context[0]["content"] == "Recent message"

    async def test_prune_no_ttl(self, context_manager):
        """Test pruning with no TTL specified (only max_exchanges)."""
        # Add old message
        old_timestamp = time.time() - 3600  # 1 hour ago
        async with context_manager.async_db.connection() as conn:
            await conn.execute(
                '''INSERT INTO llm_conversation_context (context_key, role, content, timestamp)
                   VALUES (?, ?, ?, ?)''',
                ("test_key", "user", "Old message", old_timestamp),
            )
            await conn.commit()

        # Add recent message
        await context_manager.add_message("test_key", "user", "Recent message")

        # Prune with no TTL
        await context_manager.prune_context("test_key", max_exchanges=10, ttl_seconds=None)

        # Both messages should remain (within max_exchanges limit)
        context = await context_manager.get_context("test_key")
        assert len(context) == 2

    async def test_prune_context_key_isolation(self, context_manager):
        """Test that pruning only affects the specified context key."""
        # Add messages to two different contexts
        await context_manager.add_message("key1", "user", "Key1 message 1")
        await context_manager.add_message("key1", "user", "Key1 message 2")
        await context_manager.add_message("key2", "user", "Key2 message")

        # Prune key1 to 0 exchanges (delete all)
        await context_manager.prune_context("key1", max_exchanges=0)

        # Verify key1 is empty but key2 is intact
        context1 = await context_manager.get_context("key1")
        context2 = await context_manager.get_context("key2")

        assert len(context1) == 0
        assert len(context2) == 1

    async def test_prune_no_error_on_empty_context(self, context_manager):
        """Test that pruning an empty context doesn't raise errors."""
        # Should not raise any exceptions
        await context_manager.prune_context("nonexistent_key", max_exchanges=5)


# ---------------------------------------------------------------------------
# TestClearContext
# ---------------------------------------------------------------------------


class TestClearContext:
    """Test LLMContextManager.clear_context()."""

    async def test_clear_existing_context(self, context_manager, mock_logger):
        """Test clearing a context with messages."""
        # Add messages
        await context_manager.add_message("test_key", "user", "Message 1")
        await context_manager.add_message("test_key", "assistant", "Message 2")

        # Clear context
        result = await context_manager.clear_context("test_key")
        assert result is True

        # Verify context is empty
        context = await context_manager.get_context("test_key")
        assert len(context) == 0

        # Verify info log was called with the clear message
        # Use assert_any_call because migrations also log info messages
        mock_logger.info.assert_any_call("Cleared context for key 'test_key'")

    async def test_clear_empty_context(self, context_manager):
        """Test clearing a context that doesn't exist."""
        # Should not raise any errors
        result = await context_manager.clear_context("nonexistent_key")
        assert result is True

    async def test_clear_context_key_isolation(self, context_manager):
        """Test that clearing only affects the specified context key."""
        # Add messages to two different contexts
        await context_manager.add_message("key1", "user", "Key1 message")
        await context_manager.add_message("key2", "user", "Key2 message")

        # Clear key1
        await context_manager.clear_context("key1")

        # Verify key1 is empty but key2 is intact
        context1 = await context_manager.get_context("key1")
        context2 = await context_manager.get_context("key2")

        assert len(context1) == 0
        assert len(context2) == 1


# ---------------------------------------------------------------------------
# TestFormatContextForOllama
# ---------------------------------------------------------------------------


class TestFormatContextForOllama:
    """Test LLMContextManager.format_context_for_ollama()."""

    def test_empty_context(self):
        """Test formatting an empty context."""
        result = LLMContextManager.format_context_for_ollama([])
        assert result == []

    def test_single_message(self):
        """Test formatting a single message."""
        context = [
            {
                "id": 1,
                "context_key": "test_key",
                "role": "user",
                "content": "Hello",
                "timestamp": 12345.67,
                "created_at": "2024-01-01 12:00:00",
            }
        ]

        result = LLMContextManager.format_context_for_ollama(context)

        assert len(result) == 1
        assert result[0] == {"role": "user", "content": "Hello"}

    def test_multiple_messages(self):
        """Test formatting multiple messages."""
        context = [
            {
                "id": 1,
                "context_key": "test_key",
                "role": "user",
                "content": "Hello",
                "timestamp": 12345.67,
                "created_at": "2024-01-01 12:00:00",
            },
            {
                "id": 2,
                "context_key": "test_key",
                "role": "assistant",
                "content": "Hi there!",
                "timestamp": 12345.68,
                "created_at": "2024-01-01 12:00:01",
            },
            {
                "id": 3,
                "context_key": "test_key",
                "role": "user",
                "content": "How are you?",
                "timestamp": 12345.69,
                "created_at": "2024-01-01 12:00:02",
            },
        ]

        result = LLMContextManager.format_context_for_ollama(context)

        assert len(result) == 3
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there!"}
        assert result[2] == {"role": "user", "content": "How are you?"}

    def test_only_role_and_content(self):
        """Test that only role and content fields are included."""
        context = [
            {
                "id": 1,
                "context_key": "test_key",
                "role": "user",
                "content": "Test",
                "timestamp": 12345.67,
                "created_at": "2024-01-01 12:00:00",
            }
        ]

        result = LLMContextManager.format_context_for_ollama(context)

        # Should only have role and content keys
        assert set(result[0].keys()) == {"role", "content"}

    async def test_integration_with_get_context(self, context_manager):
        """Test formatting context retrieved from get_context()."""
        # Add messages
        await context_manager.add_message("test_key", "user", "Hello")
        await context_manager.add_message("test_key", "assistant", "Hi!")

        # Get context and format it
        context = await context_manager.get_context("test_key")
        result = LLMContextManager.format_context_for_ollama(context)

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi!"}


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test error handling in LLMContextManager methods."""

    async def test_get_context_error_returns_empty_list(self, context_manager, mock_logger):
        """Test that get_context returns empty list on error and logs it."""
        # Force an error by using invalid context_key type
        # This is a bit contrived, but we want to test error handling
        context_manager.async_db = None  # This will cause an error

        result = await context_manager.get_context("test_key")

        assert result == []
        mock_logger.error.assert_called_once()

    async def test_add_message_error_returns_false(self, async_db_manager, mock_logger):
        """Test that add_message returns False on error and logs it."""
        manager = LLMContextManager(async_db_manager, mock_logger)

        # Force an error by closing the database connection
        manager.async_db = None  # This will cause an error

        result = await manager.add_message("test_key", "user", "Test")

        assert result is False
        mock_logger.error.assert_called_once()

    async def test_clear_context_error_returns_false(self, async_db_manager, mock_logger):
        """Test that clear_context returns False on error and logs it."""
        manager = LLMContextManager(async_db_manager, mock_logger)

        # Force an error
        manager.async_db = None  # This will cause an error

        result = await manager.clear_context("test_key")

        assert result is False
        mock_logger.error.assert_called_once()

    async def test_prune_context_error_logged_but_no_exception(self, async_db_manager, mock_logger):
        """Test that prune_context logs errors but doesn't raise exceptions."""
        manager = LLMContextManager(async_db_manager, mock_logger)

        # Force an error
        manager.async_db = None  # This will cause an error

        # Should not raise any exceptions
        await manager.prune_context("test_key", max_exchanges=5)

        # Error should be logged
        mock_logger.error.assert_called_once()


# ---------------------------------------------------------------------------
# TestAddCommandContext
# ---------------------------------------------------------------------------


class TestAddCommandContext:
    """Test LLMContextManager.add_command_context()."""

    async def test_add_command_context_success(self, context_manager):
        """Test adding command context successfully."""
        result = await context_manager.add_command_context(
            context_key="test_key",
            command_name="wx",
            user_input="!wx Austin",
            bot_response="Austin: 72°F, Sunny",
            sender_name="TestUser",
        )
        assert result is True

        # Verify both user and assistant messages were stored
        context = await context_manager.get_context("test_key")
        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "!wx Austin"
        assert context[0]["command_name"] == "wx"
        assert context[0]["sender_name"] == "TestUser"
        assert context[1]["role"] == "assistant"
        assert context[1]["content"] == "Austin: 72°F, Sunny"
        assert context[1]["command_name"] == "wx"
        assert context[1]["sender_name"] == "TestUser"

    async def test_add_command_context_without_sender_name(self, context_manager):
        """Test adding command context without sender_name."""
        result = await context_manager.add_command_context(
            context_key="test_key",
            command_name="ping",
            user_input="!ping",
            bot_response="Pong!",
        )
        assert result is True

        context = await context_manager.get_context("test_key")
        assert len(context) == 2
        assert context[0]["sender_name"] is None
        assert context[1]["sender_name"] is None

    async def test_command_context_timestamps(self, context_manager):
        """Test that command context entries have slightly different timestamps."""
        await context_manager.add_command_context(
            context_key="test_key",
            command_name="wx",
            user_input="!wx Austin",
            bot_response="Austin: 72°F, Sunny",
        )

        context = await context_manager.get_context("test_key")
        assert len(context) == 2
        # Assistant timestamp should be slightly after user timestamp
        assert context[1]["timestamp"] > context[0]["timestamp"]

    async def test_command_context_mixed_with_regular_messages(self, context_manager):
        """Test command context can be mixed with regular LLM messages."""
        # Add regular message
        await context_manager.add_message("test_key", "user", "Hello")
        await context_manager.add_message("test_key", "assistant", "Hi!")

        # Add command context
        await context_manager.add_command_context(
            context_key="test_key",
            command_name="wx",
            user_input="!wx Austin",
            bot_response="Austin: 72°F",
        )

        # Add another regular message
        await context_manager.add_message("test_key", "user", "Thanks")

        context = await context_manager.get_context("test_key")
        assert len(context) == 5

        # Check that we have both regular messages and command context
        regular_messages = [msg for msg in context if msg["command_name"] is None]
        command_messages = [msg for msg in context if msg["command_name"] == "wx"]

        assert len(regular_messages) == 3  # "Hello", "Hi!", "Thanks"
        assert len(command_messages) == 2  # user command + assistant response

    async def test_command_context_error_handling(self, async_db_manager, mock_logger):
        """Test that add_command_context returns False on error and logs it."""
        manager = LLMContextManager(async_db_manager, mock_logger)
        manager.async_db = None  # Force error

        result = await manager.add_command_context(
            context_key="test_key",
            command_name="wx",
            user_input="!wx Austin",
            bot_response="Austin: 72°F",
        )

        assert result is False
        mock_logger.error.assert_called_once()


# ---------------------------------------------------------------------------
# TestCommandContextFields
# ---------------------------------------------------------------------------


class TestCommandContextFields:
    """Test that command_name and sender_name fields are properly handled."""

    async def test_get_context_includes_new_fields(self, context_manager):
        """Test that get_context includes command_name and sender_name."""
        await context_manager.add_message("test_key", "user", "Regular message")

        context = await context_manager.get_context("test_key")
        assert len(context) == 1
        assert "command_name" in context[0]
        assert "sender_name" in context[0]
        assert context[0]["command_name"] is None
        assert context[0]["sender_name"] is None

    async def test_format_context_with_command_fields(self, context_manager):
        """Test that format_context_for_ollama works with command context."""
        await context_manager.add_command_context(
            context_key="test_key",
            command_name="wx",
            user_input="!wx Austin",
            bot_response="Austin: 72°F",
            sender_name="TestUser",
        )

        context = await context_manager.get_context("test_key")
        formatted = LLMContextManager.format_context_for_ollama(context)

        # Formatted context should only have role and content
        assert len(formatted) == 2
        assert formatted[0] == {"role": "user", "content": "!wx Austin"}
        assert formatted[1] == {"role": "assistant", "content": "Austin: 72°F"}
        # command_name and sender_name should not be in formatted output
        assert "command_name" not in formatted[0]
        assert "sender_name" not in formatted[0]
