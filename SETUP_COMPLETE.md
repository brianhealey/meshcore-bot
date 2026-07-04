# ✅ Ralph Setup Complete - LLM Integration Ready

## Summary

Ralph autonomous agent is fully configured and ready to implement LLM integration for MeshCore Bot.

**What was done:**
1. ✅ Cloned Ralph from https://github.com/snarktank/ralph
2. ✅ Analyzed MeshCore Bot architecture
3. ✅ Created comprehensive PRD (200+ lines)
4. ✅ Converted PRD to Ralph format (15 user stories)
5. ✅ Set up Ralph scripts and configuration
6. ✅ Created documentation and guides

## Files Created

### Documentation (5 files)
```
LLM_INTEGRATION_PRD.md          (18 KB) - Full product requirements
LLM_IMPLEMENTATION_SUMMARY.md    (7 KB) - Quick reference
RALPH_SETUP.md                  (12 KB) - Detailed setup guide
RALPH_QUICKSTART.md              (4 KB) - 5-minute start guide ⭐
README_RALPH.md                  (6 KB) - Integration overview
```

### Ralph Configuration (4 files)
```
scripts/ralph/ralph.sh           (3.4 KB) - Autonomous loop script
scripts/ralph/CLAUDE.md          (6.0 KB) - Iteration instructions
scripts/ralph/prd.json          (11 KB) - 15 user stories
scripts/ralph/progress.txt       (241 B) - Progress log (empty)
```

### Repository Setup
```
CLAUDE.md                      (Updated) - Bot architecture guide
```

## The Implementation Plan

Ralph will autonomously implement **15 user stories** in **~2-4 hours**:

### Phase 1: Foundation (Stories 1-5)
- US-001: Database migration for context storage
- US-002: OllamaClient HTTP wrapper
- US-003: LLMContextManager for DB operations
- US-004: Response chunking utility
- US-005: Configuration section

### Phase 2: Command Implementation (Stories 6-10)
- US-006: LLMCommand skeleton
- US-007: Execute method with context
- US-008: Response chunking & delivery
- US-009: Context pruning
- US-010: !clear-context command

### Phase 3: Testing (Stories 11-14)
- US-011: OllamaClient unit tests
- US-012: LLMContextManager unit tests
- US-013: Chunking utility tests
- US-014: Integration test

### Phase 4: Documentation (Story 15)
- US-015: User and developer docs

## Start Ralph Now (3 Commands)

```bash
# 1. Navigate to project
cd ~/code/meshcore-bot

# 2. Create feature branch
git checkout -b ralph/llm-integration

# 3. Run Ralph
./scripts/ralph/ralph.sh --tool claude 25
```

**That's it!** Ralph runs autonomously.

## What Ralph Will Do

Each iteration (~10 minutes):
1. Read `prd.json` and `progress.txt`
2. Pick highest priority story where `passes: false`
3. Implement that story
4. Run quality checks:
   - `mypy` - Type checking
   - `ruff` - Linting
   - `pytest` - Tests
5. If all pass → commit with message `feat: US-XXX - [Story Title]`
6. Mark story as `passes: true` in `prd.json`
7. Append learnings to `progress.txt`
8. Exit (ralph.sh spawns fresh Claude instance)
9. Repeat until all stories complete

## Monitoring Progress

### Terminal 1: Run Ralph
```bash
./scripts/ralph/ralph.sh --tool claude 25
```

### Terminal 2: Watch Progress (Optional)
```bash
# Watch progress file update
watch -n 10 'tail -40 ~/code/meshcore-bot/scripts/ralph/progress.txt'

# Or watch story completion
watch -n 10 'cat scripts/ralph/prd.json | jq ".userStories[] | {id, passes}"'
```

## Expected Output

Ralph will print each iteration:

```
===============================================================
  Ralph Iteration 1 of 25 (claude)
===============================================================

[Claude implements US-001: Database migration]
[Runs mypy, ruff, pytest]
[Commits: feat: US-001 - Add database migration]
[Updates prd.json]
[Appends to progress.txt]

Iteration 1 complete. Continuing...

===============================================================
  Ralph Iteration 2 of 25 (claude)
===============================================================

[Implements US-002: OllamaClient]
...
```

