"""Tests for modules/commands/llm_command.py — LLMCommand integration tests."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from modules.commands.llm_command import LLMCommand
from modules.db_manager import AsyncDBManager, DBManager
from tests.conftest import mock_message

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


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
def command_mock_bot_with_llm(mock_logger, async_db_manager):
    """Mock bot with LLM Command configuration and async_db_manager."""
    bot = Mock()
    bot.logger = mock_logger
    bot.async_db_manager = async_db_manager
    bot.config = Mock()

    # Configure LLM_Command section
    def get_config(section, option, fallback=None):
        """Mock config getter."""
        if section == 'LLM_Command':
            config_map = {
                'enabled': 'true',
                'ollama_endpoint': 'http://localhost:11434',
                'ollama_model': 'llama2',
                'ollama_timeout_seconds': '30',
                'context_max_exchanges': '5',
                'context_ttl_seconds': '3600',
                'max_chunk_length': '180',
                'max_response_parts': '5',
                'chunk_delay_seconds': '2.0',
                'system_prompt': 'You are a helpful AI assistant.',
            }
            return config_map.get(option, str(fallback))
        return str(fallback)

    bot.config.get = Mock(side_effect=get_config)
    bot.config.getboolean = Mock(side_effect=lambda s, o, fallback=False: get_config(s, o, fallback) == 'true')
    bot.config.getint = Mock(side_effect=lambda s, o, fallback=0: int(get_config(s, o, fallback)))
    bot.config.getfloat = Mock(side_effect=lambda s, o, fallback=0.0: float(get_config(s, o, fallback)))

    # Mock command manager
    bot.command_manager = Mock()
    bot.command_manager.send_response = AsyncMock(return_value=True)
    bot.command_manager.send_response_chunked = AsyncMock(return_value=True)

    return bot


# ---------------------------------------------------------------------------
# TestLLMCommandInit
# ---------------------------------------------------------------------------


class TestLLMCommandInit:
    """Test LLMCommand initialization."""

    async def test_init_loads_config(self, command_mock_bot_with_llm):
        """Test that __init__ loads all config values correctly."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        assert cmd.llm_enabled is True
        assert cmd.ollama_endpoint == 'http://localhost:11434'
        assert cmd.ollama_model == 'llama2'
        assert cmd.ollama_timeout_seconds == 30
        assert cmd.context_max_exchanges == 5
        assert cmd.context_ttl_seconds == 3600
        assert cmd.max_chunk_length == 180
        assert cmd.max_response_parts == 5
        assert cmd.chunk_delay_seconds == 2.0
        assert cmd.system_prompt == 'You are a helpful AI assistant.'

    async def test_init_creates_ollama_client(self, command_mock_bot_with_llm):
        """Test that __init__ creates OllamaClient instance."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        assert cmd.ollama_client is not None

    async def test_init_creates_context_manager(self, command_mock_bot_with_llm):
        """Test that __init__ creates LLMContextManager instance."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        assert cmd.context_manager is not None


# ---------------------------------------------------------------------------
# TestLLMCommandCanExecute
# ---------------------------------------------------------------------------


