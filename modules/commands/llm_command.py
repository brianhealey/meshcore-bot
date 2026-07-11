#!/usr/bin/env python3
"""
LLM command for the MeshCore Bot
Provides conversational AI capabilities via Ollama with LoRa-optimized response chunking
"""

from typing import Any, Optional

from ..llm_context_manager import LLMContextManager
from ..models import MeshMessage
from ..ollama_client import OllamaClient
from ..tool_executor import ToolExecutor
from ..tool_registry import ToolRegistry
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

        # Load user mention setting
        self.include_user_mention = self.get_config_value(
            'LLM_Command', 'include_user_mention',
            fallback=True, value_type='bool'
        )

        # Load command context tracking setting
        self.track_all_commands = self.get_config_value(
            'LLM_Command', 'track_all_commands',
            fallback=True, value_type='bool'
        )

        # Load tool calling settings
        self.enable_tools = self.get_config_value(
            'LLM_Command', 'enable_tools',
            fallback=False, value_type='bool'
        )
        self.max_tools_per_query = self.get_config_value(
            'LLM_Command', 'max_tools_per_query',
            fallback=3, value_type='int'
        )
        self.tool_timeout = self.get_config_value(
            'LLM_Command', 'tool_timeout',
            fallback=10, value_type='int'
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

        # Initialize ToolRegistry and ToolExecutor lazily (on first use)
        # to avoid accessing bot.command_manager before it's fully initialized
        self.tool_registry: ToolRegistry | None = None
        self.tool_executor: ToolExecutor | None = None
        self._tools_initialized = False

    def _initialize_tools(self) -> None:
        """Initialize ToolRegistry and ToolExecutor lazily.

        This is called on first use to avoid accessing bot.command_manager
        before it's fully initialized during bot startup.
        """
        if self._tools_initialized or not self.enable_tools:
            return

        try:
            self.tool_registry = ToolRegistry(
                bot=self.bot,
                command_manager=self.bot.command_manager,
            )
            self.tool_executor = ToolExecutor(
                bot=self.bot,
                command_manager=self.bot.command_manager,
                tool_registry=self.tool_registry,
            )
            self._tools_initialized = True
            self.logger.info("Tool calling initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize tool calling: {e}")
            self.enable_tools = False

    async def cleanup(self) -> None:
        """Clean up resources (close HTTP session).

        This method should be called when the command is being unloaded or the bot is shutting down.
        """
        try:
            await self.ollama_client.close()
        except Exception as e:
            self.logger.error(f"Error closing OllamaClient session: {e}")

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
        # Initialize tools lazily on first use (if enabled)
        self._initialize_tools()

        # Build context key from message (channel name or user identifier)
        context_key = self._build_context_key(message)

        # Check if this is a clear-context request
        if self._is_clear_context_request(message.content):
            try:
                success = await self.context_manager.clear_context(context_key)
                if success:
                    response = self._add_user_mention("Conversation context cleared.", message)
                    await self.send_response(message, response)
                    return True
                else:
                    response = self._add_user_mention(
                        "Failed to clear context. Please try again.", message
                    )
                    await self.send_response(message, response)
                    return False
            except Exception as e:
                self.logger.error(f"Error clearing context for key '{context_key}': {e}")
                response = self._add_user_mention(
                    "An error occurred while clearing context.", message
                )
                await self.send_response(message, response)
                return False

        # Extract the question from the message content
        question = self._extract_question(message.content)

        if not question:
            response = self._add_user_mention(
                "Usage: !ask <question> or !clear-context", message
            )
            await self.send_response(message, response)
            return False

        self.logger.debug(
            f"[LLM] Processing query: sender='{message.sender_id}', "
            f"channel='{message.channel}', is_dm={message.is_dm}, query='{question[:100]}...'"
        )

        try:
            # Load conversation context
            context_records = await self.context_manager.get_context(
                context_key=context_key,
                max_exchanges=self.context_max_exchanges,
            )

            # Convert context to Ollama format
            context = LLMContextManager.format_context_for_ollama(context_records)

            self.logger.debug(
                f"[LLM] Context loaded: {len(context_records)} records, "
                f"formatted to {len(context)} messages for Ollama"
            )

            # Query Ollama (with or without tool calling)
            try:
                if self.enable_tools:
                    self.logger.info(
                        f"[LLM] Using tool-enabled mode for query: '{question[:50]}...'"
                    )
                    llm_response = await self._execute_with_tools(question, context, message)
                else:
                    self.logger.info(
                        f"[LLM] Using direct LLM mode (no tools) for query: '{question[:50]}...'"
                    )
                    self.logger.debug(f"[LLM] System prompt: '{self.system_prompt[:100]}...'")
                    llm_response = await self.ollama_client.generate(
                        prompt=question,
                        context=context,
                        system_prompt=self.system_prompt,
                    )
                self.logger.debug(
                    f"[LLM] Received response: '{llm_response[:200]}...'"
                )
            except Exception as e:
                self.logger.error(f"Ollama generation error: {e}")
                error_msg = self._add_user_mention(
                    "Sorry, I'm having trouble connecting to the AI service. Please try again later.",
                    message
                )
                await self.send_response(message, error_msg)
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
                content=llm_response,
            )

            # Add user mention to response if configured
            response_with_mention = self._add_user_mention(llm_response, message)

            # Use actual max message length for the message type (accounts for username prefix)
            effective_max_length = self.get_max_message_length(message)

            # Hard truncate to maximum possible length before chunking
            # Reserve space for chunk indicators like [N/M] (8 chars per chunk)
            chunk_overhead = 8  # "[99/99] " worst case
            max_content_per_chunk = effective_max_length - chunk_overhead
            max_total_length = max_content_per_chunk * self.max_response_parts
            if len(response_with_mention) > max_total_length:
                # Truncate at sentence boundary if possible
                truncated = response_with_mention[:max_total_length]
                # Try to truncate at last sentence boundary
                for delimiter in ['. ', '! ', '? ', '\n']:
                    last_delim = truncated.rfind(delimiter)
                    if last_delim > max_total_length * 0.7:  # Keep at least 70% of content
                        truncated = truncated[:last_delim + 1]
                        break
                response_with_mention = truncated.rstrip()
            chunks = chunk_llm_response(
                text=response_with_mention,
                max_chunk_length=effective_max_length,
                max_parts=self.max_response_parts,
            )

            # Send response (single or multi-part)
            if len(chunks) == 1:
                # Single chunk - send directly
                await self.send_response(message, chunks[0])
            else:
                # Multiple chunks - send with chunked method
                await self.send_response_chunked(message, chunks)

            # Prune old context to prevent unbounded DB growth
            try:
                await self.context_manager.prune_context(
                    context_key=context_key,
                    max_exchanges=self.context_max_exchanges,
                    ttl_seconds=self.context_ttl_seconds,
                )
            except Exception as e:
                # Log pruning errors but don't fail the command
                self.logger.error(f"Context pruning error for key '{context_key}': {e}")

            return True

        except Exception as e:
            self.logger.error(f"LLM command execution error: {e}")
            error_msg = self._add_user_mention(
                "Sorry, an error occurred while processing your request.", message
            )
            await self.send_response(message, error_msg)
            return False

    async def _execute_with_tools(
        self,
        question: str,
        context: list[dict[str, str]],
        message: MeshMessage,
    ) -> str:
        """Execute LLM query with tool calling support.

        Implements the tool-calling loop:
        1. Call LLM with available tools
        2. If LLM returns tool calls, execute them
        3. Add tool results to messages and repeat
        4. Continue until LLM returns final response or max iterations reached

        Args:
            question: The user's question
            context: Previous conversation context in Ollama format
            message: The original MeshMessage (for channel/sender info)

        Returns:
            Final LLM response text

        Raises:
            Exception: If tool calling fails or LLM errors
        """
        if not self.tool_registry or not self.tool_executor:
            # Fallback to non-tool mode if tools not initialized
            return await self.ollama_client.generate(
                prompt=question,
                context=context,
                system_prompt=self.system_prompt,
            )

        # Get tool schemas filtered by query intent (keyword matching)
        # This prevents irrelevant tools from being offered to the LLM
        tool_schemas = self.tool_registry.get_tool_schemas_for_query(question)

        if not tool_schemas:
            # No tools match the query - use direct LLM response
            self.logger.info(
                "[LLM_TOOLS] No tools match query intent, falling back to direct response"
            )
            return await self.ollama_client.generate(
                prompt=question,
                context=context,
                system_prompt=self.system_prompt,
            )

        tool_names = [t.get("function", {}).get("name", "unknown") for t in tool_schemas]
        self.logger.debug(
            f"[LLM_TOOLS] Filtered tools for query ({len(tool_schemas)}): {tool_names}"
        )

        # Build messages list for chat API
        messages: list[dict[str, Any]] = []

        # Add system prompt
        self.logger.debug(f"[LLM_TOOLS] System prompt: '{self.system_prompt}'")
        messages.append({
            "role": "system",
            "content": self.system_prompt,
        })

        # Add conversation context
        messages.extend(context)

        # Add current user question
        messages.append({
            "role": "user",
            "content": question,
        })

        # Tool calling loop
        tool_calls_count = 0
        max_iterations = self.max_tools_per_query

        self.logger.info(
            f"[LLM_TOOLS] Starting tool calling loop: max_iterations={max_iterations}, "
            f"user_query='{question[:50]}...'"
        )

        for iteration in range(max_iterations + 1):
            self.logger.debug(
                f"[LLM_TOOLS] Iteration {iteration + 1}/{max_iterations + 1}: "
                f"tool_calls_so_far={tool_calls_count}"
            )

            # Call LLM with tools
            response = await self.ollama_client.chat(
                messages=messages,
                tools=tool_schemas if iteration < max_iterations else None,
            )

            # Extract message from response
            response_message = response.get("message", {})

            # Check for tool calls
            tool_calls = response_message.get("tool_calls", [])

            if not tool_calls:
                # No tool calls - return final response
                final_response = response_message.get("content", "")
                self.logger.info(
                    f"[LLM_TOOLS] LLM returned DIRECT RESPONSE (no tools called) at iteration {iteration + 1}"
                )
                self.logger.debug(
                    f"[LLM_TOOLS] Direct response content: '{final_response[:200]}...'"
                )
                return final_response

            # Execute tool calls
            tool_call_names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
            self.logger.info(
                f"[LLM_TOOLS] LLM requested TOOL CALLS ({len(tool_calls)}): {tool_call_names}"
            )

            # Add assistant message with tool calls to conversation
            messages.append(response_message)

            # Execute each tool call and collect results
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_args = tool_call.get("function", {}).get("arguments", {})

                self.logger.info(
                    f"[LLM_TOOLS] Invoking tool: '{tool_name}' with args: {tool_args}"
                )
                self.logger.debug(
                    f"[LLM_TOOLS] Tool invocation reason: LLM selected this tool based on "
                    f"user query '{question[:50]}...' and available tool schemas"
                )

                try:
                    # Execute the tool
                    tool_result = await self.tool_executor.execute_tool(
                        tool_name=tool_name,
                        arguments=tool_args,
                        original_message=message,
                        timeout=self.tool_timeout,
                    )

                    self.logger.debug(
                        f"[LLM_TOOLS] Tool '{tool_name}' result: {tool_result[:200]}..."
                    )

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                    })

                    tool_calls_count += 1

                except Exception as e:
                    error_msg = f"Error executing tool {tool_name}: {e}"
                    self.logger.error(error_msg)

                    # Add error as tool result
                    messages.append({
                        "role": "tool",
                        "content": f"Error: {error_msg}",
                    })

            # Check if we've hit the max tool calls limit
            if tool_calls_count >= self.max_tools_per_query:
                self.logger.warning(
                    f"[LLM_TOOLS] Reached max tool calls limit ({self.max_tools_per_query}). "
                    "Forcing final response from LLM."
                )
                break

        # If we exit the loop without a final response, make one last call without tools
        self.logger.info("[LLM_TOOLS] Making final LLM call without tools to get response")
        final_response_obj = await self.ollama_client.chat(
            messages=messages,
            tools=None,  # No tools for final call
        )

        final_text = final_response_obj.get("message", {}).get("content", "")
        self.logger.debug(
            f"[LLM_TOOLS] Final response after tools: '{final_text[:200]}...'"
        )
        return final_text

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

    def _is_clear_context_request(self, content: str) -> bool:
        """Check if the message is a clear-context request.

        Args:
            content: The message content

        Returns:
            bool: True if this is a clear-context request, False otherwise
        """
        # Strip leading/trailing whitespace
        content = content.strip()

        # Remove command prefix (! or other configured prefix)
        if content.startswith('!'):
            content = content[1:].strip()

        # Check if content matches 'clear-context' (case-insensitive)
        return content.lower().startswith('clear-context')

    def _add_user_mention(self, response: str, message: MeshMessage) -> str:
        """Add user mention prefix to response if configured.

        Args:
            response: The response text to potentially prefix
            message: The message containing sender info

        Returns:
            The response with user mention prefix if enabled, otherwise unchanged
        """
        # Skip mention for DMs
        if message.is_dm:
            return response

        # Skip mention if disabled in config
        if not self.include_user_mention:
            return response

        # Extract sender name
        sender_name = message.sender_id or "User"

        # Add mention prefix
        return f"@[{sender_name}] {response}"