## When Complete

After 15-20 iterations, you'll see:

```
Ralph completed all tasks!
Completed at iteration 18 of 25
```

**Then:**

1. **Review**: `git log --oneline -20`
2. **Test**: `make test`
3. **Manual test**:
   ```bash
   ollama pull llama3.2:3b-instruct-q4_K_M
   ollama serve &
   .venv/bin/python meshcore_bot.py
   # Try: !ask What is LoRa?
   ```
4. **PR**: `gh pr create --title "feat: LLM integration"`

## File Changes Ralph Will Make

```diff
+ modules/ollama_client.py              (new)
+ modules/llm_context_manager.py        (new)
+ modules/commands/llm_command.py       (new)
± modules/db_migrations.py              (add migration)
± modules/utils.py                      (add chunking)
± config.ini.example                    (add [LLM_Command])
+ tests/test_ollama_client.py           (new)
+ tests/test_llm_context_manager.py     (new)
+ tests/test_llm_command.py             (new)
± tests/test_utils.py                   (add chunking tests)
+ docs/llm-integration.md               (new)
```

## Troubleshooting

### Ralph Gets Stuck
```bash
# Stop: Ctrl+C
# Check: tail -50 scripts/ralph/progress.txt
# Fix manually, mark done in prd.json
# Resume: ./scripts/ralph/ralph.sh --tool claude 25
```

### Quality Checks Fail
```bash
# Run manually to debug
.venv/bin/mypy modules/
.venv/bin/ruff check modules/ tests/
.venv/bin/pytest tests/ -v
```

### Pause/Resume
```bash
# Pause: Ctrl+C (safe anytime)
# Resume: ./scripts/ralph/ralph.sh --tool claude 25
```

## Resources

| Document | Purpose |
|----------|---------|
| `RALPH_QUICKSTART.md` ⭐ | **START HERE** - Get running in 5 minutes |
| `LLM_INTEGRATION_PRD.md` | Full requirements and architecture |
| `LLM_IMPLEMENTATION_SUMMARY.md` | Quick reference |
| `RALPH_SETUP.md` | Detailed setup explanation |
| `README_RALPH.md` | Overview and monitoring |

## Architecture Preview

What gets built:

```
User: !ask What is LoRa?
         ↓
CommandManager → LLMCommand.execute()
         ↓
Load context from SQLite (last 5 exchanges)
         ↓
Query Ollama API (http://localhost:11434)
         ↓
Chunk response (~180 chars/chunk)
         ↓
Send chunks with 1.5s delays
         ↓
Save context to SQLite
```

**Context management:**
- Per-user and per-channel isolation
- Time-limited (10 min default)
- Size-limited (5 exchanges)
- Auto-pruning

**Response chunking:**
- Split at sentence boundaries
- Max 180 chars/chunk (LoRa mesh safe)
- Max 5 chunks before truncation
- Chunk indicators: [1/3], [2/3], [3/3]

## Key Metrics

- **Stories**: 15
- **Estimated time**: 2-4 hours
- **Lines of code**: ~1200-1500
- **Test coverage**: >80%
- **Quality checks**: 3 (mypy, ruff, pytest)

## Next Action

**Copy and paste these 3 commands to start:**

```bash
cd ~/code/meshcore-bot
git checkout -b ralph/llm-integration
./scripts/ralph/ralph.sh --tool claude 25
```

Then **walk away** and check back in 30-60 minutes! 🚀

---

**Status**: ✅ Ready to run
**Branch**: ralph/llm-integration (will be created)
**Estimated completion**: 2-4 hours
**Manual intervention needed**: None (Ralph is fully autonomous)

## Questions?

- See `RALPH_QUICKSTART.md` for quick start
- See `RALPH_SETUP.md` for detailed explanation
- See `LLM_INTEGRATION_PRD.md` for full requirements
- See https://github.com/snarktank/ralph for Ralph docs
