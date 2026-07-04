"""Ollama HTTP client for LLM text generation.

This module provides an async HTTP client for interacting with Ollama's API.
It handles chat completions with context management and health checking.
"""

import logging
from typing import Any, Optional

import aiohttp


class OllamaClient:
    """Async HTTP client for Ollama API.

    This client provides methods to generate text responses using Ollama's chat API
    and to check the health of the Ollama service.

    Attributes:
        endpoint: Base URL of the Ollama API (e.g., "http://localhost:11434")
        model: Name of the Ollama model to use (e.g., "llama2", "mistral")
        api_key: Optional API key for authentication (not commonly used with Ollama)
        timeout: Request timeout configuration
        session: Optional aiohttp ClientSession for connection reuse
        logger: Logger instance for error and info logging
    """

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        logger: Optional[logging.Logger] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Initialize the Ollama API client.

        Args:
            endpoint: Base URL of the Ollama API (e.g., "http://localhost:11434")
            model: Name of the Ollama model to use (e.g., "llama2", "mistral")
            api_key: Optional API key for authentication (default: None)
            timeout: Request timeout in seconds (default: 30)
            logger: Optional logger instance. If None, creates a default logger.
            session: Optional existing aiohttp session to reuse. If None, creates new sessions as needed.
        """
        self.endpoint = endpoint.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = session
        self.logger = logger or logging.getLogger(__name__)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session.

        Returns:
            An active aiohttp ClientSession instance.
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session

    async def generate(
        self,
        prompt: str,
        context: Optional[list[dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a text response using Ollama's chat API.

        This method sends a chat completion request to Ollama with the provided prompt,
        optional conversation context, and system instructions.

        Args:
            prompt: The user's prompt/question to send to the LLM
            context: Optional list of prior messages in format [{"role": "user"|"assistant", "content": "text"}, ...]
            system_prompt: Optional system instructions to guide model behavior

        Returns:
            The generated text response from the LLM.

        Raises:
            aiohttp.ClientError: If there's a connection error
            aiohttp.ServerTimeoutError: If the request times out
            ValueError: If the API response is malformed or missing expected fields
        """
        url = f"{self.endpoint}/api/chat"

        # Build messages list: system prompt (if any) + context + current prompt
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if context:
            messages.extend(context)

        messages.append({"role": "user", "content": prompt})

        # Prepare request payload
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()

                # Extract the assistant's message from the response
                if "message" not in data:
                    raise ValueError("Response missing 'message' field")

                message = data["message"]
                if not isinstance(message, dict) or "content" not in message:
                    raise ValueError("Response 'message' field malformed")

                content = message["content"]
                if not isinstance(content, str):
                    raise ValueError("Response 'content' is not a string")

                return content.strip()

        except aiohttp.ClientError as e:
            self.logger.error(f"Ollama API connection error: {e}")
            raise
        except aiohttp.ServerTimeoutError as e:
            self.logger.error(f"Ollama API timeout: {e}")
            raise
        except ValueError as e:
            self.logger.error(f"Ollama API response parsing error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during Ollama generate: {e}")
            raise

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Send a chat completion request with optional tool definitions.

        This method sends a chat completion request to Ollama's /api/chat endpoint
        with support for tool calling. The LLM can request to call tools by
        returning tool_calls in the response.

        Args:
            messages: List of message dicts in format [{"role": "user"|"assistant"|"system", "content": "text"}, ...]
            tools: Optional list of tool definitions in OpenAI function format
            stream: Whether to stream the response (default: False)

        Returns:
            Full response dict from Ollama API including:
            - message: The assistant's message with content and optional tool_calls
            - done: Boolean indicating if generation is complete
            - model: The model name used
            Other fields may be present depending on Ollama version

        Raises:
            aiohttp.ClientError: If there's a connection error
            aiohttp.ServerTimeoutError: If the request times out
            ValueError: If the API response is malformed or missing expected fields
        """
        url = f"{self.endpoint}/api/chat"

        # Prepare request payload
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()

                # Validate response structure
                if "message" not in data:
                    raise ValueError("Response missing 'message' field")

                message = data["message"]
                if not isinstance(message, dict):
                    raise ValueError("Response 'message' field is not a dict")

                # Return full response including tool_calls if present
                return data

        except aiohttp.ClientError as e:
            self.logger.error(f"Ollama API connection error: {e}")
            raise
        except aiohttp.ServerTimeoutError as e:
            self.logger.error(f"Ollama API timeout: {e}")
            raise
        except ValueError as e:
            self.logger.error(f"Ollama API response parsing error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during Ollama chat: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if the Ollama service is available and responsive.

        This method tests connectivity to the Ollama API by calling the tags endpoint,
        which lists available models.

        Returns:
            True if the service is healthy and reachable, False otherwise.
        """
        url = f"{self.endpoint}/api/tags"

        try:
            session = await self._get_session()
            async with session.get(url) as response:
                response.raise_for_status()
                # If we can successfully get a response, the service is healthy
                await response.json()
                return True
        except Exception as e:
            self.logger.error(f"Ollama health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the aiohttp session if it was created by this client.

        This method should be called when the client is no longer needed to ensure
        proper cleanup of network resources.
        """
        if self.session and not self.session.closed:
            await self.session.close()
