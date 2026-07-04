# Product Requirements Document: LLM Integration for MeshCore Bot

## Executive Summary

This PRD outlines the integration of Large Language Model (LLM) capabilities into the MeshCore Bot using Ollama as the backend inference engine. The integration will provide conversational AI capabilities while respecting the inherent constraints of LoRa mesh networking (limited message size, potential latency, bandwidth constraints).

## Document Information

- **Version**: 1.0
- **Date**: 2026-07-04
- **Author**: Engineering Team
- **Status**: Draft

---

## 1. Project Overview

### 1.1 Background

MeshCore Bot currently supports 40+ commands providing weather, alerts, mesh utilities, and entertainment features. However, it lacks conversational AI capabilities that could enhance user interactions and provide more flexible, natural language responses to mesh users.

### 1.2 Goals

1. **Primary Goal**: Add LLM-powered conversational capabilities to the MeshCore Bot
2. **Secondary Goals**:
   - Maintain bot responsiveness despite mesh network constraints
   - Provide both command-based and channel-based LLM interaction modes
   - Implement intelligent response chunking for long-form answers
   - Ensure graceful degradation when LLM service is unavailable

### 1.3 Non-Goals

- Real-time streaming of LLM responses (incompatible with LoRa mesh)
- Multi-modal AI (images, audio) due to bandwidth constraints
- Fine-tuning or training custom models
- Providing LLM inference locally on bot hardware

---

## 2. Technical Context

### 2.1 MeshCore Network Constraints

**Message Size Limitations**:
- **Base text message max**: ~237 bytes (firmware-imposed)
- **Regional flood scope overhead**: 10 bytes (reduces effective max to ~227 bytes)
- **Webhook service default**: 200 character limit
- **Practical target**: ~180-200 characters per message chunk for safety margins

**Network Characteristics**:
- **Transmission rate**: Limited by LoRa bandwidth (typical: 0.3-5.5 kbps)
- **Latency**: Variable, multi-hop routing can add seconds to minutes
- **Reliability**: Best-effort delivery, no guaranteed ACKs for all message types
- **Airtime limitations**: Regulatory duty cycle restrictions (typically 1% in EU, 10% in US)

### 2.2 Bot Architecture Review

**Existing Infrastructure**:
- **Plugin Architecture**: Commands inherit from `BaseCommand` and implement `async def execute()`
- **Message Chunking**: Existing `send_channel_messages_chunked()` handles multi-part messages
- **Rate Limiting**: Multiple layers (global, per-user, per-channel, bot transmission)
- **Database**: SQLite with async support (`AsyncDBManager`)
- **Config System**: INI-based with section-based plugin configuration
- **Web Viewer**: Flask + SocketIO dashboard for monitoring

**Relevant Existing Commands**:
- `joke_command.py`: External API integration pattern (aiohttp)
- `webhook_service.py`: HTTP server pattern (aiohttp web)
- `help_command.py`: Context-aware responses based on message content

---

## 3. Requirements

### 3.1 Functional Requirements

#### FR-1: Command-Based LLM Interaction (`!ask` command)

**Description**: Users can trigger LLM responses via `!ask <question>` command

**Acceptance Criteria**:
- [x] Command accepts format: `!ask <question>` or `!ask <question>`
- [x] Question is sent to Ollama API for inference
- [x] Response is chunked if exceeds ~180 characters
- [x] Multi-part responses are rate-limited (1-2 second spacing between chunks)
- [x] Command respects existing bot rate limits (global, per-user, per-channel)
- [x] Command works in both channels and DMs

**Example Usage**:
```
User: !ask What is a LoRa mesh network?
Bot (chunk 1): A LoRa mesh network uses low-power, long-range radio to create a decentralized network where devices relay messages peer-to-peer...
Bot (chunk 2): ...instead of relying on central infrastructure. Each node forwards packets, extending coverage beyond single-hop range.
```

#### FR-2: Dedicated LLM Channel

**Description**: A specific channel (e.g., `#ai-chat`) operates in conversational mode where all messages are sent to the LLM

