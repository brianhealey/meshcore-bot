"""Tests for modules/ollama_client.py — OllamaClient."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

from modules.ollama_client import OllamaClient

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
def ollama_client(mock_logger):
    """Create an OllamaClient instance for testing."""
    return OllamaClient(
        endpoint="http://localhost:11434",
        model="llama2",
        api_key=None,
        timeout=30,
        logger=mock_logger,
    )


def _make_mock_response(status: int, json_data: dict):
    """Create a mock aiohttp response."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data)
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _make_context_manager(mock_response):
    """Create a mock async context manager for aiohttp session methods."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------


class TestInit:
    """Test OllamaClient initialization."""

    def test_endpoint_stripped(self):
        """Test that endpoint trailing slashes are removed."""
        client = OllamaClient(endpoint="http://localhost:11434/", model="llama2")
        assert client.endpoint == "http://localhost:11434"

    def test_model_stored(self):
        """Test that model name is stored correctly."""
        client = OllamaClient(endpoint="http://localhost:11434", model="mistral")
        assert client.model == "mistral"

    def test_api_key_optional(self):
        """Test that api_key is optional."""
        client = OllamaClient(endpoint="http://localhost:11434", model="llama2")
        assert client.api_key is None

        client_with_key = OllamaClient(
            endpoint="http://localhost:11434", model="llama2", api_key="test-key"
        )
        assert client_with_key.api_key == "test-key"

    def test_timeout_configured(self):
        """Test that timeout is configured correctly."""
        client = OllamaClient(
            endpoint="http://localhost:11434", model="llama2", timeout=60
        )
        assert isinstance(client.timeout, aiohttp.ClientTimeout)
        assert client.timeout.total == 60

    def test_logger_default(self):
        """Test that logger is created if not provided."""
        client = OllamaClient(endpoint="http://localhost:11434", model="llama2")
        assert client.logger is not None


# ---------------------------------------------------------------------------
# TestGenerate
# ---------------------------------------------------------------------------


class TestGenerate:
    """Test OllamaClient.generate() method."""

    async def test_generate_success(self, ollama_client, mock_logger):
        """Test successful generate() call."""
        # Mock response
        mock_resp = _make_mock_response(
            200, {"message": {"role": "assistant", "content": "Hello, world!"}}
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session to return our mock
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            # Execute
            result = await ollama_client.generate("What is AI?")

        # Assert
        assert result == "Hello, world!"
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args.args[0] == "http://localhost:11434/api/chat"

    async def test_generate_with_context(self, ollama_client):
        """Test generate() with conversation context."""
        # Mock response
        mock_resp = _make_mock_response(
            200, {"message": {"role": "assistant", "content": "Response with context"}}
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session to return our mock
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            # Execute with context
            context = [
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": "Previous answer"},
            ]
            result = await ollama_client.generate("Follow-up question", context=context)

        # Assert
        assert result == "Response with context"
        call_args = mock_session.post.call_args
        payload = call_args.kwargs["json"]
        assert len(payload["messages"]) == 3  # context + new prompt
        assert payload["messages"][0]["content"] == "Previous question"
        assert payload["messages"][2]["content"] == "Follow-up question"

    async def test_generate_with_system_prompt(self, ollama_client):
        """Test generate() with system prompt."""
        # Mock response
        mock_resp = _make_mock_response(
            200, {"message": {"role": "assistant", "content": "Concise response"}}
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session to return our mock
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            # Execute with system prompt
            result = await ollama_client.generate(
                "What is AI?", system_prompt="Be concise"
            )

        # Assert
        assert result == "Concise response"
        call_args = mock_session.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "Be concise"

    async def test_generate_strips_whitespace(self, ollama_client):
        """Test that response content is stripped of whitespace."""
        # Mock response with extra whitespace
        mock_resp = _make_mock_response(
            200, {"message": {"role": "assistant", "content": "  Response  \n"}}
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session to return our mock
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            # Execute
            result = await ollama_client.generate("Question")

        # Assert - whitespace should be stripped
        assert result == "Response"

    async def test_generate_includes_api_key_header(self, mock_logger):
        """Test that API key is included in headers when provided."""
        client = OllamaClient(
            endpoint="http://localhost:11434",
            model="llama2",
            api_key="secret-key",
            logger=mock_logger,
        )

        # Mock response
        mock_resp = _make_mock_response(
            200, {"message": {"role": "assistant", "content": "Authenticated response"}}
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session to return our mock
        with patch.object(client, '_get_session', return_value=mock_session):
            # Execute
            await client.generate("Question")

        # Assert - Authorization header should be present
        call_args = mock_session.post.call_args
        headers = call_args.kwargs["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer secret-key"

    async def test_generate_missing_message_field(self, ollama_client, mock_logger):
        """Test that ValueError is raised when response is missing 'message' field."""
        # Mock response without 'message' field
        mock_resp = _make_mock_response(200, {"error": "Invalid request"})

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            with pytest.raises(ValueError, match="Response missing 'message' field"):
                await ollama_client.generate("Question")

        # Assert error was logged
        assert mock_logger.error.called

    async def test_generate_malformed_message_field(self, ollama_client, mock_logger):
        """Test that ValueError is raised when 'message' field is malformed."""
        # Mock response with malformed message (not a dict)
        mock_resp = _make_mock_response(200, {"message": "string instead of dict"})

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            with pytest.raises(ValueError, match="Response 'message' field malformed"):
                await ollama_client.generate("Question")

        # Assert error was logged
        assert mock_logger.error.called

    async def test_generate_missing_content_field(self, ollama_client, mock_logger):
        """Test that ValueError is raised when 'content' field is missing."""
        # Mock response without 'content' field
        mock_resp = _make_mock_response(
            200, {"message": {"role": "assistant", "text": "wrong field"}}
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            with pytest.raises(ValueError, match="Response 'message' field malformed"):
                await ollama_client.generate("Question")

        # Assert error was logged
        assert mock_logger.error.called

    async def test_generate_non_string_content(self, ollama_client, mock_logger):
        """Test that ValueError is raised when 'content' is not a string."""
        # Mock response with non-string content
        mock_resp = _make_mock_response(
            200, {"message": {"role": "assistant", "content": 123}}
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            with pytest.raises(ValueError, match="Response 'content' is not a string"):
                await ollama_client.generate("Question")

        # Assert error was logged
        assert mock_logger.error.called

    async def test_generate_client_error(self, ollama_client, mock_logger):
        """Test that aiohttp.ClientError is raised and logged on connection error."""
        # Mock session that raises ClientError
        mock_session = MagicMock()
        mock_session.post = MagicMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            with pytest.raises(aiohttp.ClientError):
                await ollama_client.generate("Question")

        # Assert error was logged
        assert mock_logger.error.called
        assert "connection error" in mock_logger.error.call_args[0][0].lower()

    async def test_generate_timeout_error(self, ollama_client, mock_logger):
        """Test that ServerTimeoutError is raised and logged on timeout."""
        # Mock session that raises ServerTimeoutError
        mock_session = MagicMock()
        mock_session.post = MagicMock(
            side_effect=aiohttp.ServerTimeoutError("Request timed out")
        )

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            with pytest.raises(aiohttp.ServerTimeoutError):
                await ollama_client.generate("Question")

        # Assert error was logged (ServerTimeoutError is caught by ClientError handler)
        assert mock_logger.error.called
        assert "connection error" in mock_logger.error.call_args[0][0].lower()


# ---------------------------------------------------------------------------
# TestHealthCheck
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Test OllamaClient.health_check() method."""

    async def test_health_check_success(self, ollama_client, mock_logger):
        """Test successful health check."""
        # Mock response
        mock_resp = _make_mock_response(200, {"models": []})

        # Mock session
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            result = await ollama_client.health_check()

        # Assert
        assert result is True
        mock_session.get.assert_called_once_with("http://localhost:11434/api/tags")

    async def test_health_check_failure(self, ollama_client, mock_logger):
        """Test failed health check."""
        # Mock session that raises exception
        mock_session = MagicMock()
        mock_session.get = MagicMock(
            side_effect=aiohttp.ClientError("Connection refused")
        )

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            result = await ollama_client.health_check()

        # Assert
        assert result is False
        assert mock_logger.error.called
        assert "health check failed" in mock_logger.error.call_args[0][0].lower()

    async def test_health_check_http_error(self, ollama_client, mock_logger):
        """Test health check with HTTP error response."""
        # Mock response that raises on raise_for_status
        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=500
            )
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=_make_context_manager(mock_resp))

        # Patch _get_session and execute
        with patch.object(ollama_client, '_get_session', return_value=mock_session):
            result = await ollama_client.health_check()

        # Assert
        assert result is False
        assert mock_logger.error.called


