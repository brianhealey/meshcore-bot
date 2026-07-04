# LLM Integration Implementation Summary

## Quick Overview

This document provides a high-level summary of the LLM integration plan for MeshCore Bot. For full details, see [LLM_INTEGRATION_PRD.md](LLM_INTEGRATION_PRD.md).

---

## What We're Building

**Two LLM interaction modes**:

1. **Command-based**: `!ask <question>` - Users trigger LLM responses via explicit commands
2. **AI Channel** (optional): Dedicated channel (e.g., `#ai-chat`) where all messages go to the LLM

**Key Constraints We're Solving**:
- LoRa mesh has ~180-237 byte message limit → Intelligent response chunking
- Network latency can be high → Configurable timeouts and async processing
- Bandwidth is precious → Rate limiting and chunk delays to prevent saturation

---

## Architecture at a Glance

```
User: !ask What is LoRa?
         ↓
CommandManager → LLMCommand.execute()
         ↓
Load context from SQLite
         ↓
Query Ollama API (HTTP POST)
         ↓
Chunk response (max ~180 chars/chunk)
         ↓
Send chunks with rate-limit delays
         ↓
Save context to SQLite
```

---

## Core Components

### 1. `llm_command.py` (Main Command Plugin)
- Inherits from `BaseCommand`
- Implements `!ask`, `!ai`, `!clear-context` commands
- Handles Ollama API calls, chunking, and context management

### 2. `ollama_client.py` (HTTP Client)
- Wrapper around Ollama REST API
- Handles `/api/generate` and `/api/chat` endpoints
- Health checks and error handling

### 3. `llm_context_manager.py` (Context Storage)
- CRUD operations for conversation history
- Per-user and per-channel context isolation
- Automatic pruning based on age and size

### 4. `llm_channel_service.py` (Optional Service Plugin)
- Monitors dedicated AI channel
- Routes all channel messages to LLM
- Independent enable/disable from `!ask` command

### 5. Database Migration
- New table: `llm_conversation_context`
- Stores recent exchanges for context continuity

---

## Configuration Example

```ini
[LLM_Command]
enabled = true
ollama_endpoint = http://localhost:11434
ollama_model = llama3.2:3b-instruct-q4_K_M
ask_command_enabled = true
ai_channel_enabled = false
ai_channel = ai-chat
context_max_exchanges = 5
context_ttl_seconds = 600
max_chunk_length = 180
system_prompt = You are a helpful assistant for a LoRa mesh network. Keep responses very concise.
```

---

## Implementation Phases

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **1. Foundation** | Week 1 | DB migration, Ollama client, config |
| **2. Command** | Week 2 | `!ask` command, chunking, context CRUD |
| **3. Polish** | Week 3 | Error handling, `!clear-context`, logging |
| **4. AI Channel** | Week 4 | Service plugin, channel monitoring (optional) |

---

## Key Design Decisions

### Why Ollama?
- **Open-source**: Self-hostable, no vendor lock-in
- **Local/remote**: Can run on bot server or separate machine
- **Model flexibility**: Swap models without code changes
- **Simple API**: RESTful HTTP, easy to integrate

### Why Not Real-time Streaming?
- LoRa mesh doesn't support streaming
- Each message has overhead (routing, airtime)
- Chunked delivery with delays is more mesh-friendly

### Context Management Strategy
- **Per-channel and per-user**: Isolated conversation threads
- **Time-limited**: 10 minute default TTL prevents stale context
- **Size-limited**: 5 exchange pairs max (configurable)
- **Database-backed**: Persists across bot restarts

### Response Chunking
1. Try to split at sentence boundaries (`. `, `! `, `? `)
2. Fallback to word boundaries if sentences too long
3. Max 5 chunks; truncate and warn if longer
4. Prefix each chunk: `[1/3]`, `[2/3]`, `[3/3]`

---

## Example Usage

