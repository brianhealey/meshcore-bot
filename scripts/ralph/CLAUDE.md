# Ralph Agent Instructions

You are an autonomous coding agent working on a software project.

## Your Task

1. Read the PRD at `prd.json` (in the same directory as this file)
2. Read the progress log at `progress.txt` (check Codebase Patterns section first)
3. Check you're on the correct branch from PRD `branchName`. If not, check it out or create from main.
4. Pick the **highest priority** user story where `passes: false`
5. Implement that single user story
6. Run quality checks (see below)
7. Update CLAUDE.md files if you discover reusable patterns (see below)
8. If checks pass, commit ALL changes with message: `feat: [Story ID] - [Story Title]`
9. Update the PRD to set `passes: true` for the completed story
10. Append your progress to `progress.txt`

## Quality Checks

Run these commands to verify your implementation:

```bash
# Typecheck (mypy strict mode for new modules)
.venv/bin/mypy modules/ollama_client.py modules/llm_context_manager.py modules/commands/llm_command.py --config-file=pyproject.toml

# Lint (ruff)
.venv/bin/ruff check modules/ tests/

# Run all tests
.venv/bin/pytest tests/ -v --tb=short

# If working on specific module, run its tests only for faster feedback
.venv/bin/pytest tests/test_ollama_client.py -v
```

**IMPORTANT**: Do NOT commit if any check fails. Fix the issues first.

## Progress Report Format

APPEND to progress.txt (never replace, always append):
```
## [Date/Time] - [Story ID]
- What was implemented
- Files changed
- **Learnings for future iterations:**
  - Patterns discovered (e.g., "this codebase uses X for Y")
  - Gotchas encountered (e.g., "don't forget to update Z when changing W")
  - Useful context (e.g., "the evaluation panel is in component X")
---
```

The learnings section is critical - it helps future iterations avoid repeating mistakes and understand the codebase better.

## Consolidate Patterns

If you discover a **reusable pattern** that future iterations should know, add it to the `## Codebase Patterns` section at the TOP of progress.txt (create it if it doesn't exist). This section should consolidate the most important learnings:

```
## Codebase Patterns
- Database migrations go in modules/db_migrations.py with sequential IDs
- Commands inherit from BaseCommand and live in modules/commands/
- Use AsyncDBManager for async DB operations
- Configuration follows INI format with section per plugin
- Use tmp_path fixture for test databases (not :memory:)
```

Only add patterns that are **general and reusable**, not story-specific details.

## Update CLAUDE.md Files

Before committing, check if any edited files have learnings worth preserving in nearby CLAUDE.md files:

1. **Identify directories with edited files** - Look at which directories you modified
2. **Check for existing CLAUDE.md** - Look for CLAUDE.md in those directories or parent directories
3. **Add valuable learnings** - If you discovered something future developers/agents should know:
   - API patterns or conventions specific to that module
   - Gotchas or non-obvious requirements
   - Dependencies between files
   - Testing approaches for that area
   - Configuration or environment requirements

**Examples of good CLAUDE.md additions:**
- "When modifying X, also update Y to keep them in sync"
- "This module uses pattern Z for all API calls"
- "Tests require the dev server running on PORT 3000"
- "Field names must match the template exactly"

**Do NOT add:**
- Story-specific implementation details
- Temporary debugging notes
- Information already in progress.txt

Only update CLAUDE.md if you have **genuinely reusable knowledge** that would help future work in that directory.

## MeshCore Bot Specific Patterns

### Plugin Architecture
- Commands inherit from `BaseCommand` (modules/commands/base_command.py)
- Implement `async def execute(self, message: MeshMessage) -> bool`
- Set class attributes: name, keywords, description, category
- Use `self.get_config_value(section, key, fallback, value_type)` for config
- Use `self.send_response(message, text)` for single replies
- Use `self.send_response_chunked(message, chunks)` for multi-part messages

### Database Patterns
- Migrations in `modules/db_migrations.py` as `_mNNNN_description(cursor)` functions
- Append to `MIGRATIONS` list: `(NNNN, "description", _mNNNN_function)`
- Never modify existing migrations - always add new ones
- Use `AsyncDBManager` for async operations
- Use `tmp_path` fixture in tests for file-based SQLite

### Testing Patterns
- Use fixtures from `tests/conftest.py`: mock_logger, minimal_config, test_db
- Async tests work without `@pytest.mark.asyncio` decorator
- Use `MagicMock` for sync methods, `AsyncMock` for async methods
- Test files match module names: `test_ollama_client.py` for `ollama_client.py`

### Type Checking
- New modules should pass strict mypy checks
- Add type hints to all function signatures
- Use `from typing import Any, Optional` for complex types
- Configure per-module mypy overrides in `pyproject.toml` if needed

### Configuration
- INI format with sections like `[LLM_Command]`
- Boolean: `enabled = true`
- String: `ollama_endpoint = http://localhost:11434`
- Integer: `timeout_seconds = 30`
- Comments start with `#`

## Quality Requirements

- ALL commits must pass typecheck, lint, and tests
- Do NOT commit broken code
- Keep changes focused and minimal
- Follow existing code patterns
- Write comprehensive docstrings (Google style)
- Add type hints to all new functions

## Stop Condition

After completing a user story, check if ALL stories have `passes: true`.

If ALL stories are complete and passing, reply with:
<promise>COMPLETE</promise>

If there are still stories with `passes: false`, end your response normally (another iteration will pick up the next story).

## Important

- Work on ONE story per iteration
- Commit frequently
- Keep CI green
- Read the Codebase Patterns section in progress.txt before starting
- Check CLAUDE.md in project root for codebase-wide patterns
