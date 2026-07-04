# Ralph Setup Guide for MeshCore Bot LLM Integration

This guide walks through setting up Ralph to autonomously implement the LLM integration feature for MeshCore Bot.

## What is Ralph?

Ralph is an autonomous AI coding agent loop that:
1. Reads a `prd.json` file with user stories
2. Implements one story at a time in fresh Claude Code instances
3. Runs quality checks (tests, typecheck, lint)
4. Commits if checks pass
5. Marks story as complete in `prd.json`
6. Repeats until all stories are done

**Key Benefits**:
- Each iteration gets fresh context (no context overflow)
- Git history provides memory between iterations
- Quality checks prevent broken code from compounding
- Fully autonomous - you can walk away and come back

## Prerequisites

✅ You already have:
- Claude Code installed (`/Users/brianhealey/.local/bin/claude`)
- Git repository (meshcore-bot)
- The LLM integration PRD (`LLM_INTEGRATION_PRD.md`)

## Setup Steps

### 1. Copy Ralph Files to MeshCore Bot

```bash
cd ~/code/meshcore-bot

# Create ralph directory
mkdir -p scripts/ralph

# Copy ralph script
cp ~/code/ralph/ralph.sh scripts/ralph/
chmod +x scripts/ralph/ralph.sh

# Copy Claude Code prompt template
cp ~/code/ralph/CLAUDE.md scripts/ralph/CLAUDE.md
```

### 2. Install Ralph Skills for Claude Code

```bash
# Copy skills to Claude Code config directory
mkdir -p ~/.claude/skills
cp -r ~/code/ralph/skills/ralph ~/.claude/skills/
cp -r ~/code/ralph/skills/prd ~/.claude/skills/
```

### 3. Customize Ralph Prompt for MeshCore Bot

Edit `scripts/ralph/CLAUDE.md` to add meshcore-bot specific quality checks:

```bash
# Open the file
nano scripts/ralph/CLAUDE.md
```

**Add after line 6 (Run quality checks):**

```markdown
6. Run quality checks:
   ```bash
   # Typecheck
   .venv/bin/mypy modules/ --config-file=pyproject.toml

   # Lint
   .venv/bin/ruff check modules/ tests/

   # Run tests
   .venv/bin/pytest tests/ -v --tb=short
   ```
```

### 4. Convert PRD to Ralph Format

Now we'll use Claude Code with the Ralph skill to convert the markdown PRD to `prd.json`:

```bash
cd ~/code/meshcore-bot

# Start Claude Code
claude
```

Then in Claude Code, say:

```
Use the ralph skill to convert LLM_INTEGRATION_PRD.md to scripts/ralph/prd.json format.

Break down the implementation plan into small user stories that can each be completed in one context window.

Remember:
- Each story must be completable in ONE iteration
- Stories must be ordered by dependency (DB migration → client → command → service)
- Include "Typecheck passes" and "Tests pass" in all acceptance criteria
- No browser verification needed (this is a CLI bot, not a web app)
```

### 5. Review the Generated prd.json

The skill will create `scripts/ralph/prd.json`. Review it and make sure:

- [ ] Stories are small enough (one context window each)
- [ ] Dependencies are ordered correctly (DB → backend → integration)
- [ ] Each story has verifiable acceptance criteria
- [ ] All stories have `"passes": false` initially
- [ ] Branch name is appropriate (e.g., `ralph/llm-integration`)

### 6. Initialize Progress Tracking

```bash
cd ~/code/meshcore-bot/scripts/ralph

# Create progress log
echo "# Ralph Progress Log" > progress.txt
echo "Started: $(date)" >> progress.txt
echo "Project: MeshCore Bot LLM Integration" >> progress.txt
echo "---" >> progress.txt
```

### 7. Create Feature Branch

```bash
# Check the branch name from prd.json
BRANCH=$(jq -r '.branchName' scripts/ralph/prd.json)
echo "Branch will be: $BRANCH"

# Create and checkout the branch
git checkout -b $BRANCH
```

### 8. Run Ralph!

```bash
cd ~/code/meshcore-bot

# Run Ralph with Claude Code for 20 iterations
./scripts/ralph/ralph.sh --tool claude 20
```

**What happens now:**

Each iteration (every ~5-10 minutes):
1. Claude Code reads `prd.json` and `progress.txt`
2. Picks the highest priority story where `passes: false`
3. Implements that story
4. Runs `mypy`, `ruff`, and `pytest`
5. If all pass, commits with message like `feat: US-001 - Add Ollama client`
6. Updates `prd.json` to mark story as `passes: true`
7. Appends learnings to `progress.txt`
8. Exits, and ralph.sh spawns a new fresh Claude instance

