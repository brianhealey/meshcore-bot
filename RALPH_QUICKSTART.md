# Ralph Quickstart - LLM Integration

## Setup Complete! ✅

Ralph is ready to autonomously implement the LLM integration. Here's what's been set up:

```
meshcore-bot/
├── scripts/ralph/
│   ├── ralph.sh              ✅ Autonomous loop script
│   ├── CLAUDE.md             ✅ Instructions for each iteration
│   ├── prd.json              ✅ 15 user stories ready to implement
│   └── progress.txt          ✅ Empty progress log
├── LLM_INTEGRATION_PRD.md    ✅ Full requirements document
├── RALPH_SETUP.md            ✅ Detailed setup guide
└── RALPH_QUICKSTART.md       ⬅️ You are here
```

## Quick Start (5 minutes)

### 1. Create the Feature Branch

```bash
cd ~/code/meshcore-bot
git checkout -b ralph/llm-integration
```

### 2. Run Ralph

```bash
./scripts/ralph/ralph.sh --tool claude 25
```

**What happens:** Ralph will autonomously:
- Pick user story US-001 (database migration)
- Implement it
- Run typecheck, lint, tests
- Commit if all pass
- Mark US-001 as done
- Move to US-002
- Repeat until all 15 stories are complete

### 3. Monitor Progress (Optional)

In another terminal:

```bash
# Watch progress file update in real-time
watch -n 10 'tail -40 ~/code/meshcore-bot/scripts/ralph/progress.txt'

# Or check which stories are done
watch -n 10 'cat ~/code/meshcore-bot/scripts/ralph/prd.json | jq ".userStories[] | {id, title, passes}"'
```

### 4. When Complete

Ralph will output:
```
Ralph completed all tasks!
Completed at iteration X of 25
```

Then:

```bash
# Review the code
git log --oneline -20

# Run full test suite
make test

# Manual testing (requires Ollama running)
ollama pull llama3.2:3b-instruct-q4_K_M
ollama serve &

# Test the bot
.venv/bin/python meshcore_bot.py
# Try: !ask What is LoRa?
```

## Expected Timeline

- **15 stories** × **~10 min/story** = **~2.5 hours**
- Some stories may need 2-3 iterations (test failures, edge cases)
- **Total estimate: 2-4 hours of autonomous work**

## The User Stories

Ralph will implement these in order:

1. **US-001**: Database migration for context storage
2. **US-002**: OllamaClient HTTP wrapper
3. **US-003**: LLMContextManager for DB operations
4. **US-004**: Response chunking utility
5. **US-005**: Configuration section
6. **US-006**: LLMCommand skeleton
7. **US-007**: LLMCommand execute with context
8. **US-008**: Response chunking & delivery
9. **US-009**: Context pruning
10. **US-010**: !clear-context command
11. **US-011**: OllamaClient tests
12. **US-012**: LLMContextManager tests
13. **US-013**: Chunking tests
14. **US-014**: Integration test
15. **US-015**: Documentation

## If Ralph Gets Stuck

**Symptom**: Same story fails 3+ times

**Solution**:
```bash
# Stop Ralph (Ctrl+C)

# Check what's failing
cat scripts/ralph/progress.txt | tail -50

# Fix manually, then mark as done
nano scripts/ralph/prd.json
# Change "passes": false → "passes": true for that story

# Resume Ralph
./scripts/ralph/ralph.sh --tool claude 25
```

## Pausing and Resuming

Ralph is just a bash loop - `Ctrl+C` stops it safely.

Resume anytime:
```bash
./scripts/ralph/ralph.sh --tool claude 25
```

It reads `prd.json` to see what's left and continues.

## Monitoring Commands

```bash
# See completed stories
jq '.userStories[] | select(.passes == true) | {id, title}' scripts/ralph/prd.json

# See pending stories
jq '.userStories[] | select(.passes == false) | {id, title}' scripts/ralph/prd.json

# Count progress
echo "Done: $(jq '[.userStories[] | select(.passes == true)] | length' scripts/ralph/prd.json)/15"

# Check latest learnings
tail -30 scripts/ralph/progress.txt
```

## After Ralph Completes

1. **Review**: `git log --oneline -20`
2. **Test**: `make test`
3. **Manual test** with Ollama
4. **Create PR**:
   ```bash
   git push -u origin ralph/llm-integration
   gh pr create --title "feat: LLM integration via Ollama" \
     --body-file LLM_IMPLEMENTATION_SUMMARY.md
   ```

## Next Steps

**Option 1: Start Ralph now** (recommended)
```bash
cd ~/code/meshcore-bot
git checkout -b ralph/llm-integration
./scripts/ralph/ralph.sh --tool claude 25
```

**Option 2: Review the plan first**
```bash
# See all user stories
jq '.userStories[] | {id, title, acceptanceCriteria}' scripts/ralph/prd.json | less

# Read the full PRD
open LLM_INTEGRATION_PRD.md
```

---

## Ready? Let's Go! 🚀

```bash
cd ~/code/meshcore-bot
git checkout -b ralph/llm-integration
./scripts/ralph/ralph.sh --tool claude 25
```

Then sit back and watch Ralph work. Check back in 30-60 minutes to see progress.