### Command-Based Interaction
```
User: !ask What is a LoRa mesh network?

Bot [1/2]: A LoRa mesh network uses low-power, long-range radio to create a decentralized network where devices relay messages peer-to-peer instead of relying on...

Bot [2/2]: ...central infrastructure. Each node forwards packets, extending coverage beyond single-hop range. Great for IoT in remote areas!
```

### Multi-turn Conversation
```
User: !ask What is Python?
Bot: Python is a high-level programming language known for readability and versatility.

User: !ask What's it used for?
Bot: Python is used for web dev, data science, automation, AI/ML, and scripting tasks.

User: !clear-context
Bot: Conversation context cleared.
```

### AI Channel Mode
```
[In #ai-chat channel]

Alice: Explain mesh networking
Bot: Mesh networks are decentralized topologies where each node relays data for others, creating resilient coverage without central infrastructure.

Bob: What frequency does LoRa use in the US?
Bot: In North America, LoRa typically uses the 902-928 MHz ISM band.
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Slow inference** | 30s timeout, use fast 3B param model, "thinking..." indicator |
| **Long responses** | System prompt emphasizes brevity, 5-chunk max, truncation |
| **Mesh saturation** | 10s per-user cooldown, 1.5s chunk delays, 20 req/hr limit |
| **Ollama downtime** | Health checks, graceful errors, fallback messages |
| **Context growth** | Auto-prune by TTL and count, periodic cleanup task |

---

## Testing Strategy

### Unit Tests
- `test_ollama_client.py` - Mocked HTTP responses
- `test_llm_context_manager.py` - DB operations
- `test_llm_command.py` - Command logic

### Integration Tests
- End-to-end `!ask` flow with live Ollama
- Multi-part chunking and delivery
- Context persistence across restarts

### Manual Testing
- Deploy to test mesh with real LoRa devices
- Verify message sizes respect MTU
- Measure latency and airtime usage

---

## Recommended Ollama Model

**Default**: `llama3.2:3b-instruct-q4_K_M`

**Why this model?**
- **Size**: ~2GB RAM (runs on modest hardware)
- **Speed**: Fast inference (~1-5 sec on CPU)
- **Quality**: Good for Q&A and conversation
- **Efficiency**: 4-bit quantization balances size/quality

**Alternatives**:
- Faster/simpler: `llama3.2:1b-instruct-q4_K_M` (~1GB)
- Better quality: `mistral:7b-instruct-q4_K_M` (~4GB)

---

## Future Enhancements (Post-MVP)

1. **Model selection per request**: `!ask-small` uses 1B model, `!ask-large` uses 7B
2. **Context summarization**: Compress old exchanges to fit more history
3. **Tool use**: LLM can invoke other bot commands (e.g., `!wx Seattle`)
4. **Semantic search**: Vector DB for searching mesh message history
5. **Admin commands**: `!llm-stats`, `!llm-health`

---

## Success Criteria

**Quantitative**:
- 10+ unique users/day after 2 weeks
- <15s p50 response time, <30s p95
- <5% error rate
- 80% of conversations span 2+ exchanges

**Qualitative**:
- 70% of users find LLM feature helpful
- No mesh congestion complaints from admins

---

## Getting Started (for Developers)

1. **Read full PRD**: [LLM_INTEGRATION_PRD.md](LLM_INTEGRATION_PRD.md)
2. **Install Ollama**: `curl -fsSL https://ollama.com/install.sh | sh`
3. **Pull model**: `ollama pull llama3.2:3b-instruct-q4_K_M`
4. **Start Ollama**: `ollama serve` (default port 11434)
5. **Add config section**: Copy `[LLM_Command]` from PRD to `config.ini`
6. **Implement Phase 1**: Start with database migration and Ollama client

---

## Questions?

- **Full details**: See [LLM_INTEGRATION_PRD.md](LLM_INTEGRATION_PRD.md)
- **Ollama docs**: https://github.com/ollama/ollama/blob/main/docs/api.md
- **Architecture**: See section 4.1 in PRD
- **Examples**: See Appendix B in PRD

---

**Status**: ✅ PRD Complete, Ready for Implementation