**Acceptance Criteria**:
- [x] Channel name is configurable via `[LLM_Command]` section: `ai_channel = ai-chat`
- [x] All non-bot messages in this channel are treated as LLM prompts
- [x] Bot maintains conversation history per channel (last N exchanges)
- [x] Conversation context is time-limited (configurable, default 10 minutes)
- [x] Channel can be enabled/disabled independently of `!ask` command
- [x] Rate limiting prevents spam (configurable delay between responses)

**Example Usage**:
```
[In #ai-chat channel]
Alice: What's the weather like in Seattle?
Bot: I don't have real-time weather access, but you can use the !wx command...

Bob: Tell me about mesh networking
Bot: Mesh networks are decentralized topologies where each node can relay data...
```

#### FR-3: Context Management

**Description**: LLM maintains limited conversation context to provide coherent responses

**Acceptance Criteria**:
- [x] Context stores last N message pairs (user question + bot response)
- [x] Context is per-channel (channel messages) or per-user (DMs)
- [x] Context has configurable max size (default: 5 exchanges, ~10 messages total)
- [x] Context has configurable TTL (default: 600 seconds / 10 minutes)
- [x] Old context is automatically pruned based on timestamp and count
- [x] Context is stored in SQLite for persistence across bot restarts
- [x] Manual context clear command: `!clear-context` (user can reset their history)

**Database Schema** (new table: `llm_conversation_context`):
```sql
CREATE TABLE llm_conversation_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_key TEXT NOT NULL,        -- channel name or user pubkey/ID
    role TEXT NOT NULL,                 -- 'user' or 'assistant'
    content TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_context_key ON llm_conversation_context(context_key, timestamp);
```

#### FR-4: Response Chunking and Formatting

**Description**: LLM responses are intelligently chunked to fit LoRa message constraints

**Acceptance Criteria**:
- [x] Responses exceeding ~180 characters are split at sentence boundaries
- [x] If sentence splitting isn't possible, split at word boundaries
- [x] Each chunk is prefixed with indicator (e.g., `[1/3]`) if multi-part
- [x] Chunks are sent sequentially with rate-limit spacing (1-2 seconds)
- [x] If chunking would create >5 parts, response is summarized or truncated
- [x] User is notified if response was truncated: `...(truncated, too long)`

**Chunking Algorithm**:
```python
def chunk_llm_response(text: str, max_chunk: int = 180, max_parts: int = 5) -> list[str]:
    """
    Split response intelligently:
    1. Try sentence boundaries (. ! ?)
    2. Fallback to word boundaries
    3. If too many chunks, truncate and warn
    """
```

#### FR-5: Ollama Integration

**Description**: Bot communicates with remote Ollama instance via HTTP API

**Acceptance Criteria**:
- [x] Ollama connection uses configurable endpoint (default: `http://localhost:11434`)
- [x] Model selection is configurable (default: `llama3.2:3b-instruct-q4_K_M`)
- [x] Request timeout is configurable (default: 30 seconds)
- [x] Connection failures are handled gracefully (error message to user)
- [x] Health check endpoint verifies Ollama availability on bot startup
- [x] HTTP client uses aiohttp for async communication
- [x] Optional API key/auth header support for secured Ollama instances

**Configuration** (`config.ini.example`):
```ini
[LLM_Command]
enabled = true
ollama_endpoint = http://localhost:11434
ollama_model = llama3.2:3b-instruct-q4_K_M
ollama_timeout_seconds = 30
ollama_api_key =                    # Optional Bearer token

# Command-based interaction
ask_command_enabled = true
ask_aliases = ask,ai,llm

# Dedicated AI channel
ai_channel_enabled = true
ai_channel = ai-chat

# Context settings
context_max_exchanges = 5           # Max user-bot exchange pairs to remember
context_ttl_seconds = 600           # 10 minutes
context_max_tokens = 1000           # Approximate token limit for context window

# Response formatting
max_chunk_length = 180              # Characters per chunk
max_response_parts = 5              # Max chunks before truncation
chunk_delay_seconds = 1.5           # Delay between sending chunks

# System prompt (optional)
system_prompt = You are a helpful assistant for a LoRa mesh network. Keep responses concise (under 500 chars when possible). Be friendly and informative.
```

#### FR-6: Error Handling and Fallbacks

**Description**: Robust error handling ensures bot remains functional when LLM service fails

