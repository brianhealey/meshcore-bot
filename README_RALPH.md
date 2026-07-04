# Ralph Integration Summary

This repository is now set up with Ralph autonomous agent for implementing the LLM integration feature.

## What You Have

### Documentation
- **`LLM_INTEGRATION_PRD.md`** - Full product requirements (200+ lines)
- **`LLM_IMPLEMENTATION_SUMMARY.md`** - Quick reference summary
- **`RALPH_SETUP.md`** - Detailed setup instructions
- **`RALPH_QUICKSTART.md`** - Get started in 5 minutes ⭐ **START HERE**
- **`README_RALPH.md`** - This file

### Ralph Setup
- **`scripts/ralph/ralph.sh`** - Autonomous loop script
- **`scripts/ralph/CLAUDE.md`** - Instructions for each iteration
- **`scripts/ralph/prd.json`** - 15 user stories to implement
- **`scripts/ralph/progress.txt`** - Progress tracking log

## Quick Start (Copy-Paste)

```bash
# Navigate to project
cd ~/code/meshcore-bot

# Create feature branch
git checkout -b ralph/llm-integration

# Run Ralph (autonomous implementation)
./scripts/ralph/ralph.sh --tool claude 25
```

**That's it!** Ralph will autonomously implement all 15 user stories.

## What Ralph Will Build

### Core Components
1. **Database Migration** - `llm_conversation_context` table
2. **Ollama Client** - HTTP wrapper for Ollama API
3. **Context Manager** - Conversation history CRUD
4. **LLM Command** - `!ask` and `!clear-context` commands
5. **Response Chunking** - Split long responses for LoRa mesh
6. **Configuration** - `[LLM_Command]` section in config
7. **Tests** - Unit and integration tests (>80% coverage)
8. **Documentation** - User and developer docs

### User Features
```
User: !ask What is a LoRa mesh network?

Bot [1/2]: A LoRa mesh network uses low-power, long-range radio to create
a decentralized network where devices relay messages peer-to-peer...

Bot [2/2]: ...instead of relying on central infrastructure. Each node forwards
packets, extending coverage beyond single-hop range.

User: !ask How far can it reach?

Bot: LoRa can transmit up to 10+ km in rural areas, or 2-5 km in urban
environments, depending on obstacles and antenna height.

User: !clear-context

Bot: Conversation context cleared.
```

## Timeline

- **15 user stories**
- **~10 minutes per story** (with quality checks)
- **Estimated total: 2-4 hours of autonomous work**

## File Structure After Ralph

```
meshcore-bot/
├── modules/
│   ├── ollama_client.py              [NEW] HTTP client
│   ├── llm_context_manager.py        [NEW] Context CRUD
│   ├── db_migrations.py              [MODIFIED] +migration
│   ├── utils.py                      [MODIFIED] +chunking
│   └── commands/
│       └── llm_command.py            [NEW] !ask command
├── tests/
│   ├── test_ollama_client.py         [NEW]
│   ├── test_llm_context_manager.py   [NEW]
│   ├── test_llm_command.py           [NEW]
│   └── test_utils.py                 [MODIFIED] +chunking tests
├── config.ini.example                [MODIFIED] +[LLM_Command]
├── docs/
│   └── llm-integration.md            [NEW]
└── scripts/ralph/
    ├── prd.json                      [MODIFIED] passes: true
    └── progress.txt                  [MODIFIED] learnings log
```

## Monitoring Progress

### Real-time Watch
```bash
# In another terminal
watch -n 10 'tail -40 ~/code/meshcore-bot/scripts/ralph/progress.txt'
```

### Check Status
```bash
# See completed stories
jq '.userStories[] | select(.passes == true) | .id' scripts/ralph/prd.json

# Count progress
echo "$(jq '[.userStories[] | select(.passes == true)] | length' scripts/ralph/prd.json)/15 stories done"

# View latest commit
git log -1 --oneline
```

## When Ralph Completes

You'll see:
```
Ralph completed all tasks!
Completed at iteration 18 of 25
```

**Next steps:**

1. **Review the implementation**
   ```bash
   git log --oneline ralph/llm-integration
   git diff main..ralph/llm-integration
   ```

2. **Run tests**
   ```bash
   make test
   ```

3. **Manual testing**
   ```bash
   # Install and run Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull llama3.2:3b-instruct-q4_K_M
   ollama serve

   # Configure bot
   cp config.ini.example config.ini
   # Edit [LLM_Command] section

   # Run bot
   .venv/bin/python meshcore_bot.py
   ```

4. **Create pull request**
   ```bash
   git push -u origin ralph/llm-integration
   gh pr create --title "feat: LLM integration via Ollama" \
     --body-file LLM_IMPLEMENTATION_SUMMARY.md
   ```

## Troubleshooting

### Ralph Gets Stuck
If same story fails 3+ times:
```bash
# Stop Ralph: Ctrl+C
# Check error
tail -50 scripts/ralph/progress.txt

# Fix manually, then mark done
nano scripts/ralph/prd.json  # Set passes: true

# Resume
./scripts/ralph/ralph.sh --tool claude 25
```

### Quality Checks Fail
```bash
# Run checks manually
.venv/bin/mypy modules/
.venv/bin/ruff check modules/ tests/
.venv/bin/pytest tests/ -v
```

### Need to Pause
```bash
# Just Ctrl+C - it's safe to stop anytime

# Resume later
./scripts/ralph/ralph.sh --tool claude 25
```

## Architecture Overview

```
┌─────────────┐
│  Mesh User  │
└──────┬──────┘
       │ !ask What is LoRa?
       ▼
┌────────────────────────────┐
│   LLMCommand.execute()     │
│   ├─ Load context from DB  │
│   ├─ Query Ollama API      │
│   ├─ Chunk response        │
│   ├─ Send chunks           │
│   └─ Save context to DB    │
└──────────┬─────────────────┘
           │ HTTP POST
           ▼
    ┌──────────────┐
    │    Ollama    │
    │   (Local)    │
    └──────────────┘
```

## Key Constraints Solved

| Constraint | Solution |
|------------|----------|
| **237 byte LoRa message limit** | Intelligent chunking at sentence boundaries |
| **Network latency** | 30s configurable timeout, async processing |
| **Limited bandwidth** | Rate limiting, chunk delays (1.5s between parts) |
| **Context continuity** | SQLite-backed conversation history |
| **Unbounded DB growth** | Auto-pruning by age (10 min) and size (5 exchanges) |

## Resources

- **Full PRD**: `LLM_INTEGRATION_PRD.md`
- **Quick Start**: `RALPH_QUICKSTART.md` ⭐
- **Setup Guide**: `RALPH_SETUP.md`
- **Ollama Docs**: https://ollama.com
- **Ralph Docs**: https://github.com/snarktank/ralph

---

## Ready to Start?

```bash
cd ~/code/meshcore-bot
git checkout -b ralph/llm-integration
./scripts/ralph/ralph.sh --tool claude 25
```

Then check back in 30-60 minutes to monitor progress! 🚀