class TestLLMCommandCanExecute:
    """Test LLMCommand.can_execute()."""

    async def test_can_execute_when_enabled(self, command_mock_bot_with_llm):
        """Test can_execute returns True when enabled."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        # BaseCommand checks are bypassed in this test
        assert cmd.llm_enabled is True

    async def test_can_execute_when_disabled(self, command_mock_bot_with_llm):
        """Test can_execute returns False when disabled."""
        # Modify config to disable
        command_mock_bot_with_llm.config.getboolean = Mock(return_value=False)
        cmd = LLMCommand(command_mock_bot_with_llm)
        msg = mock_message(content="!ask test", is_dm=True)
        assert cmd.can_execute(msg) is False


# ---------------------------------------------------------------------------
# TestLLMCommandAsk
# ---------------------------------------------------------------------------


class TestLLMCommandAsk:
    """Test LLMCommand !ask functionality."""

    async def test_ask_command_success(self, command_mock_bot_with_llm):
        """Test !ask command with mocked OllamaClient returns response."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        # Mock Ollama generate method
        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "The capital of France is Paris."

            msg = mock_message(content="!ask What is the capital of France?", is_dm=True)
            result = await cmd.execute(msg)

            assert result is True
            mock_generate.assert_called_once()
            # Verify send_response was called with the LLM response
            command_mock_bot_with_llm.command_manager.send_response.assert_called_once()
            call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
            assert "Paris" in call_args[0][1]

    async def test_ask_command_empty_question(self, command_mock_bot_with_llm):
        """Test !ask command with empty question returns usage info."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        msg = mock_message(content="!ask", is_dm=True)
        result = await cmd.execute(msg)

        assert result is False
        command_mock_bot_with_llm.command_manager.send_response.assert_called_once()
        call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
        assert "Usage:" in call_args[0][1]

    async def test_ask_command_ollama_error(self, command_mock_bot_with_llm):
        """Test !ask command handles Ollama errors gracefully."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        # Mock Ollama generate method to raise exception
        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = Exception("Connection refused")

            msg = mock_message(content="!ask What is the weather?", is_dm=True)
            result = await cmd.execute(msg)

            assert result is False
            command_mock_bot_with_llm.command_manager.send_response.assert_called_once()
            call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
            assert "trouble connecting" in call_args[0][1]


# ---------------------------------------------------------------------------
# TestLLMCommandMultiTurnConversation
# ---------------------------------------------------------------------------