**Acceptance Criteria**:
- [x] Connection timeout: "LLM service unavailable, please try later"
- [x] Model not found: "Configured LLM model not available"
- [x] Rate limit from Ollama: "LLM service busy, try again in a moment"
- [x] Malformed response: "Received invalid response from LLM"
- [x] Context DB error: Log error, continue without context
- [x] All errors are logged with appropriate severity

### 3.2 Non-Functional Requirements

#### NFR-1: Performance

- LLM inference completes within 30 seconds (configurable timeout)
- Context retrieval from DB completes in <100ms
- Chunked responses begin transmitting within 2 seconds of inference completion
- Memory footprint increase: <50MB per active conversation context

#### NFR-2: Scalability

- Support up to 50 active conversation contexts simultaneously
- Context pruning prevents unbounded database growth
- LRU eviction for in-memory context cache (if implemented)

#### NFR-3: Reliability

- Graceful degradation when Ollama is unreachable
- No bot crashes due to LLM errors
- User notification on all error conditions

#### NFR-4: Security

- No user input is executed as code (prompt injection prevention)
- Ollama API key (if used) is not logged or exposed
- PII in context is handled according to existing bot privacy practices
- Context data is not shared between users/channels

#### NFR-5: Maintainability

- LLM command follows existing plugin architecture
- Code is type-hinted and passes mypy strict checks
- Configuration follows existing INI patterns
- Comprehensive docstrings and inline comments

---

## 4. Implementation Plan

### 4.1 High-Level Architecture

```
┌─────────────────┐
│   Mesh User     │
└────────┬────────┘
         │ "!ask What is LoRa?"
         ▼
┌─────────────────────────────────────────────┐
│         MeshCore Bot                        │
│  ┌──────────────────────────────────────┐  │
│  │  CommandManager.check_keywords()     │  │
│  │    ├─ matches "!ask"                 │  │
│  │    └─ routes to LLMCommand.execute() │  │
│  └──────────────┬───────────────────────┘  │
│                 ▼                            │
│  ┌──────────────────────────────────────┐  │
│  │  LLMCommand                          │  │
│  │   ├─ load_context_from_db()          │  │
│  │   ├─ query_ollama()                  │  │
│  │   ├─ chunk_response()                │  │
│  │   ├─ save_context_to_db()            │  │
│  │   └─ send_response_chunked()         │  │
│  └──────────────┬───────────────────────┘  │
│                 │                            │
└─────────────────┼────────────────────────────┘
                  │ HTTP POST
                  ▼
         ┌─────────────────┐
         │  Ollama Server  │
         │  (Remote/Local) │
         │  - /api/generate│
         │  - /api/tags    │
         └─────────────────┘
```

### 4.2 Component Breakdown

#### Component 1: `llm_command.py`

**Purpose**: Main command plugin for LLM interactions

**Key Methods**:
```python
class LLMCommand(BaseCommand):
    name = "ask"
    keywords = ['ask', 'ai', 'llm']  # Configurable via aliases
    requires_internet = True

    async def execute(self, message: MeshMessage) -> bool:
        """Main entry point for !ask command"""

    async def query_ollama(self, prompt: str, context: list = None) -> str:
        """Send request to Ollama API"""

    async def load_context(self, context_key: str) -> list:
        """Load recent conversation history from DB"""

    async def save_context(self, context_key: str, role: str, content: str):
        """Save message to conversation history"""

    def chunk_response(self, text: str) -> list[str]:
        """Intelligently chunk long responses"""

    async def prune_old_context(self, context_key: str):
        """Remove expired context entries"""
```

#### Component 2: `llm_channel_service.py` (Service Plugin)

**Purpose**: Background service for dedicated AI channel monitoring

**Key Methods**:
```python
class LLMChannelService(BaseServicePlugin):
    config_section = 'LLM_Channel'

    async def start(self):
        """Register message listener for AI channel"""

    async def stop(self):
        """Unregister listener"""

    async def handle_channel_message(self, message: MeshMessage):
        """Process all messages in AI channel as LLM prompts"""
```

#### Component 3: `llm_context_manager.py`

**Purpose**: Manage conversation context storage and retrieval