When all stories have `passes: true`, Ralph outputs `<promise>COMPLETE</promise>` and stops.

## Monitoring Progress

### Check Current Status

```bash
# See which stories are done
cat scripts/ralph/prd.json | jq '.userStories[] | {id, title, passes}'

# See learnings from iterations
tail -50 scripts/ralph/progress.txt

# Check git history
git log --oneline -10
```

### Watch in Real-Time

```bash
# In another terminal, watch the progress file
watch -n 5 'tail -30 ~/code/meshcore-bot/scripts/ralph/progress.txt'
```

## Troubleshooting

### Ralph Gets Stuck on a Story

If Ralph fails the same story 3+ times:

1. **Check the error** in `progress.txt`
2. **Manual intervention**:
   ```bash
   # Fix the issue manually
   git add .
   git commit -m "fix: US-XXX manual correction"

   # Mark story as passing in prd.json
   # Edit the JSON to set "passes": true for that story
   ```
3. **Resume Ralph** - it will pick up the next story

### Quality Checks Fail

Check what's failing:

```bash
# Run checks manually
cd ~/code/meshcore-bot
.venv/bin/mypy modules/
.venv/bin/ruff check modules/ tests/
.venv/bin/pytest tests/ -v
```

Fix the issues and commit, then resume Ralph.

### Need to Pause

Ralph is just a bash loop, so `Ctrl+C` stops it safely. Resume anytime:

```bash
./scripts/ralph/ralph.sh --tool claude 20
```

It reads `prd.json` to see what's left and continues from there.

## Expected Timeline

**Estimated completion**: 15-25 iterations (depends on test failures and complexity)

**Why?**
- ~8-12 stories (based on 4-phase implementation plan)
- Some stories may need 2-3 iterations if tests fail or edge cases found
- Each iteration: ~5-10 minutes

**Total time**: 2-4 hours of autonomous work

## After Ralph Completes

When you see:
```
Ralph completed all tasks!
Completed at iteration X of 20
```

**Next steps:**

1. **Review the code**:
   ```bash
   git log --oneline -20
   git diff main..HEAD
   ```

2. **Manual testing**:
   ```bash
   # Set up Ollama
   ollama pull llama3.2:3b-instruct-q4_K_M
   ollama serve

   # Test the bot
   .venv/bin/python meshcore_bot.py
   # Try: !ask What is LoRa?
   ```

3. **Create PR**:
   ```bash
   git push -u origin ralph/llm-integration
   gh pr create --title "feat: LLM integration via Ollama" \
     --body "Implements LLM integration as described in LLM_INTEGRATION_PRD.md"
   ```

## Tips for Success

### Keep Stories Small

If Ralph runs out of context before finishing a story, **the story was too big**. Split it:

**Too big:**
- "Implement LLM command with context management"

**Right size:**
- US-001: "Add database migration for llm_conversation_context table"
- US-002: "Create OllamaClient class with health check"
- US-003: "Add LLMContextManager for DB operations"
- US-004: "Implement LLMCommand.execute() basic flow"

### Let It Fail Fast

If a story fails quality checks 2-3 times, it's better to:
1. Stop Ralph (`Ctrl+C`)
2. Manually inspect and fix
3. Resume Ralph

Don't let it burn through 10 iterations on the same bug.

### Check Progress Often

Every 3-4 iterations, check `progress.txt` for learnings. If Ralph is discovering the same issue repeatedly, that's a sign to intervene.

## File Structure After Setup

```
meshcore-bot/
├── scripts/
│   └── ralph/
│       ├── ralph.sh              # The loop script
│       ├── CLAUDE.md             # Prompt for each iteration
│       ├── prd.json              # User stories with status
│       ├── progress.txt          # Append-only learnings log
│       ├── .last-branch          # Tracks current branch
│       └── archive/              # Previous runs (auto-created)
│           └── 2026-07-04-old-feature/
│               ├── prd.json
│               └── progress.txt
├── LLM_INTEGRATION_PRD.md        # Original PRD
├── modules/
│   ├── commands/
│   │   └── llm_command.py        # Ralph will create these
│   └── service_plugins/
│       └── llm_channel_service.py
└── tests/
    ├── test_ollama_client.py     # Ralph will create these
    └── test_llm_command.py
```

## Next Steps

1. ✅ Complete setup steps above
2. ✅ Convert PRD to prd.json using Ralph skill
3. ✅ Review and adjust prd.json if needed
4. ✅ Run Ralph: `./scripts/ralph/ralph.sh --tool claude 20`
5. ⏳ Monitor progress
6. ✅ Review and test when complete
7. ✅ Create PR and merge

---

**Ready?** Start with step 1 and work through the setup. Once Ralph is running, you can walk away and check back every 30-60 minutes to monitor progress.