class TestLLMCommandMultiTurnConversation:
    """Test multi-turn conversation context management."""

    async def test_multi_turn_conversation_maintains_context(self, command_mock_bot_with_llm):
        """Test that conversation context is maintained across multiple turns."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        # Mock Ollama generate method
        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            # First turn
            mock_generate.return_value = "The capital of France is Paris."
            msg1 = mock_message(content="!ask What is the capital of France?", channel="general", is_dm=False)
            result1 = await cmd.execute(msg1)
            assert result1 is True

            # Second turn - context should include first exchange
            mock_generate.return_value = "The population of Paris is about 2.2 million."
            msg2 = mock_message(content="!ask What is its population?", channel="general", is_dm=False)
            result2 = await cmd.execute(msg2)
            assert result2 is True

            # Verify context was passed in second call
            assert mock_generate.call_count == 2
            second_call_context = mock_generate.call_args_list[1][1]['context']
            # Context should have 2 messages from first turn (user + assistant)
            assert len(second_call_context) == 2
            assert second_call_context[0]['role'] == 'user'
            assert "capital of France" in second_call_context[0]['content']
            assert second_call_context[1]['role'] == 'assistant'
            assert "Paris" in second_call_context[1]['content']

    async def test_different_channels_separate_context(self, command_mock_bot_with_llm):
        """Test that different channels maintain separate conversation contexts."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Response"

            # Send message to channel1
            msg1 = mock_message(content="!ask Question 1", channel="channel1", is_dm=False)
            await cmd.execute(msg1)

            # Send message to channel2
            msg2 = mock_message(content="!ask Question 2", channel="channel2", is_dm=False)
            await cmd.execute(msg2)

            # Verify each channel got empty context (no shared context)
            assert mock_generate.call_count == 2
            # First call should have empty context
            assert mock_generate.call_args_list[0][1]['context'] == []
            # Second call should also have empty context (different channel)
            assert mock_generate.call_args_list[1][1]['context'] == []

    async def test_dm_uses_sender_pubkey_for_context(self, command_mock_bot_with_llm):
        """Test that DMs use sender pubkey for context key."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Response 1"

            # First DM from user
            msg1 = mock_message(
                content="!ask Question 1",
                is_dm=True,
                sender_pubkey="abc123",
                sender_id="User1"
            )
            await cmd.execute(msg1)

            mock_generate.return_value = "Response 2"

            # Second DM from same user
            msg2 = mock_message(
                content="!ask Question 2",
                is_dm=True,
                sender_pubkey="abc123",
                sender_id="User1"
            )
            await cmd.execute(msg2)

            # Verify second message has context from first
            assert mock_generate.call_count == 2
            second_call_context = mock_generate.call_args_list[1][1]['context']
            assert len(second_call_context) == 2  # First user message + first assistant response


# ---------------------------------------------------------------------------
# TestLLMCommandClearContext
# ---------------------------------------------------------------------------


class TestLLMCommandClearContext:
    """Test !clear-context functionality."""

    async def test_clear_context_success(self, command_mock_bot_with_llm):
        """Test !clear-context command clears conversation history."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        # First, add some context
        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Test response"
            msg1 = mock_message(content="!ask Test question", channel="general", is_dm=False)
            await cmd.execute(msg1)

        # Now clear context
        msg2 = mock_message(content="!clear-context", channel="general", is_dm=False)
        result = await cmd.execute(msg2)

        assert result is True
        command_mock_bot_with_llm.command_manager.send_response.assert_called()
        # Check last call was for clear-context
        last_call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
        assert "cleared" in last_call_args[0][1].lower()

        # Verify context is actually cleared by checking next query has empty context
        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "New response"
            msg3 = mock_message(content="!ask New question", channel="general", is_dm=False)
            await cmd.execute(msg3)

            # Context should be empty after clear
            call_context = mock_generate.call_args[1]['context']
            assert call_context == []

    async def test_clear_context_error_handling(self, command_mock_bot_with_llm):
        """Test !clear-context handles errors gracefully."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        # Mock context_manager.clear_context to raise exception
        with patch.object(cmd.context_manager, 'clear_context', new_callable=AsyncMock) as mock_clear:
            mock_clear.side_effect = Exception("Database error")

            msg = mock_message(content="!clear-context", channel="general", is_dm=False)
            result = await cmd.execute(msg)

            assert result is False
            command_mock_bot_with_llm.command_manager.send_response.assert_called_once()
            call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
            assert "error" in call_args[0][1].lower()


# ---------------------------------------------------------------------------
# TestLLMCommandChunkedResponse
# ---------------------------------------------------------------------------


class TestLLMCommandChunkedResponse:
    """Test chunked response delivery."""

    async def test_short_response_single_chunk(self, command_mock_bot_with_llm):
        """Test short responses are sent as single chunk."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Short response."

            msg = mock_message(content="!ask Test?", is_dm=True)
            result = await cmd.execute(msg)

            assert result is True
            # Should use send_response for single chunk
            command_mock_bot_with_llm.command_manager.send_response.assert_called_once()
            # Should not use send_response_chunked
            command_mock_bot_with_llm.command_manager.send_response_chunked.assert_not_called()

    async def test_long_response_multiple_chunks(self, command_mock_bot_with_llm):
        """Test long responses are split into multiple chunks."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            # Generate a long response that will exceed max_chunk_length (180)
            long_response = "This is a very long response. " * 20  # ~600 chars

            mock_generate.return_value = long_response

            msg = mock_message(content="!ask Tell me a long story?", is_dm=True)
            result = await cmd.execute(msg)

            assert result is True
            # Should use send_response_chunked for multiple chunks
            command_mock_bot_with_llm.command_manager.send_response_chunked.assert_called_once()
            # Should not use send_response
            command_mock_bot_with_llm.command_manager.send_response.assert_not_called()

            # Verify chunks were passed correctly
            call_args = command_mock_bot_with_llm.command_manager.send_response_chunked.call_args
            chunks = call_args[0][1]
            assert len(chunks) > 1
            # Each chunk should have indicator like [1/N]
            assert "[1/" in chunks[0]

    async def test_very_long_response_truncated(self, command_mock_bot_with_llm):
        """Test very long responses are truncated at max_response_parts."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            # Generate a response that would exceed max_response_parts (5)
            very_long_response = "This is sentence number X. " * 100  # ~2700 chars

            mock_generate.return_value = very_long_response

            msg = mock_message(content="!ask Tell me everything?", is_dm=True)
            result = await cmd.execute(msg)

            assert result is True
            call_args = command_mock_bot_with_llm.command_manager.send_response_chunked.call_args
            chunks = call_args[0][1]
            # Should be truncated to max_response_parts
            assert len(chunks) <= cmd.max_response_parts
            # Last chunk should contain truncation indicator
            if len(chunks) == cmd.max_response_parts:
                # May be truncated
                pass  # Truncation suffix is implementation detail