**Key Methods**:
```python
class LLMContextManager:
    def __init__(self, db_manager: AsyncDBManager, config: ConfigParser):
        """Initialize with DB connection"""

    async def get_context(self, context_key: str, max_exchanges: int) -> list[dict]:
        """Retrieve recent context for key"""

    async def add_message(self, context_key: str, role: str, content: str):
        """Append message to context"""

    async def prune_context(self, context_key: str, max_exchanges: int, ttl_seconds: int):
        """Remove old/excess context"""

    async def clear_context(self, context_key: str):
        """Clear all context for key (for !clear-context command)"""

    def format_context_for_ollama(self, context: list[dict]) -> list[dict]:
        """Convert DB records to Ollama message format"""
```

#### Component 4: `ollama_client.py`

**Purpose**: HTTP client wrapper for Ollama API

**Key Methods**:
```python
class OllamaClient:
    def __init__(self, endpoint: str, model: str, api_key: str = None):
        """Initialize HTTP client"""

    async def generate(
        self,
        prompt: str,
        context: list[dict] = None,
        system_prompt: str = None,
        timeout: int = 30
    ) -> str:
        """Call /api/generate endpoint"""

    async def health_check(self) -> bool:
        """Verify Ollama is reachable"""

    async def list_models(self) -> list[str]:
        """Get available models from /api/tags"""
```

### 4.3 Database Migration

**Migration ID**: `_m0042_llm_conversation_context`

**SQL**:
```sql
CREATE TABLE IF NOT EXISTS llm_conversation_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_key TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_llm_context_key
    ON llm_conversation_context(context_key, timestamp DESC);
```

**Append to `modules/db_migrations.py`**:
```python
def _m0042_llm_conversation_context(cursor):
    """Add table for LLM conversation context storage."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_conversation_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context_key TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_llm_context_key
            ON llm_conversation_context(context_key, timestamp DESC)
    ''')

# Add to MIGRATIONS list:
(42, "Add LLM conversation context table", _m0042_llm_conversation_context),
```

### 4.4 Configuration Updates

**File**: `config.ini.example`

Add new section:
```ini
[LLM_Command]
# Enable LLM integration
enabled = true

# Ollama server configuration
ollama_endpoint = http://localhost:11434
ollama_model = llama3.2:3b-instruct-q4_K_M
ollama_timeout_seconds = 30
ollama_api_key =

# Command-based !ask interaction
ask_command_enabled = true
aliases = ask,ai

# Dedicated AI channel (experimental)
ai_channel_enabled = false
ai_channel = ai-chat

# Context management
context_max_exchanges = 5
context_ttl_seconds = 600
context_max_tokens = 1000

# Response formatting
max_chunk_length = 180
max_response_parts = 5
chunk_delay_seconds = 1.5
truncation_suffix = ... (truncated)

# System prompt (guides LLM behavior)
system_prompt = You are a helpful assistant for a LoRa mesh network. Keep responses very concise (under 500 characters when possible) due to bandwidth constraints. Be friendly and informative. If asked about mesh or radio topics, be accurate.

# Rate limiting (inherits bot-level limits, these are additional)
per_user_cooldown_seconds = 10
max_requests_per_hour = 20
```

---

## 5. Implementation Phases

### Phase 1: Foundation (Week 1)

**Deliverables**:
- [x] Database migration for `llm_conversation_context` table
- [x] `ollama_client.py` module with basic HTTP client
- [x] Configuration section in `config.ini.example`
- [x] Unit tests for Ollama client (mocked API responses)

**Testing**:
- Verify Ollama client can connect to local Ollama instance
- Confirm configuration loads correctly
- Database migration runs successfully

### Phase 2: Command Implementation (Week 2)

**Deliverables**:
- [x] `llm_command.py` with basic `!ask` functionality
- [x] `llm_context_manager.py` for context CRUD operations
- [x] Response chunking algorithm
- [x] Integration with existing `send_channel_messages_chunked()`

**Testing**:
- End-to-end test: `!ask` command receives response from Ollama
- Chunking correctly splits long responses
- Context is saved and retrieved from DB

### Phase 3: Context and Polish (Week 3)

**Deliverables**:
- [x] Context management (load, save, prune)
- [x] `!clear-context` command
- [x] Error handling and graceful degradation
- [x] User-facing error messages
- [x] Logging and monitoring hooks

**Testing**:
- Multi-turn conversations maintain context
- Old context is pruned correctly
- Ollama downtime doesn't crash bot

