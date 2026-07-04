"""LLM conversation context manager.

This module provides conversation history management for LLM interactions,
storing and retrieving message context from the database with automatic pruning.
"""

import logging
import time
from typing import Any, Optional

from .db_manager import AsyncDBManager


class LLMContextManager:
    """Manages LLM conversation context stored in the database.

    This class provides methods to store, retrieve, and manage conversation history
    for LLM interactions. It supports automatic pruning based on age and message count.

    Attributes:
        async_db: AsyncDBManager instance for database operations
        logger: Logger instance for error and info logging
    """

    def __init__(
        self,
        async_db: AsyncDBManager,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Initialize the LLM context manager.

        Args:
            async_db: AsyncDBManager instance for database operations
            logger: Optional logger instance. If None, creates a default logger.
        """
        self.async_db = async_db
        self.logger = logger or logging.getLogger(__name__)

    async def get_context(
        self,
        context_key: str,
        max_exchanges: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve recent conversation history from the database.

        Fetches the most recent messages for the given context key, limited by
        the number of exchanges (user-assistant pairs). Messages are ordered
        chronologically (oldest first) for proper conversation flow.

        Args:
            context_key: Unique identifier for the conversation context
                         (e.g., channel name, user pubkey, or DM identifier)
            max_exchanges: Maximum number of user-assistant exchange pairs to retrieve
                          (default: 10, meaning up to 20 messages total)

        Returns:
            List of message dictionaries with keys: id, context_key, role, content, timestamp, created_at
            Ordered chronologically (oldest first). Returns empty list if no history exists.
        """
        try:
            # Calculate max messages (2 per exchange: user + assistant)
            max_messages = max_exchanges * 2

            async with self.async_db.connection() as conn:
                async with conn.execute(
                    '''
                    SELECT id, context_key, role, content, timestamp, created_at
                    FROM llm_conversation_context
                    WHERE context_key = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    ''',
                    (context_key, max_messages),
                ) as cursor:
                    rows = await cursor.fetchall()

                    # Convert rows to dicts and reverse to chronological order
                    messages = []
                    for row in reversed(rows):
                        messages.append({
                            'id': row[0],
                            'context_key': row[1],
                            'role': row[2],
                            'content': row[3],
                            'timestamp': row[4],
                            'created_at': row[5],
                        })

                    return messages

        except Exception as e:
            self.logger.error(f"Error retrieving context for key '{context_key}': {e}")
            return []

    async def add_message(
        self,
        context_key: str,
        role: str,
        content: str,
    ) -> bool:
        """Save a new message to the conversation context.

        Adds a message (user or assistant) to the database for the given context key.
        The timestamp is automatically set to the current Unix epoch time.

        Args:
            context_key: Unique identifier for the conversation context
            role: Message role - either "user" or "assistant"
            content: The message content/text

        Returns:
            True if the message was saved successfully, False otherwise.
        """
        try:
            timestamp = time.time()

            async with self.async_db.connection() as conn:
                await conn.execute(
                    '''
                    INSERT INTO llm_conversation_context (context_key, role, content, timestamp)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (context_key, role, content, timestamp),
                )
                await conn.commit()

            return True

        except Exception as e:
            self.logger.error(
                f"Error adding message to context '{context_key}' (role={role}): {e}"
            )
            return False

    async def prune_context(
        self,
        context_key: str,
        max_exchanges: int = 10,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Remove old messages from the conversation context.

        Prunes the context by removing messages that exceed the maximum exchange count
        or are older than the specified time-to-live. This helps prevent unbounded
        database growth and keeps conversations focused on recent history.

        Args:
            context_key: Unique identifier for the conversation context
            max_exchanges: Maximum number of user-assistant exchange pairs to keep
                          (default: 10, meaning up to 20 messages total)
            ttl_seconds: Optional time-to-live in seconds. Messages older than this
                        will be deleted regardless of max_exchanges. If None, no age-based pruning.
        """
        try:
            async with self.async_db.connection() as conn:
                # First, delete messages older than TTL if specified
                if ttl_seconds is not None:
                    cutoff_timestamp = time.time() - ttl_seconds
                    await conn.execute(
                        '''
                        DELETE FROM llm_conversation_context
                        WHERE context_key = ? AND timestamp < ?
                        ''',
                        (context_key, cutoff_timestamp),
                    )

                # Then, keep only the most recent max_exchanges * 2 messages
                max_messages = max_exchanges * 2
                await conn.execute(
                    '''
                    DELETE FROM llm_conversation_context
                    WHERE context_key = ? AND id NOT IN (
                        SELECT id FROM llm_conversation_context
                        WHERE context_key = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    )
                    ''',
                    (context_key, context_key, max_messages),
                )

                await conn.commit()

        except Exception as e:
            self.logger.error(f"Error pruning context for key '{context_key}': {e}")
            # Don't raise - pruning failures shouldn't break the command

    async def clear_context(self, context_key: str) -> bool:
        """Delete all messages for a given conversation context.

        Removes all stored messages for the specified context key, effectively
        resetting the conversation history.

        Args:
            context_key: Unique identifier for the conversation context to clear

        Returns:
            True if the context was cleared successfully, False otherwise.
        """
        try:
            async with self.async_db.connection() as conn:
                await conn.execute(
                    '''
                    DELETE FROM llm_conversation_context
                    WHERE context_key = ?
                    ''',
                    (context_key,),
                )
                await conn.commit()

            self.logger.info(f"Cleared context for key '{context_key}'")
            return True

        except Exception as e:
            self.logger.error(f"Error clearing context for key '{context_key}': {e}")
            return False

    @staticmethod
    def format_context_for_ollama(
        context: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Convert database context records to Ollama message format.

        Transforms the database representation of conversation history into the
        format expected by OllamaClient.generate()'s context parameter.

        Args:
            context: List of message dicts from get_context() with keys:
                    id, context_key, role, content, timestamp, created_at

        Returns:
            List of message dicts in Ollama format with keys: role, content
            Example: [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        """
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
            }
            for msg in context
        ]