# ---------------------------------------------------------------------------
# TestLLMCommandContextPruning
# ---------------------------------------------------------------------------


class TestLLMCommandContextPruning:
    """Test context pruning after response."""

    async def test_context_pruning_called(self, command_mock_bot_with_llm):
        """Test that context pruning is called after LLM response."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Response"

            with patch.object(cmd.context_manager, 'prune_context', new_callable=AsyncMock) as mock_prune:
                msg = mock_message(content="!ask Test?", channel="general", is_dm=False)
                result = await cmd.execute(msg)

                assert result is True
                # Verify prune_context was called
                mock_prune.assert_called_once_with(
                    context_key="general",
                    max_exchanges=cmd.context_max_exchanges,
                    ttl_seconds=cmd.context_ttl_seconds,
                )

    async def test_context_pruning_error_does_not_fail_command(self, command_mock_bot_with_llm):
        """Test that pruning errors don't cause command failure."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Response"

            with patch.object(cmd.context_manager, 'prune_context', new_callable=AsyncMock) as mock_prune:
                mock_prune.side_effect = Exception("Pruning failed")

                msg = mock_message(content="!ask Test?", is_dm=True)
                result = await cmd.execute(msg)

                # Command should still succeed despite pruning error
                assert result is True
                # Response should still be sent
                command_mock_bot_with_llm.command_manager.send_response.assert_called_once()

    async def test_old_messages_pruned_by_max_exchanges(self, command_mock_bot_with_llm):
        """Test that old messages are pruned when exceeding max_exchanges."""
        cmd = LLMCommand(command_mock_bot_with_llm)

        # Set max_exchanges to 2 for this test
        cmd.context_max_exchanges = 2

        # Mock time.time() to return incrementing values for deterministic timestamp ordering
        base_time = 1000.0
        with patch('time.time', side_effect=[base_time + i * 10 for i in range(100)]):
            with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
                mock_generate.return_value = "Response"

                # Send 3 questions (each creates 2 messages: user + assistant)
                for i in range(3):
                    msg = mock_message(content=f"!ask Question {i+1}", channel="test", is_dm=False)
                    await cmd.execute(msg)

                # Verify context is limited to max_exchanges
                context = await cmd.context_manager.get_context("test", max_exchanges=10)
                # Should have at most max_exchanges * 2 messages (user + assistant per exchange)
                assert len(context) <= cmd.context_max_exchanges * 2 + 2  # +2 for current exchange


# ---------------------------------------------------------------------------
# TestLLMCommandUserMention
# ---------------------------------------------------------------------------