### Phase 4: AI Channel Service (Week 4 - Optional)

**Deliverables**:
- [x] `llm_channel_service.py` service plugin
- [x] Channel message listener registration
- [x] Per-channel context management

**Testing**:
- All messages in `#ai-chat` get LLM responses
- Context is isolated per channel
- Rate limiting prevents spam

---

## 6. Testing Strategy

### 6.1 Unit Tests

**Test Files**:
- `tests/test_ollama_client.py` - HTTP client with mocked responses
- `tests/test_llm_context_manager.py` - DB operations with `tmp_path` fixture
- `tests/test_llm_command.py` - Command logic with mocked Ollama

**Coverage Target**: >80% for new modules

### 6.2 Integration Tests

**Scenarios**:
1. `!ask` command end-to-end with live Ollama instance
2. Multi-part response chunking and delivery
3. Context persistence across bot restarts
4. Concurrent requests from multiple users
5. AI channel service with multiple participants

### 6.3 Manual Testing

**Test Plan**:
- Deploy to test mesh network with real LoRa devices
- Verify message chunking doesn't exceed MTU
- Test latency and response times over multi-hop paths
- Validate airtime consumption is acceptable
- Confirm rate limiting prevents abuse

---

## 7. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Ollama inference too slow** | Users experience long delays | Medium | Implement configurable timeout (default 30s), use smaller models (llama3.2:3b), provide "thinking..." indicator |
| **Responses too long for mesh** | Excessive chunking degrades UX | High | Default system prompt emphasizes brevity, hard limit on response parts (5 max), truncation with warning |
| **Context DB grows unbounded** | Disk space exhaustion | Low | Automated pruning based on TTL and count, periodic cleanup task |
| **Prompt injection attacks** | Users manipulate bot behavior | Medium | No code execution, sanitize inputs, validate Ollama responses, rate limiting |
| **Ollama server downtime** | Feature unavailable | Medium | Health checks, graceful error messages, fallback to "service unavailable" |
| **Airtime saturation** | Bot monopolizes mesh bandwidth | High | Per-user cooldowns (10s default), hourly request limits (20/hr), chunk delays, admin override |

---

## 8. Success Metrics

**Quantitative Metrics**:
- LLM command usage: Target 10+ unique users/day after 2 weeks
- Average response time: <15 seconds p50, <30 seconds p95
- Error rate: <5% of requests result in error
- Context retention: 80% of multi-turn conversations span 2+ exchanges

**Qualitative Metrics**:
- User feedback survey: "LLM feature is helpful" - target 70% agree/strongly agree
- Admin feedback: "LLM doesn't cause mesh congestion" - target 100% agree

---

## 9. Future Enhancements

**Post-MVP Features** (not in initial release):

1. **Model Selection**: Allow users to choose model via `!ask-[model] question`
   - Example: `!ask-small What is LoRa?` uses `llama3.2:1b`

2. **Multi-turn Summaries**: Periodically compress old context to fit more history
   - Use LLM to summarize previous exchanges into shorter context

3. **Tool Use**: LLM can trigger other bot commands
   - Example: LLM responds "Let me check weather: !wx Seattle"

4. **Embedding Search**: Semantic search over mesh message history
   - Requires vector DB (ChromaDB, Qdrant) for context retrieval

5. **Voice Transcription**: Accept audio messages via webhook, transcribe, send to LLM
   - Requires Whisper model and audio encoding support

6. **Admin Commands**: `!llm-stats`, `!llm-health`, `!llm-reload-config`

---

## 10. Documentation Requirements

**User Documentation** (`docs/llm-integration.md`):
- Installation: How to set up Ollama
- Configuration: All `[LLM_Command]` options explained
- Usage examples: `!ask`, `!clear-context`, AI channel
- FAQ: Common issues and troubleshooting

**Developer Documentation**:
- Architecture diagrams (see section 4.1)
- API contract for Ollama client
- Context manager interface
- Adding new LLM providers (future: Anthropic, OpenAI)

**Command Reference Website**:
- Add LLM commands to `generate_website.py`
- Usage syntax, parameters, examples

---

## 11. Open Questions

