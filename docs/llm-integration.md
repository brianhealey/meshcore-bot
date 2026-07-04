# LLM Integration

The LLM Integration feature adds conversational AI capabilities to MeshCore Bot via [Ollama](https://ollama.com/), enabling natural language interactions on LoRa mesh networks with intelligent response chunking for bandwidth constraints.

**Features:**
- Natural language question answering via `!ask` command
- Multi-turn conversation context (remembers previous exchanges)
- Intelligent response chunking for LoRa compatibility
- Per-channel and per-user conversation isolation
- Context clearing with `!clear-context`
- Automatic context pruning to prevent unbounded growth
- Configurable LLM model, timeouts, and chunking behavior
- Disabled by default (opt-in)

---

## Quick Start

### 1. Install Ollama

**Linux / macOS:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download the installer from [ollama.com/download](https://ollama.com/download)

**Verify installation:**
```bash
ollama --version
```

### 2. Pull an LLM Model

Download a model (recommended: `llama2` for general use, `mistral` for faster responses):

```bash
# Recommended: Llama 2 (4GB download)
ollama pull llama2

# Alternative: Mistral (smaller, faster)
ollama pull mistral

# Alternative: Gemma 2B (smallest, fastest)
ollama pull gemma:2b
```

### 3. Start Ollama Server

**Linux / macOS:**
```bash
# Start Ollama service (runs in background)
ollama serve
```

**Systemd service (Linux):**
```bash
sudo systemctl enable ollama
sudo systemctl start ollama
```

**Verify server is running:**
```bash
curl http://localhost:11434/api/tags
```

### 4. Configure MeshCore Bot

Edit `config.ini`:

```ini
[LLM_Command]
enabled = true
ollama_endpoint = http://localhost:11434
ollama_model = llama2
```

### 5. Restart Bot

```bash
sudo systemctl restart meshcore-bot
# OR if running manually: python3 meshcore_bot.py
```

### 6. Test

Send a message on MeshCore:
```
!ask What is the weather like today?
!ask Tell me a joke
!clear-context
```

---

## Configuration

### Basic Setup

```ini
[LLM_Command]
# Enable/disable the LLM command
enabled = true

# Ollama server endpoint (default: http://localhost:11434)
ollama_endpoint = http://localhost:11434

# Model to use (e.g., llama2, mistral, gemma:2b)
# List available models: ollama list
ollama_model = llama2

# HTTP timeout for Ollama requests in seconds (default: 30)
ollama_timeout_seconds = 30
```

### Context Management

```ini
[LLM_Command]
# Maximum conversation exchanges to remember (default: 5)
# Each exchange = 1 user message + 1 assistant response
# Higher values = more context but slower responses
context_max_exchanges = 5

# Time-to-live for context entries in seconds (default: 3600 = 1 hour)
# Entries older than this are automatically pruned
context_ttl_seconds = 3600
```

### Response Chunking

```ini
[LLM_Command]
# Maximum characters per message chunk (default: 180)
# LoRa mesh networks have strict message size limits
# Responses longer than this are split into multiple messages
max_chunk_length = 180

# Maximum number of chunks to send (default: 5)
# Responses requiring more chunks are truncated
max_response_parts = 5

# Delay between sending chunks in seconds (default: 2.0)
# Prevents flooding the mesh network
chunk_delay_seconds = 2.0
```

### System Prompt

```ini
[LLM_Command]
# System prompt to guide LLM behavior (default shown below)
# Customize this to change the assistant's personality or focus
system_prompt = You are a helpful AI assistant on a LoRa mesh network. Keep responses brief and focused. Avoid markdown formatting.
```

### Channel Restrictions (Optional)

```ini
[LLM_Command]
# Limit LLM command to specific channels (comma-separated)
# If not set, works in all monitored channels
allowed_channels = general,tech-support

# Keyword aliases (additional trigger words)
# Default keywords: ask, clear-context
aliases = query,question
```

---

## Usage

### Ask Questions

**Basic usage:**
```
!ask What is the capital of France?
```

**Multi-turn conversation:**
```
User: !ask What is the capital of France?
Bot:  The capital of France is Paris.

User: !ask What is its population?
Bot:  The population of Paris is approximately 2.2 million people within the city limits, and over 12 million in the metropolitan area.
```

The bot remembers previous exchanges in the conversation and maintains context per channel or per user (in DMs).

### Clear Context

Clear conversation history for the current channel or user:

```
!clear-context
```

**Response:** `Conversation context cleared.`

Use this when:
- Starting a new topic unrelated to previous conversation
- Context has become confused or unhelpful
- You want to reset the assistant's memory

### Response Chunking

Long responses are automatically split into multiple messages:

```
User: !ask Tell me about the history of LoRa technology
Bot:  [1/3] LoRa (Long Range) is a wireless modulation technique derived from Chirp Spread Spectrum (CSS) technology. It was developed by Cycleo, a French company...
Bot:  [2/3] The technology was acquired by Semtech in 2012. LoRa enables long-range transmissions with low power consumption, making it ideal for IoT applications...
Bot:  [3/3] LoRaWAN, the network protocol built on LoRa, was standardized by the LoRa Alliance in 2015 and is now used worldwide for low-power wide-area networks.
```

Chunk indicators `[1/3]`, `[2/3]`, `[3/3]` show progress through multi-part responses.

---

## Advanced Configuration

### Using Remote Ollama Server

If Ollama is running on a different machine:

```ini
[LLM_Command]
ollama_endpoint = http://192.168.1.100:11434
```

**Note:** Ensure the Ollama server is configured to accept remote connections:
```bash
# Set OLLAMA_HOST environment variable
export OLLAMA_HOST=0.0.0.0:11434
ollama serve
```

### Model Selection

Choose models based on your hardware and use case:

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `gemma:2b` | 1.4GB | Fastest | Good | Quick responses, limited hardware |
| `mistral` | 4.1GB | Fast | Better | Balanced performance |
| `llama2` | 3.8GB | Medium | Good | General purpose |
| `llama2:13b` | 7.4GB | Slower | Best | High-quality responses |
| `codellama` | 3.8GB | Medium | Good | Code-related questions |

List installed models:
```bash
ollama list
```

Pull a new model:
```bash
ollama pull <model-name>
```

### Custom System Prompts

Tailor the assistant's behavior for specific use cases:

**Technical support:**
```ini
system_prompt = You are a technical support assistant for LoRa mesh networks. Provide concise, actionable troubleshooting steps. Assume users have basic technical knowledge.
```

**Emergency communications:**
```ini
system_prompt = You are an emergency communications assistant. Provide clear, brief, critical information only. Prioritize life safety. Avoid unnecessary details.
```

**Weather-focused:**
```ini
system_prompt = You are a weather and environmental conditions assistant on a mesh network. Keep responses brief and include actionable advice when relevant.
```

### Context Isolation

Conversations are isolated by:
- **Channel messages:** Context key = channel name (e.g., "general", "emergency")
- **Direct messages:** Context key = sender's public key or ID

This means:
- Users in different channels have separate conversations
- Each user's DM conversation is private and isolated
- Switching channels starts a new conversation thread

---

## FAQ

### How do I check if Ollama is running?

```bash
curl http://localhost:11434/api/tags
```

Expected response: JSON list of installed models.

If you get "Connection refused", start Ollama:
```bash
ollama serve
```

### Why are responses slow?

**Possible causes:**
- **Large model:** Smaller models (gemma:2b, mistral) are faster than larger ones (llama2:13b)
- **Limited hardware:** LLMs require significant CPU/GPU. Check system resources.
- **Network latency:** If using remote Ollama server, check network connection.
- **Long context:** Reduce `context_max_exchanges` to speed up responses.

**Solutions:**
```ini
# Use smaller model
ollama_model = gemma:2b

# Reduce context memory
context_max_exchanges = 3

# Increase timeout if needed
ollama_timeout_seconds = 60
```

### Why am I getting "trouble connecting to the AI service"?

**Troubleshooting steps:**
1. Verify Ollama is running: `curl http://localhost:11434/api/tags`
2. Check endpoint configuration matches Ollama server address
3. Ensure firewall allows connection to Ollama port (default: 11434)
4. Check bot logs: `sudo journalctl -u meshcore-bot -f`
5. Test Ollama directly:
   ```bash
   curl http://localhost:11434/api/generate -d '{
     "model": "llama2",
     "prompt": "Hello"
   }'
   ```

### How do I update my model?

```bash
# Pull latest version of current model
ollama pull llama2

# Switch to a different model
ollama pull mistral

# Update config.ini
[LLM_Command]
ollama_model = mistral

# Restart bot
sudo systemctl restart meshcore-bot
```

### Can I use multiple models?

Currently, only one model can be configured per bot instance. To use multiple models:
- Run multiple bot instances with different configs
- OR change the config and restart the bot when you want to switch models

### How much bandwidth does this use?

**Typical usage:**
- Question: ~50 bytes
- Short response: ~200 bytes (1 chunk)
- Long response: ~900 bytes (5 chunks max)

Responses are automatically chunked to fit LoRa constraints (default: 180 characters per chunk). Very long responses are truncated after `max_response_parts` chunks.

### Why was my response truncated?

Responses exceeding `max_response_parts` chunks (default: 5) are automatically truncated with a `...(truncated)` suffix. This prevents flooding the mesh network with excessively long responses.

**Solutions:**
- Ask more specific questions to get shorter responses
- Increase `max_response_parts` (not recommended for LoRa networks)
- Use `!clear-context` and rephrase the question

### Can I disable LLM for specific channels?

Yes, use `allowed_channels` to whitelist specific channels:

```ini
[LLM_Command]
allowed_channels = general,tech-support
```

LLM commands will only work in the specified channels. DMs are controlled separately via `[Channels]` → `respond_to_dms`.

### How secure is my conversation data?

- **Conversation context:** Stored in local SQLite database (`meshcore_bot.db`)
- **Privacy:** Contexts are isolated per channel/user
- **Retention:** Automatically pruned based on `context_ttl_seconds` (default: 1 hour)
- **Ollama:** Runs locally - no data sent to external APIs

To clear all LLM context data:
```bash
sqlite3 meshcore_bot.db "DELETE FROM llm_conversation_context;"
```

### Does this work with OpenAI/Anthropic/other APIs?

No, this integration is designed specifically for Ollama. Ollama provides:
- Local inference (privacy, no API costs)
- Offline operation
- Model flexibility
- Simple HTTP API

For other LLM providers, you would need a custom plugin implementing their API.

---

## Troubleshooting

### Bot doesn't respond to !ask

**Check:**
1. LLM command is enabled: `[LLM_Command]` → `enabled = true`
2. Channel is monitored: `[Channels]` → `monitor_channels` includes the channel
3. Ollama is running: `curl http://localhost:11434/api/tags`
4. Model is installed: `ollama list`
5. Check bot logs: `sudo journalctl -u meshcore-bot -f`

### Responses are gibberish or nonsensical

**Causes:**
- Context has become confused (multiple unrelated topics)
- Model hallucination (LLMs sometimes generate incorrect information)

**Solutions:**
```
!clear-context
```

Then ask a new, clear, specific question.

### Timeout errors

Increase timeout if model is slow:
```ini
[LLM_Command]
ollama_timeout_seconds = 60
```

Or use a faster model:
```bash
ollama pull gemma:2b
```

### High memory usage

LLMs require significant RAM. Smaller models use less memory:
- `gemma:2b`: ~1.5GB RAM
- `mistral`: ~4GB RAM
- `llama2:13b`: ~8GB RAM

Check available memory:
```bash
free -h
```

If memory is limited, use `gemma:2b` or reduce `context_max_exchanges`.

---

## Integration Details

### Database Schema

LLM conversation context is stored in the `llm_conversation_context` table:

```sql
CREATE TABLE llm_conversation_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_key TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_llm_context_key_timestamp ON llm_conversation_context(context_key, timestamp DESC);
```

### Context Pruning

Automatic context pruning occurs after each LLM response:
1. Delete entries older than `context_ttl_seconds`
2. Keep only the most recent `context_max_exchanges * 2` messages per context key

Pruning errors are logged but do not fail the command execution.

### Architecture

```
User → !ask question
  ↓
LLMCommand.execute()
  ↓
LLMContextManager.get_context() → Load recent conversation history
  ↓
OllamaClient.generate() → Query Ollama with context + system prompt
  ↓
chunk_llm_response() → Split long response into LoRa-compatible chunks
  ↓
send_response() or send_response_chunked() → Deliver to user
  ↓
LLMContextManager.add_message() → Save user question and bot response
  ↓
LLMContextManager.prune_context() → Remove old entries
```

### API Reference

See source code documentation:
- `modules/commands/llm_command.py` — LLMCommand class
- `modules/ollama_client.py` — OllamaClient HTTP wrapper
- `modules/llm_context_manager.py` — Conversation context CRUD
- `modules/utils.py` — chunk_llm_response() utility

---

## Additional Resources

- **Ollama Documentation:** https://ollama.com/docs
- **Model Library:** https://ollama.com/library
- **MeshCore Bot Docs:** https://github.com/meshnz/meshcore-bot/tree/main/docs
- **LoRa Technology:** https://lora-alliance.org/

---

## License

This feature is part of MeshCore Bot and follows the same license terms. Ollama is a separate project with its own license (MIT).