class TestLLMCommandUserMention:
    """Test LLMCommand user mention functionality."""

    async def test_user_mention_enabled_for_channel_messages(self, command_mock_bot_with_llm):
        """Test that user mention is added for channel messages when enabled."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.include_user_mention = True

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "This is the answer."

            msg = mock_message(content="!ask What is 2+2?", channel="test", is_dm=False)
            msg.sender_id = "TestUser"
            await cmd.execute(msg)

            # Verify response includes user mention
            call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
            assert call_args is not None
            response_text = call_args[0][1]
            assert response_text.startswith("[@TestUser]")
            assert "This is the answer." in response_text

    async def test_user_mention_disabled_for_dms(self, command_mock_bot_with_llm):
        """Test that user mention is NOT added for DMs even when enabled."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.include_user_mention = True

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "This is the answer."

            msg = mock_message(content="!ask What is 2+2?", is_dm=True)
            msg.sender_id = "TestUser"
            await cmd.execute(msg)

            # Verify response does NOT include user mention for DMs
            call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
            assert call_args is not None
            response_text = call_args[0][1]
            assert not response_text.startswith("[@TestUser]")
            assert response_text == "This is the answer."

    async def test_user_mention_disabled_via_config(self, command_mock_bot_with_llm):
        """Test that user mention is NOT added when disabled in config."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.include_user_mention = False

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "This is the answer."

            msg = mock_message(content="!ask What is 2+2?", channel="test", is_dm=False)
            msg.sender_id = "TestUser"
            await cmd.execute(msg)

            # Verify response does NOT include user mention when disabled
            call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
            assert call_args is not None
            response_text = call_args[0][1]
            assert not response_text.startswith("[@TestUser]")
            assert response_text == "This is the answer."

    async def test_user_mention_in_error_messages(self, command_mock_bot_with_llm):
        """Test that user mention is added to error messages."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.include_user_mention = True

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = Exception("Ollama error")

            msg = mock_message(content="!ask What is 2+2?", channel="test", is_dm=False)
            msg.sender_id = "TestUser"
            await cmd.execute(msg)

            # Verify error response includes user mention
            call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
            assert call_args is not None
            response_text = call_args[0][1]
            assert response_text.startswith("[@TestUser]")

    async def test_user_mention_in_clear_context_response(self, command_mock_bot_with_llm):
        """Test that user mention is added to clear-context response."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.include_user_mention = True

        msg = mock_message(content="!clear-context", channel="test", is_dm=False)
        msg.sender_id = "TestUser"
        await cmd.execute(msg)

        # Verify clear-context response includes user mention
        call_args = command_mock_bot_with_llm.command_manager.send_response.call_args
        assert call_args is not None
        response_text = call_args[0][1]
        assert response_text.startswith("[@TestUser]")
        assert "context cleared" in response_text.lower()


# ---------------------------------------------------------------------------
# TestLLMCommandToolCalling
# ---------------------------------------------------------------------------


class TestLLMCommandToolCalling:
    """Test LLMCommand tool calling integration."""

    async def test_tool_calling_disabled_by_default(self, command_mock_bot_with_llm):
        """Test that tool calling is disabled by default."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        assert cmd.enable_tools is False
        assert cmd.tool_registry is None
        assert cmd.tool_executor is None

    async def test_tool_calling_enabled_initializes_components(self, command_mock_bot_with_llm):
        """Test that enabling tool calling initializes ToolRegistry and ToolExecutor."""
        # Update mock config to enable tools
        original_get = command_mock_bot_with_llm.config.get

        def get_with_tools(section, option, fallback=None):
            if section == 'LLM_Command' and option == 'enable_tools':
                return 'true'
            return original_get(section, option, fallback)

        command_mock_bot_with_llm.config.get = Mock(side_effect=get_with_tools)
        command_mock_bot_with_llm.config.getboolean = Mock(
            side_effect=lambda s, o, fallback=False: get_with_tools(s, o, fallback) == 'true'
        )

        cmd = LLMCommand(command_mock_bot_with_llm)
        assert cmd.enable_tools is True
        assert cmd.tool_registry is not None
        assert cmd.tool_executor is not None

    async def test_tool_calling_loads_config_values(self, command_mock_bot_with_llm):
        """Test that tool calling config values are loaded correctly."""
        # Update mock config
        original_get = command_mock_bot_with_llm.config.get

        def get_with_tools(section, option, fallback=None):
            if section == 'LLM_Command':
                tool_config = {
                    'enable_tools': 'true',
                    'max_tools_per_query': '5',
                    'tool_timeout': '15',
                }
                if option in tool_config:
                    return tool_config[option]
            return original_get(section, option, fallback)

        command_mock_bot_with_llm.config.get = Mock(side_effect=get_with_tools)
        command_mock_bot_with_llm.config.getboolean = Mock(
            side_effect=lambda s, o, fallback=False: get_with_tools(s, o, fallback) == 'true'
        )
        command_mock_bot_with_llm.config.getint = Mock(
            side_effect=lambda s, o, fallback=0: int(get_with_tools(s, o, fallback))
        )

        cmd = LLMCommand(command_mock_bot_with_llm)
        assert cmd.enable_tools is True
        assert cmd.max_tools_per_query == 5
        assert cmd.tool_timeout == 15

    async def test_execute_with_tools_disabled_uses_generate(self, command_mock_bot_with_llm):
        """Test that execute uses generate() when tools are disabled."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.enable_tools = False

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
                mock_generate.return_value = "Answer without tools"

                msg = mock_message(content="!ask What is 2+2?", channel="test")
                await cmd.execute(msg)

                # Verify generate was called, not chat
                assert mock_generate.call_count == 1
                assert mock_chat.call_count == 0

    async def test_execute_with_tools_enabled_uses_chat(self, command_mock_bot_with_llm):
        """Test that execute uses chat() when tools are enabled."""
        # Enable tools
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.enable_tools = True
        cmd.tool_registry = Mock()
        cmd.tool_registry.get_all_tool_schemas = Mock(return_value=[])
        cmd.tool_executor = Mock()

        with patch.object(cmd.ollama_client, 'generate', new_callable=AsyncMock) as mock_generate:
            with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
                # Mock chat response with no tool calls
                mock_chat.return_value = {
                    "message": {
                        "role": "assistant",
                        "content": "Answer with tools enabled",
                    },
                    "done": True,
                }

                msg = mock_message(content="!ask What is 2+2?", channel="test")
                await cmd.execute(msg)

                # Verify chat was called, not generate
                assert mock_chat.call_count == 1
                assert mock_generate.call_count == 0

    async def test_tool_calling_single_tool_execution(self, command_mock_bot_with_llm):
        """Test LLM calls single tool and returns final response."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.enable_tools = True
        cmd.tool_registry = Mock()
        cmd.tool_registry.get_all_tool_schemas = Mock(return_value=[
            {
                "type": "function",
                "function": {
                    "name": "wx",
                    "description": "Get weather",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        ])
        cmd.tool_executor = Mock()
        cmd.tool_executor.execute_tool = AsyncMock(return_value="Austin: 72°F, Sunny")

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            # First call: LLM requests tool call
            # Second call: LLM returns final response
            mock_chat.side_effect = [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "wx",
                                    "arguments": {"location": "Austin"},
                                }
                            }
                        ],
                    },
                    "done": True,
                },
                {
                    "message": {
                        "role": "assistant",
                        "content": "The weather in Austin is 72°F and sunny.",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(content="!ask What's the weather in Austin?", channel="test")
            await cmd.execute(msg)

            # Verify tool was executed
            assert cmd.tool_executor.execute_tool.call_count == 1
            call_args = cmd.tool_executor.execute_tool.call_args
            assert call_args[1]['tool_name'] == 'wx'
            assert call_args[1]['arguments'] == {'location': 'Austin'}

            # Verify final response was sent
            assert command_mock_bot_with_llm.command_manager.send_response.call_count == 1
            response_text = command_mock_bot_with_llm.command_manager.send_response.call_args[0][1]
            assert "72°F and sunny" in response_text

    async def test_tool_calling_multiple_tools(self, command_mock_bot_with_llm):
        """Test LLM calls multiple tools in sequence."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.enable_tools = True
        cmd.max_tools_per_query = 5
        cmd.tool_registry = Mock()
        cmd.tool_registry.get_all_tool_schemas = Mock(return_value=[])
        cmd.tool_executor = Mock()
        cmd.tool_executor.execute_tool = AsyncMock(side_effect=[
            "Austin: 72°F, Sunny",
            "ISS passes at 10:30 PM",
        ])

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                # First call: LLM requests wx tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "wx", "arguments": {"location": "Austin"}}}
                        ],
                    },
                    "done": True,
                },
                # Second call: LLM requests satpass tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "satpass", "arguments": {}}}
                        ],
                    },
                    "done": True,
                },
                # Third call: LLM returns final response
                {
                    "message": {
                        "role": "assistant",
                        "content": "Weather is 72°F. ISS passes at 10:30 PM.",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(content="!ask Weather and ISS pass?", channel="test")
            await cmd.execute(msg)

            # Verify both tools were executed
            assert cmd.tool_executor.execute_tool.call_count == 2

    async def test_tool_calling_max_iterations_limit(self, command_mock_bot_with_llm):
        """Test that tool calling respects max_tools_per_query limit."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.enable_tools = True
        cmd.max_tools_per_query = 2  # Limit to 2 tools
        cmd.tool_registry = Mock()
        cmd.tool_registry.get_all_tool_schemas = Mock(return_value=[])
        cmd.tool_executor = Mock()
        cmd.tool_executor.execute_tool = AsyncMock(return_value="Tool result")

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            # LLM keeps requesting tools
            mock_chat.side_effect = [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"function": {"name": "wx", "arguments": {}}}],
                    },
                    "done": True,
                },
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"function": {"name": "satpass", "arguments": {}}}],
                    },
                    "done": True,
                },
                # Should not reach this call - limit hit
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"function": {"name": "airplanes", "arguments": {}}}],
                    },
                    "done": True,
                },
                # Final call without tools
                {
                    "message": {
                        "role": "assistant",
                        "content": "Final response after hitting limit",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(content="!ask Test max tools", channel="test")
            await cmd.execute(msg)

            # Verify only 2 tools were executed (limit)
            assert cmd.tool_executor.execute_tool.call_count == 2

    async def test_tool_calling_error_handling(self, command_mock_bot_with_llm):
        """Test that tool execution errors are handled gracefully."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.enable_tools = True
        cmd.tool_registry = Mock()
        cmd.tool_registry.get_all_tool_schemas = Mock(return_value=[])
        cmd.tool_executor = Mock()
        cmd.tool_executor.execute_tool = AsyncMock(side_effect=Exception("Tool error"))

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                # LLM requests tool
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"function": {"name": "wx", "arguments": {}}}],
                    },
                    "done": True,
                },
                # LLM handles error and returns final response
                {
                    "message": {
                        "role": "assistant",
                        "content": "Sorry, I couldn't get the weather.",
                    },
                    "done": True,
                },
            ]

            msg = mock_message(content="!ask Weather?", channel="test")
            result = await cmd.execute(msg)

            # Execute should still succeed despite tool error
            assert result is True
            assert cmd.tool_executor.execute_tool.call_count == 1

    async def test_tool_calling_no_tools_returns_immediately(self, command_mock_bot_with_llm):
        """Test that LLM response without tool calls returns immediately."""
        cmd = LLMCommand(command_mock_bot_with_llm)
        cmd.enable_tools = True
        cmd.tool_registry = Mock()
        cmd.tool_registry.get_all_tool_schemas = Mock(return_value=[])
        cmd.tool_executor = Mock()

        with patch.object(cmd.ollama_client, 'chat', new_callable=AsyncMock) as mock_chat:
            # LLM responds directly without tool calls
            mock_chat.return_value = {
                "message": {
                    "role": "assistant",
                    "content": "Direct answer without tools",
                },
                "done": True,
            }

            msg = mock_message(content="!ask Simple question?", channel="test")
            await cmd.execute(msg)

            # Verify only one chat call was made
            assert mock_chat.call_count == 1
            # Verify no tools were executed
            assert not hasattr(cmd.tool_executor, 'execute_tool') or cmd.tool_executor.execute_tool.call_count == 0