1. **Q**: Should AI channel be opt-in per user or channel-wide?
   - **A**: Channel-wide (simpler), but add per-user mute command later

2. **Q**: What happens if two users ask questions simultaneously in AI channel?
   - **A**: FIFO queue, second user waits for first response to finish

3. **Q**: Should context be encrypted at rest?
   - **A**: No for MVP, revisit if PII concerns arise

4. **Q**: What's the recommended Ollama model for best speed/quality balance?
   - **A**: `llama3.2:3b-instruct-q4_K_M` (3B params, 4-bit quantized, ~2GB RAM)

---

## 12. Appendices

### Appendix A: Ollama API Reference

**Generate Endpoint**: `POST /api/generate`

```json
Request:
{
  "model": "llama3.2:3b-instruct-q4_K_M",
  "prompt": "What is a LoRa mesh network?",
  "system": "You are a helpful assistant...",
  "stream": false,
  "options": {
    "temperature": 0.7,
    "num_predict": 200
  }
}

Response:
{
  "model": "llama3.2:3b-instruct-q4_K_M",
  "created_at": "2026-07-04T12:00:00.000Z",
  "response": "A LoRa mesh network is a decentralized wireless network...",
  "done": true
}
```

**Chat Endpoint**: `POST /api/chat` (alternative with native multi-turn support)

```json
Request:
{
  "model": "llama3.2:3b-instruct-q4_K_M",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant..."},
    {"role": "user", "content": "What is LoRa?"},
    {"role": "assistant", "content": "LoRa is a long-range..."},
    {"role": "user", "content": "How far can it transmit?"}
  ],
  "stream": false
}

Response:
{
  "model": "llama3.2:3b-instruct-q4_K_M",
  "created_at": "2026-07-04T12:00:00.000Z",
  "message": {
    "role": "assistant",
    "content": "LoRa can transmit up to 10+ km in rural areas..."
  },
  "done": true
}
```

### Appendix B: Example User Flows

**Flow 1: Simple Question**
```
User: !ask What is the capital of France?
Bot: The capital of France is Paris.
```

**Flow 2: Long Response (Chunked)**
```
User: !ask Explain how LoRa mesh networks work
Bot [1/3]: LoRa mesh networks use long-range radio (LoRa modulation) to create peer-to-peer networks without infrastructure. Each device (node) can...
Bot [2/3]: ...relay messages from other nodes, extending coverage beyond single-hop range. Nodes automatically route packets through the mesh...
Bot [3/3]: ...finding optimal paths based on signal strength and hop count. This creates resilient, decentralized networks ideal for IoT.
```

**Flow 3: Multi-turn Conversation**
```
User: !ask What is Python?
Bot: Python is a high-level programming language known for readability and versatility.

User: !ask What is it used for?
Bot: Python is used for web development, data science, automation, AI/ML, and scripting tasks.

User: !clear-context
Bot: Conversation context cleared.
```

**Flow 4: AI Channel**
```
[In #ai-chat]
Alice: What's the best LoRa frequency for North America?
Bot: In North America (USA/Canada), the ISM band 902-928 MHz is typically used for LoRa.

Bob: How many hops can a LoRa mesh support?
Bot: Most LoRa mesh implementations support 3-7 hops, though more hops increase latency and reduce reliability.
```

### Appendix C: Recommended Ollama Models

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `llama3.2:1b-instruct-q4_K_M` | ~1GB RAM | Very Fast | Good | Low latency, simple Q&A |
| `llama3.2:3b-instruct-q4_K_M` | ~2GB RAM | Fast | Better | **Recommended default** |
| `phi3:3.8b-mini-4k-instruct-q4_K_M` | ~2.5GB RAM | Fast | Better | Alternative to llama3.2:3b |
| `mistral:7b-instruct-q4_K_M` | ~4GB RAM | Medium | Best | High-quality responses |
| `qwen2.5:7b-instruct-q4_K_M` | ~4GB RAM | Medium | Best | Multilingual support |

**Notes**:
- All sizes assume 4-bit quantization (`q4_K_M`)
- Speed assumes modern CPU (8+ cores) or GPU acceleration
- Smaller models (<3B params) may struggle with complex context

---

## Approval Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Product Owner | | | |
| Tech Lead | | | |
| Security Lead | | | |
| QA Lead | | | |