# ---------------------------------------------------------------------------
# TestClose
# ---------------------------------------------------------------------------


class TestClose:
    """Test OllamaClient.close() method."""

    async def test_close_session(self, ollama_client):
        """Test that close() closes the session."""
        # Create a mock session
        mock_session = AsyncMock()
        mock_session.closed = False
        ollama_client.session = mock_session

        # Execute
        await ollama_client.close()

        # Assert
        mock_session.close.assert_called_once()

    async def test_close_already_closed_session(self, ollama_client):
        """Test that close() handles already closed session."""
        # Create a mock session that's already closed
        mock_session = AsyncMock()
        mock_session.closed = True
        ollama_client.session = mock_session

        # Execute
        await ollama_client.close()

        # Assert - close should not be called if already closed
        mock_session.close.assert_not_called()

    async def test_close_no_session(self, ollama_client):
        """Test that close() handles no session gracefully."""
        ollama_client.session = None

        # Execute - should not raise
        await ollama_client.close()


# ---------------------------------------------------------------------------
# TestGetSession
# ---------------------------------------------------------------------------


class TestGetSession:
    """Test OllamaClient._get_session() method."""

    async def test_get_session_creates_new(self, ollama_client):
        """Test that _get_session() creates a new session if none exists."""
        ollama_client.session = None

        # Execute
        session = await ollama_client._get_session()

        # Assert
        assert session is not None
        assert isinstance(session, aiohttp.ClientSession)
        assert ollama_client.session is session

        # Cleanup
        await session.close()

    async def test_get_session_reuses_existing(self, ollama_client):
        """Test that _get_session() reuses existing session."""
        # Create initial session
        initial_session = aiohttp.ClientSession()
        ollama_client.session = initial_session

        # Execute
        session = await ollama_client._get_session()

        # Assert - should return the same session
        assert session is initial_session

        # Cleanup
        await initial_session.close()

    async def test_get_session_recreates_closed(self, ollama_client):
        """Test that _get_session() recreates a closed session."""
        # Create and close a session
        closed_session = aiohttp.ClientSession()
        await closed_session.close()
        ollama_client.session = closed_session

        # Execute
        session = await ollama_client._get_session()

        # Assert - should create a new session
        assert session is not closed_session
        assert not session.closed

        # Cleanup
        await session.close()
