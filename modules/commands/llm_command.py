#!/usr/bin/env python3
"""
LLM command for the MeshCore Bot
Provides conversational AI capabilities via Ollama with LoRa-optimized response chunking
"""

from typing import Optional

from ..llm_context_manager import LLMContextManager
from ..models import MeshMessage
from ..ollama_client import OllamaClient
from ..utils import chunk_llm_response
from .base_command import BaseCommand


class LLMCommand(BaseCommand):
    """Handles LLM-powered conversational AI commands.

    Provides natural language interaction using Ollama for LLM inference with
    intelligent response chunking to accommodate LoRa mesh network constraints.
    Maintains conversation context per channel/user for multi-turn conversations.

    Commands:
        !ask <question> - Ask the LLM a question
        !clear-context - Clear conversation history for current channel/user
    """

    # Plugin metadata
    name = "ask"
    keywords = ['ask', 'clear-context']
    description = "Ask questions to the bot's AI assistant (usage: !ask <question>)"
    category = "ai"
    requires_internet = True  # Ollama typically runs on network-accessible service

    # Documentation
    short_description = "Conversational AI powered by Ollama"
    usage = "ask <question> | clear-context"
    examples = ["ask What is the weather like?", "ask Tell me a joke", "clear-context"]
    parameters = [
        {"name": "question", "description": "Your question or prompt for the AI assistant"}
    ]

    def __init__(self, bot) -> None:
        """Initialize the LLM command.

        Loads all configuration values from the [LLM_Command] section:
        - enabled: Enable/disable the command
        - ollama_endpoint: URL to Ollama API server
        - ollama_model: Model name to use (e.g., 'llama2', 'mistral')
        - ollama_timeout_seconds: HTTP timeout for Ollama requests
        - context_max_exchanges: Maximum conversation history pairs to maintain
        - context_ttl_seconds: Time-to-live for context entries
        - max_chunk_length: Maximum characters per message chunk
        - max_response_parts: Maximum number of chunks before truncation
        - chunk_delay_seconds: Delay between sending chunked responses
        - system_prompt: System prompt for LLM behavior

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)

        # Load enabled flag
        self.llm_enabled = self.get_config_value(
            'LLM_Command', 'enabled', fallback=False, value_type='bool'
        )

        # Load Ollama connection settings
        self.ollama_endpoint = self.get_config_value(
            'LLM_Command', 'ollama_endpoint',
            fallback='http://localhost:11434', value_type='str'
        )
        self.ollama_model = self.get_config_value(
            'LLM_Command', 'ollama_model',
            fallback='llama2', value_type='str'
        )
        self.ollama_timeout_seconds = self.get_config_value(
            'LLM_Command', 'ollama_timeout_seconds',
            fallback=30, value_type='int'
        )

        # Load context management settings
        self.context_max_exchanges = self.get_config_value(
            'LLM_Command', 'context_max_exchanges',
            fallback=5, value_type='int'
        )
        self.context_ttl_seconds = self.get_config_value(
            'LLM_Command', 'context_ttl_seconds',
            fallback=3600, value_type='int'
        )

        # Load response chunking settings
        self.max_chunk_length = self.get_config_value(
            'LLM_Command', 'max_chunk_length',
            fallback=180, value_type='int'
        )
        self.max_response_parts = self.get_config_value(
            'LLM_Command', 'max_response_parts',
            fallback=5, value_type='int'
        )
        self.chunk_delay_seconds = self.get_config_value(
            'LLM_Command', 'chunk_delay_seconds',
            fallback=2.0, value_type='float'
        )

        # Load system prompt
        self.system_prompt = self.get_config_value(
            'LLM_Command', 'system_prompt',
            fallback=(
                'You are a helpful AI assistant on a LoRa mesh network. '
                'Keep responses brief and focused. Avoid markdown formatting.'
            ),
            value_type='str'
        )

        # Initialize OllamaClient
        self.ollama_client = OllamaClient(
            endpoint=self.ollama_endpoint,
            model=self.ollama_model,
            timeout=self.ollama_timeout_seconds,
            logger=self.logger,
        )

        # Initialize LLMContextManager
        self.context_manager = LLMContextManager(
            async_db=bot.async_db_manager,
            logger=self.logger,
        )

    def can_execute(self, message: MeshMessage, skip_channel_check: bool = False) -> bool:
        """Check if this command can be executed with the given message.

        Checks if the command is enabled in addition to standard permission checks
        (channel access, DM requirements, cooldowns).

        Args:
            message: The message triggering the command.
            skip_channel_check: If True, skip channel check.

        Returns:
            bool: True if command is enabled and all checks pass, False otherwise.
        """
        if not self.llm_enabled:
            return False
        return super().can_execute(message, skip_channel_check=skip_channel_check)

    def get_help_text(self) -> str:
        """Get help text for the LLM command.

        Returns:
            str: Usage information and available subcommands.
        """
        return (
            f"{self.description}\n"
            f"Commands:\n"
            f"  !ask <question> - Ask the AI a question\n"
            f"  !clear-context - Clear your conversation history"
        )

    async def execute(self, message: MeshMessage) -> bool:
        """Execute the LLM command.

        Handles two types of requests:
        1. !ask <question> - Query the LLM with context
        2. !clear-context - Clear conversation history

        Args:
            message: The message that triggered the command.

        Returns:
            bool: True if execution was successful, False otherwise.
        """
        # Extract the question from the message content
        question = self._extract_question(message.content)

        if not question:
            await self.send_response(
                message,
                "Usage: !ask <question> or !clear-context"
            )
            return False

        # Build context key from message (channel name or user identifier)
        context_key = self._build_context_key(message)

        try:
            # Load conversation context
            context_records = await self.context_manager.get_context(
                context_key=context_key,
                max_exchanges=self.context_max_exchanges,
            )

            # Convert context to Ollama format
            context = LLMContextManager.format_context_for_ollama(context_records)

            # Query Ollama
            try:
                response = await self.ollama_client.generate(
                    prompt=question,
                    context=context,
                    system_prompt=self.system_prompt,
                )
            except Exception as e:
                self.logger.error(f"Ollama generation error: {e}")
                await self.send_response(
                    message,
                    "Sorry, I'm having trouble connecting to the AI service. Please try again later."
                )
                return False

            # Save user question and bot response to context
            await self.context_manager.add_message(
                context_key=context_key,
                role="user",
                content=question,
            )
            await self.context_manager.add_message(
                context_key=context_key,
                role="assistant",
                content=response,
            )

            # Chunk the response for LoRa compatibility
            chunks = chunk_llm_response(
                text=response,
                max_chunk_length=self.max_chunk_length,
                max_parts=self.max_response_parts,
            )

            # Send response (single or multi-part)
            if len(chunks) == 1:
                # Single chunk - send directly
                await self.send_response(message, chunks[0])
            else:
                # Multiple chunks - send with chunked method
                await self.send_response_chunked(message, chunks)

            # TODO: US-009 - Add context pruning after response

            return True

        except Exception as e:
            self.logger.error(f"LLM command execution error: {e}")
            await self.send_response(
                message,
                "Sorry, an error occurred while processing your request."
            )
            return False

    def _extract_question(self, content: str) -> Optional[str]:
        """Extract the question from the message content.

        Strips the command keyword (ask, clear-context, etc.) and returns the remaining text.

        Args:
            content: The message content (e.g., "!ask What is the weather?")

        Returns:
            The question text, or None if no question provided.
        """
        # Strip leading/trailing whitespace
        content = content.strip()

        # Remove command prefix (! or other configured prefix)
        if content.startswith('!'):
            content = content[1:].strip()

        # Find which keyword was used and strip it
        for keyword in self.keywords:
            if content.lower().startswith(keyword.lower()):
                # Strip the keyword and any following whitespace
                question = content[len(keyword):].strip()
                return question if question else None

        return None

    def _build_context_key(self, message: MeshMessage) -> str:
        """Build a context key to identify the conversation.

        For channel messages, use the channel name.
        For DMs, use the sender's pubkey or ID.

        Args:
            message: The message containing sender/channel info

        Returns:
            A unique context key string
        """
        if message.is_dm:
            # Use pubkey if available, otherwise fall back to sender_id
            return message.sender_pubkey or message.sender_id or "unknown"
        else:
            # Use channel name for channel messages
            return message.channel or "default"
